"""Feature 4 : pré-rédaction de réponses (streaming), enregistrement en brouillon ou envoi."""
from __future__ import annotations

import asyncio
from email.utils import getaddresses, parseaddr
from typing import AsyncIterator

from ..llm import prompts
from ..mail.backend import MailError
from ..mail.compose import build_reply, reply_subject, send_smtp
from ..mail.models import MailHeader
from ..mail.parsing import clean_for_llm
from .common import fmt_date, get_body, sender_label
from .context import AppContext


async def reply_context(ctx: AppContext, h: MailHeader) -> dict:
    """Destinataires / objet proposés pour la réponse."""
    body = await get_body(ctx, h)
    me = ctx.my_addresses()
    reply_to = body.headers.get("Reply-To") or body.headers.get("From") or h.from_addr
    to_addr = parseaddr(reply_to)[1] or h.from_addr
    others = [a for _, a in getaddresses([body.headers.get("To", ""), body.headers.get("Cc", "")])
              if a and a.lower() not in me and a.lower() != to_addr.lower()]
    return {
        "to": to_addr,
        "cc_all": ", ".join(dict.fromkeys(others)),
        "subject": reply_subject(h.subject),
    }


async def draft_stream(ctx: AppContext, h: MailHeader, instructions: str, tone: str) -> AsyncIterator[str]:
    s = ctx.settings
    body = await get_body(ctx, h)
    text = clean_for_llm(body.text, s.llm.max_chars_per_email * 2)
    # le fil précédent (citations) apporte du contexte : on en garde un extrait court
    quoted = [line[1:].strip() for line in body.text.splitlines() if line.startswith(">")]
    thread = ""
    if quoted:
        thread = "\nExtrait du fil précédent :\n" + clean_for_llm("\n".join(quoted), 600)
    system = prompts.DRAFT_SYSTEM.format(
        profile=prompts.profile_block(s.profile),
        language=s.profile.language,
        tone=prompts.TONES.get(tone, tone or prompts.TONES["pro"]),
        signature=s.profile.signature.strip() or s.profile.full_name or "(aucune)",
    )
    user = prompts.DRAFT_USER.format(
        sender=sender_label(h), date=fmt_date(h.date), subject=h.subject, body=text, thread=thread,
        instructions=instructions.strip() or "Réponds de manière appropriée à toutes les demandes.",
    )
    async for delta in ctx.llm.stream(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=max(0.3, s.llm.temperature), max_tokens=max(700, s.llm.max_tokens),
    ):
        yield delta


async def _drafts_folder(ctx: AppContext) -> str:
    configured = ctx.settings.mail.drafts_folder
    if configured:
        return configured
    found = await ctx.mail(ctx.backend.special_folder, "drafts")
    if found:
        return found
    await ctx.mail(ctx.backend.create_folder, "Drafts")
    return "Drafts"


async def save_or_send(ctx: AppContext, h: MailHeader, *, to: str, cc: str, subject: str, body: str, send: bool) -> dict:
    if not to.strip():
        raise MailError("Destinataire manquant")
    if not body.strip():
        raise MailError("Le message est vide")
    original = await get_body(ctx, h)
    msg = build_reply(
        ctx.settings.mail, to=to, cc=cc, subject=subject, body=body,
        in_reply_to=h.message_id, references=original.headers.get("References", h.references),
    )
    if send:
        if ctx.settings.mail.provider == "demo":
            sent = await ctx.mail(ctx.backend.special_folder, "sent") or "Envoyés"
            await ctx.mail(ctx.backend.append, sent, msg.as_bytes(), "(\\Seen)")
        else:
            await asyncio.to_thread(send_smtp, ctx.settings.mail, msg)
            host = (ctx.settings.mail.smtp_host or "").lower()
            if not any(p in host for p in ("gmail", "office365", "outlook")):  # ceux-ci archivent seuls
                sent = await ctx.mail(ctx.backend.special_folder, "sent")
                if sent:
                    await ctx.mail(ctx.backend.append, sent, msg.as_bytes(), "(\\Seen)")
        return {"status": "sent"}
    folder = await _drafts_folder(ctx)
    await ctx.mail(ctx.backend.append, folder, msg.as_bytes(), "(\\Draft \\Seen)")
    return {"status": "draft", "folder": folder}
