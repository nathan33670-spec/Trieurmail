"""Feature 3 : synthèse d'emails.

- résumé détaillé d'un email (points clés, actions, échéance, idées de réponse) ;
- résumés express d'une liste, plusieurs emails par appel ;
- synthèse globale (map-reduce) réutilisant les résumés express en cache.
"""
from __future__ import annotations

from ..llm import prompts
from ..mail.models import MailHeader
from ..mail.parsing import clean_for_llm
from .common import chunks, fmt_date, get_body, run_batches, sender_label
from .context import AppContext
from .jobs import Job


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()][:8]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


async def summarize_one(ctx: AppContext, h: MailHeader, force: bool = False) -> dict:
    s = ctx.settings
    sig = ctx.signature("sum-v1", s.llm.model, s.profile.language)
    if not force:
        cached = ctx.db.get_insights([h.mid], "summary", sig)
        if h.mid in cached:
            return cached[h.mid]
    body = await get_body(ctx, h)
    text = clean_for_llm(body.text, s.llm.max_chars_per_email * 2)
    attachments = ", ".join(a.filename for a in body.attachments)
    user = (
        f"De : {sender_label(h)}\nDate : {fmt_date(h.date)}\nObjet : {h.subject}\n"
        + (f"Pièces jointes : {attachments}\n" if attachments else "")
        + f"\n{text}"
    )
    data = await ctx.llm.chat_json(
        [{"role": "system", "content": prompts.SUMMARY_SYSTEM.format(language=s.profile.language)},
         {"role": "user", "content": user}],
        max_tokens=600, use_cache=not force,
    )
    if not isinstance(data, dict):
        data = {"summary": str(data)}
    result = {
        "summary": str(data.get("summary", "")).strip(),
        "key_points": _as_list(data.get("key_points")),
        "actions": _as_list(data.get("actions")),
        "deadline": str(data.get("deadline", "") or "").strip(),
        "reply_suggestions": _as_list(data.get("reply_suggestions"))[:4],
    }
    ctx.db.put_insights("summary", sig, {h.mid: result})
    return result


async def brief_many(ctx: AppContext, headers: list[MailHeader], job: Job | None = None,
                     span: tuple[float, float] = (0.0, 1.0)) -> dict[str, str]:
    """Résumés d'une phrase, regroupés par lots pour limiter le nombre d'appels."""
    s = ctx.settings
    sig = ctx.signature("brief-v1", s.llm.fast_model(), s.profile.language)
    mids = [h.mid for h in headers]
    cached = {m: v for m, v in ctx.db.get_insights(mids, "brief", sig).items()}
    todo = [h for h in headers if h.mid not in cached]
    if not todo:
        return cached
    lo, hi = span
    mid_point = lo + (hi - lo) * 0.4
    # corps nécessaires : téléchargés une fois puis gardés en cache
    texts: dict[str, str] = {}
    for i, h in enumerate(todo):
        if job:
            job.update(lo + (mid_point - lo) * i / len(todo), f"Lecture des emails {i + 1}/{len(todo)}")
        try:
            body = await get_body(ctx, h)
            texts[h.mid] = clean_for_llm(body.text, min(700, s.llm.max_chars_per_email))
        except Exception:
            texts[h.mid] = h.snippet
    system = prompts.BATCH_SUMMARY_SYSTEM.format(language=s.profile.language)

    async def run(batch: list[MailHeader]) -> dict:
        user = "\n\n".join(
            f"[{i + 1}] De: {sender_label(h)} | Objet: {h.subject}\n{texts[h.mid]}" for i, h in enumerate(batch)
        )
        data = await ctx.llm.chat_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=s.llm.fast_model(), max_tokens=70 * len(batch) + 80, temperature=0.1,
        )
        items = data.get("items", data) if isinstance(data, dict) else data
        out = {}
        for item in items if isinstance(items, list) else []:
            try:
                h = batch[int(str(item.get("id")).strip("[] ")) - 1]
            except (ValueError, TypeError, IndexError, AttributeError):
                continue
            out[h.mid] = str(item.get("summary", "")).strip()
        ctx.db.put_insights("brief", sig, out)
        return out

    batch_size = max(4, min(s.llm.batch_size, 10))
    for r in await run_batches(job, list(chunks(todo, batch_size)), run, "Résumés express lot", (mid_point, hi)):
        if r:
            cached.update(r)
    return cached


async def digest(ctx: AppContext, headers: list[MailHeader], job: Job) -> dict:
    s = ctx.settings
    headers = sorted(headers, key=lambda h: h.date, reverse=True)[:150]
    briefs = await brief_many(ctx, headers, job, (0.0, 0.85))
    job.update(0.88, "Rédaction de la synthèse globale…")
    lines = "\n".join(
        f"- {fmt_date(h.date)} | {h.from_name or h.from_addr} | {h.subject} — {briefs.get(h.mid, h.snippet[:160])}"
        for h in headers
    )
    text = await ctx.llm.chat(
        [{"role": "system", "content": prompts.DIGEST_SYSTEM.format(
            language=s.profile.language, profile=prompts.profile_block(s.profile))},
         {"role": "user", "content": f"{len(headers)} emails :\n{lines}"}],
        max_tokens=max(600, s.llm.max_tokens),
    )
    return {"markdown": text, "count": len(headers), "briefs": briefs}
