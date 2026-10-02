"""Décodage et nettoyage des emails (en-têtes, corps, extraits).

Le nettoyage (suppression des citations, signatures, HTML) réduit fortement
le nombre de tokens envoyés au LLM.
"""
from __future__ import annotations

import email
import html as html_lib
import re
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Optional

from .models import Attachment, MailBody

BULK_SENDER_RE = re.compile(
    r"(no-?reply|ne-?pas-?repondre|donotreply|notifications?|newsletter|mailer|bounce|news@|info@|marketing|promo)",
    re.I,
)


def decode_mime(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return str(value).strip()


def parse_from(value: str) -> tuple[str, str]:
    name, addr = parseaddr(decode_mime(value))
    return name.strip().strip('"'), addr.strip().lower()


def parse_addr_list(value: str) -> str:
    pairs = getaddresses([decode_mime(value)]) if value else []
    return ",".join(a.lower() for _, a in pairs if a)


def parse_date(value: str, fallback: int = 0) -> int:
    if not value:
        return fallback
    try:
        dt = parsedate_to_datetime(value)
        return int(dt.timestamp())
    except Exception:
        return fallback


def is_bulk(msg: Message, from_addr: str) -> bool:
    if msg.get("List-Unsubscribe") or msg.get("List-Id"):
        return True
    if (msg.get("Precedence") or "").lower() in ("bulk", "list", "junk"):
        return True
    auto = (msg.get("Auto-Submitted") or "").lower()
    if auto and auto != "no":
        return True
    return bool(BULK_SENDER_RE.search(from_addr or ""))


def is_high_importance(msg: Message) -> bool:
    prio = (msg.get("X-Priority") or "").strip()
    if prio[:1] in ("1", "2"):
        return True
    return (msg.get("Importance") or "").lower() == "high"


_TAG_BLOCKS = re.compile(r"<(script|style|head|title)[^>]*>.*?</\1>", re.S | re.I)
_BR = re.compile(r"<\s*(br|/p|/div|/tr|/li|/h\d)\s*/?>", re.I)
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    text = _TAG_BLOCKS.sub(" ", raw)
    text = _BR.sub("\n", text)
    text = _TAGS.sub(" ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t\r\f\v ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


_QUOTE_HEADER = re.compile(
    r"^(le .{5,200}a écrit\s*:|on .{5,200}wrote\s*:|-{2,}\s*(original message|message d'origine|message transféré|forwarded message)\s*-{2,}|de\s*:\s.+|from\s*:\s.+)$",
    re.I,
)
_SIGNATURE = re.compile(r"^(--\s*|__+|envoyé de mon (iphone|android|mobile).*|sent from my .*)$", re.I)


def clean_for_llm(text: str, max_chars: int) -> str:
    """Retire citations, signatures et espaces superflus puis tronque."""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if _QUOTE_HEADER.match(stripped) and lines:
            break
        if _SIGNATURE.match(stripped) and lines:
            break
        lines.append(stripped)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"https?://\S{60,}", "[lien]", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0] + " […]"
    return cleaned


def make_snippet(text: str, length: int = 240) -> str:
    snippet = clean_for_llm(text, length + 50)
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:length]


def _decode_part(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def extract_body(msg: Message) -> MailBody:
    body = MailBody()
    texts: list[str] = []
    htmls: list[str] = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart():
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        ctype = part.get_content_type()
        if filename or "attachment" in disposition:
            try:
                size = len(part.get_payload(decode=True) or b"")
            except Exception:
                size = 0
            body.attachments.append(Attachment(decode_mime(filename or "pièce jointe"), ctype, size))
            continue
        if ctype == "text/plain":
            texts.append(_decode_part(part))
        elif ctype == "text/html":
            htmls.append(_decode_part(part))
    body.text = "\n".join(t for t in texts if t).strip()
    body.html = "\n".join(htmls).strip()
    if not body.text and body.html:
        body.text = html_to_text(body.html)
    return body


def has_attachment_hint(msg: Message) -> bool:
    ctype = (msg.get("Content-Type") or "").lower()
    return "multipart/mixed" in ctype


def parse_bytes(raw: bytes) -> Message:
    return email.message_from_bytes(raw, policy=policy.compat32)


def snippet_from_partial(header_bytes: bytes, text_bytes: bytes) -> str:
    """Construit un extrait à partir d'un en-tête et d'un début de corps tronqué."""
    try:
        msg = parse_bytes(header_bytes.rstrip(b"\r\n") + b"\r\n\r\n" + text_bytes)
        body = extract_body(msg)
        return make_snippet(body.text)
    except Exception:
        return ""
