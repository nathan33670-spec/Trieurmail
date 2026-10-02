"""Construction des réponses et envoi SMTP."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from ..config import MailSettings
from .backend import MailError


def reply_subject(subject: str) -> str:
    s = subject or ""
    return s if s.lower().startswith(("re:", "re :")) else f"Re: {s}"


def build_reply(
    settings: MailSettings,
    *,
    to: str,
    cc: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    references: str = "",
) -> EmailMessage:
    msg = EmailMessage()
    sender = settings.from_address or settings.username
    msg["From"] = formataddr((settings.from_name, sender)) if settings.from_name else sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    domain = sender.split("@")[-1] if "@" in sender else None
    msg["Message-ID"] = make_msgid(domain=domain)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = f"{references} {in_reply_to}".strip()
    msg.set_content(body)
    return msg


def send_smtp(settings: MailSettings, msg: EmailMessage) -> None:
    if not settings.smtp_host:
        raise MailError("Serveur SMTP non configuré")
    user = settings.smtp_username or settings.username
    password = settings.smtp_password or settings.password
    ctx = ssl.create_default_context()
    try:
        if settings.smtp_security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=60)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=60)
            if settings.smtp_security == "starttls":
                server.starttls(context=ctx)
        with server:
            if user:
                server.login(user, password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"Envoi SMTP impossible : {exc}") from exc
