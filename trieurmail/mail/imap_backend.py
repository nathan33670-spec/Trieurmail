"""Backend IMAP générique (Gmail, Outlook, OVH, Infomaniak, Dovecot...).

Optimisations :
- les en-têtes et un extrait de 3 Ko sont récupérés en lots de 200 messages
  (pas de téléchargement des corps complets pour le tri / la priorisation) ;
- BODY.PEEK pour ne jamais marquer un message comme lu par erreur ;
- dossier sélectionné mémorisé pour éviter les SELECT redondants ;
- MOVE natif si le serveur le supporte (sinon COPY + suppression).
"""
from __future__ import annotations

import imaplib
import re
import ssl
import threading
import time
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from functools import wraps
from typing import Optional

from . import imap_utf7
from .backend import MailBackend, MailError
from .models import FolderInfo, MailBody, MailHeader
from .parsing import (
    decode_mime,
    extract_body,
    has_attachment_hint,
    is_bulk,
    is_high_importance,
    parse_addr_list,
    parse_bytes,
    parse_date,
    parse_from,
    snippet_from_partial,
)

HEADER_FIELDS = (
    "FROM TO CC SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES LIST-UNSUBSCRIBE LIST-ID "
    "PRECEDENCE AUTO-SUBMITTED CONTENT-TYPE CONTENT-TRANSFER-ENCODING X-PRIORITY IMPORTANCE"
)
SNIPPET_BYTES = 3000
CHUNK = 200

SPECIAL_FLAGS = {
    "\\drafts": "drafts",
    "\\sent": "sent",
    "\\trash": "trash",
    "\\junk": "junk",
    "\\archive": "archive",
    "\\all": "all",
    "\\flagged": "flagged",
}
SPECIAL_NAMES = {
    "drafts": ("drafts", "brouillons", "draft"),
    "sent": ("sent", "envoyés", "sent items", "sent mail", "éléments envoyés", "messages envoyés"),
    "trash": ("trash", "corbeille", "deleted items", "éléments supprimés"),
    "junk": ("junk", "spam", "courrier indésirable", "pourriel"),
    "archive": ("archive", "archives"),
}

_LIST_RE = re.compile(r'^\((?P<flags>[^)]*)\)\s+(?P<delim>"(?:[^"\\]|\\.)*"|NIL)\s*(?P<name>.*)$')
_MSG_START = re.compile(rb"^\d+ \(")


def _imap_date(d: date) -> str:
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{d.day:02d}-{months[d.month - 1]}-{d.year}"


def uid_set(uids: list[int]) -> str:
    """Compresse une liste d'uids en plages IMAP : 1:5,8,10:12."""
    if not uids:
        return ""
    s = sorted(set(uids))
    parts: list[str] = []
    start = prev = s[0]
    for u in s[1:]:
        if u == prev + 1:
            prev = u
            continue
        parts.append(f"{start}:{prev}" if start != prev else str(start))
        start = prev = u
    parts.append(f"{start}:{prev}" if start != prev else str(start))
    return ",".join(parts)


def _quote(name: str) -> str:
    encoded = imap_utf7.encode(name)
    return '"' + encoded.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def group_fetch_response(data: list) -> list[dict]:
    """Regroupe la réponse brute d'imaplib en messages {meta, header, text, full}."""
    messages: list[dict] = []
    current: Optional[dict] = None
    for item in data:
        if isinstance(item, tuple):
            prefix, literal = item[0], item[1]
            if _MSG_START.match(prefix) or current is None:
                current = {"meta": b"", "header": b"", "text": b"", "full": b""}
                messages.append(current)
            current["meta"] += b" " + prefix
            label = prefix.rsplit(b"BODY[", 1)[-1].upper()
            if label.startswith(b"HEADER"):
                current["header"] = literal
            elif label.startswith(b"TEXT"):
                current["text"] = literal
            elif label.startswith(b"]"):
                current["full"] = literal
        elif isinstance(item, bytes):
            if _MSG_START.match(item):
                current = {"meta": item, "header": b"", "text": b"", "full": b""}
                messages.append(current)
            elif current is not None:
                current["meta"] += b" " + item
    return messages


def _meta_uid(meta: bytes) -> Optional[int]:
    m = re.search(rb"UID (\d+)", meta)
    return int(m.group(1)) if m else None


def _meta_flags(meta: bytes) -> list[str]:
    m = re.search(rb"FLAGS \(([^)]*)\)", meta)
    return m.group(1).decode(errors="replace").lower().split() if m else []


def _meta_size(meta: bytes) -> int:
    m = re.search(rb"RFC822\.SIZE (\d+)", meta)
    return int(m.group(1)) if m else 0


def _meta_internaldate(meta: bytes) -> int:
    m = re.search(rb'INTERNALDATE "([^"]+)"', meta)
    if not m:
        return 0
    try:
        return int(parsedate_to_datetime(m.group(1).decode()).timestamp())
    except Exception:
        try:
            return int(time.mktime(imaplib.Internaldate2tuple(b'INTERNALDATE "' + m.group(1) + b'"')))
        except Exception:
            return 0


def _reconnecting(fn):
    @wraps(fn)
    def wrapper(self: "ImapBackend", *args, **kwargs):
        with self._lock:
            for attempt in range(2):
                try:
                    self._ensure()
                    return fn(self, *args, **kwargs)
                except (imaplib.IMAP4.abort, OSError, ssl.SSLError) as exc:
                    self._drop()
                    if attempt:
                        raise MailError(f"Connexion IMAP perdue : {exc}") from exc
                except imaplib.IMAP4.error as exc:
                    raise MailError(str(exc)) from exc
    return wrapper


class ImapBackend(MailBackend):
    def __init__(self, host: str, port: int, ssl_enabled: bool, username: str, password: str):
        if not host:
            raise MailError("Serveur IMAP non configuré")
        self.host, self.port, self.ssl_enabled = host, port, ssl_enabled
        self.username, self.password = username, password
        self.conn: Optional[imaplib.IMAP4] = None
        self._selected: Optional[tuple[str, bool]] = None
        self._uidvalidity: dict[str, int] = {}
        self._folders: Optional[list[FolderInfo]] = None
        self._lock = threading.RLock()
        self.delimiter = "/"

    # -- connexion -------------------------------------------------------
    def _ensure(self) -> None:
        if self.conn is not None:
            return
        try:
            if self.ssl_enabled:
                conn = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=ssl.create_default_context(), timeout=60)
            else:
                conn = imaplib.IMAP4(self.host, self.port, timeout=60)
                if "STARTTLS" in conn.capabilities:
                    conn.starttls(ssl.create_default_context())
            conn.login(self.username, self.password)
        except imaplib.IMAP4.error as exc:
            raise MailError(f"Authentification IMAP refusée : {exc}") from exc
        except OSError as exc:
            raise MailError(f"Impossible de joindre {self.host}:{self.port} : {exc}") from exc
        self.conn = conn
        self._selected = None

    def _drop(self) -> None:
        try:
            if self.conn is not None:
                self.conn.shutdown()
        except Exception:
            pass
        self.conn = None
        self._selected = None

    def close(self) -> None:
        with self._lock:
            if self.conn is not None:
                try:
                    self.conn.logout()
                except Exception:
                    pass
            self.conn = None

    def _caps(self) -> set[str]:
        return {c.upper() for c in (self.conn.capabilities or ())}

    def _select(self, folder: str, readonly: bool = True) -> int:
        if self._selected == (folder, readonly) and folder in self._uidvalidity:
            return self._uidvalidity[folder]
        typ, data = self.conn.select(_quote(folder), readonly=readonly)
        if typ != "OK":
            raise MailError(f"Dossier inaccessible : {folder}")
        _, uv = self.conn.response("UIDVALIDITY")
        try:
            self._uidvalidity[folder] = int(uv[0]) if uv and uv[0] else 0
        except (TypeError, ValueError):
            self._uidvalidity[folder] = 0
        self._selected = (folder, readonly)
        return self._uidvalidity[folder]

    def _check(self, typ: str, data, what: str) -> None:
        if typ != "OK":
            detail = data[0].decode(errors="replace") if data and isinstance(data[0], bytes) else data
            raise MailError(f"{what} : {detail}")

    # -- lecture -----------------------------------------------------------
    @_reconnecting
    def list_folders(self) -> list[FolderInfo]:
        if self._folders is not None:
            return self._folders
        typ, data = self.conn.list()
        self._check(typ, data, "LIST")
        folders: list[FolderInfo] = []
        for item in data:
            if item is None:
                continue
            if isinstance(item, tuple):  # nom transmis en littéral
                line = item[0].decode(errors="replace")
                literal_name = item[1].decode(errors="replace")
            else:
                line, literal_name = item.decode(errors="replace"), None
            m = _LIST_RE.match(line)
            if not m:
                continue
            flags = m.group("flags").split()
            delim = m.group("delim")
            delim = "/" if delim == "NIL" else _unquote(delim)
            raw_name = literal_name if literal_name is not None else _unquote(m.group("name"))
            name = imap_utf7.decode(raw_name)
            info = FolderInfo(name=name, delimiter=delim, flags=flags)
            for flag in flags:
                if flag.lower() in SPECIAL_FLAGS:
                    info.special_use = SPECIAL_FLAGS[flag.lower()]
            if info.special_use is None:
                leaf = name.split(delim)[-1].lower() if delim else name.lower()
                for use, names in SPECIAL_NAMES.items():
                    if leaf in names:
                        info.special_use = use
            folders.append(info)
        if folders:
            self.delimiter = next((f.delimiter for f in folders if f.name.upper() != "INBOX"), folders[0].delimiter)
        folders.sort(key=lambda f: (f.name.upper() != "INBOX", f.name.lower()))
        self._folders = folders
        return folders

    @_reconnecting
    def search(self, folder, since, before, unseen=False):
        uidvalidity = self._select(folder)
        criteria: list[str] = []
        if since:
            criteria += ["SINCE", _imap_date(since)]
        if before:
            criteria += ["BEFORE", _imap_date(before)]
        if unseen:
            criteria.append("UNSEEN")
        typ, data = self.conn.uid("SEARCH", *(criteria or ["ALL"]))
        self._check(typ, data, "SEARCH")
        uids = [int(x) for x in (data[0] or b"").split()]
        return uidvalidity, uids

    @_reconnecting
    def fetch_headers(self, folder, uids):
        uidvalidity = self._select(folder)
        results: list[MailHeader] = []
        for i in range(0, len(uids), CHUNK):
            chunk = uids[i : i + CHUNK]
            query = (
                f"(UID FLAGS RFC822.SIZE INTERNALDATE BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS})] "
                f"BODY.PEEK[TEXT]<0.{SNIPPET_BYTES}>)"
            )
            typ, data = self.conn.uid("FETCH", uid_set(chunk), query)
            self._check(typ, data, "FETCH")
            for msg in group_fetch_response(data):
                uid = _meta_uid(msg["meta"])
                if uid is None:
                    continue
                results.append(self._build_header(folder, uidvalidity, uid, msg))
        return results

    def _build_header(self, folder: str, uidvalidity: int, uid: int, msg: dict) -> MailHeader:
        parsed = parse_bytes(msg["header"])
        flags = _meta_flags(msg["meta"])
        from_name, from_addr = parse_from(parsed.get("From", ""))
        internal = _meta_internaldate(msg["meta"])
        return MailHeader(
            folder=folder,
            uidvalidity=uidvalidity,
            uid=uid,
            message_id=(parsed.get("Message-ID") or "").strip(),
            subject=decode_mime(parsed.get("Subject")) or "(sans objet)",
            from_name=from_name,
            from_addr=from_addr,
            to_addrs=parse_addr_list(parsed.get("To", "")),
            cc_addrs=parse_addr_list(parsed.get("Cc", "")),
            date=parse_date(parsed.get("Date", ""), internal) or internal,
            seen="\\seen" in flags,
            flagged="\\flagged" in flags,
            answered="\\answered" in flags,
            snippet=snippet_from_partial(msg["header"], msg["text"]),
            size=_meta_size(msg["meta"]),
            has_attachments=has_attachment_hint(parsed),
            is_bulk=is_bulk(parsed, from_addr),
            in_reply_to=(parsed.get("In-Reply-To") or "").strip(),
            references=" ".join((parsed.get("References") or "").split()),
            high_importance=is_high_importance(parsed),
        )

    @_reconnecting
    def fetch_flags(self, folder, uids):
        self._select(folder)
        out: dict[int, tuple[bool, bool, bool]] = {}
        for i in range(0, len(uids), 1000):
            typ, data = self.conn.uid("FETCH", uid_set(uids[i : i + 1000]), "(UID FLAGS)")
            self._check(typ, data, "FETCH FLAGS")
            for msg in group_fetch_response(data):
                uid = _meta_uid(msg["meta"])
                if uid is not None:
                    flags = _meta_flags(msg["meta"])
                    out[uid] = ("\\seen" in flags, "\\flagged" in flags, "\\answered" in flags)
        return out

    @_reconnecting
    def fetch_dates(self, folder, min_uid):
        uidvalidity = self._select(folder)
        typ, data = self.conn.uid("FETCH", f"{max(min_uid, 1)}:*", "(UID INTERNALDATE)")
        if typ != "OK":
            return uidvalidity, []
        out = []
        for msg in group_fetch_response(data):
            uid = _meta_uid(msg["meta"])
            if uid is not None and uid >= min_uid:
                out.append((uid, _meta_internaldate(msg["meta"])))
        return uidvalidity, out

    @_reconnecting
    def fetch_body(self, folder, uid):
        self._select(folder)
        typ, data = self.conn.uid("FETCH", str(uid), "(UID BODY.PEEK[])")
        self._check(typ, data, "FETCH BODY")
        msgs = group_fetch_response(data)
        if not msgs or not msgs[0]["full"]:
            raise MailError("Message introuvable (déplacé ou supprimé ?)")
        parsed = parse_bytes(msgs[0]["full"])
        body = extract_body(parsed)
        for name in ("From", "To", "Cc", "Reply-To", "Subject", "Date", "Message-ID", "References", "In-Reply-To"):
            if parsed.get(name):
                body.headers[name] = decode_mime(parsed.get(name))
        return body

    # -- écriture ----------------------------------------------------------
    @_reconnecting
    def set_seen(self, folder, uids, seen):
        if not uids:
            return
        self._select(folder, readonly=False)
        typ, data = self.conn.uid("STORE", uid_set(uids), "+FLAGS.SILENT" if seen else "-FLAGS.SILENT", "(\\Seen)")
        self._check(typ, data, "STORE")

    @_reconnecting
    def create_folder(self, name):
        existing = {f.name for f in self.list_folders()}
        if name in existing:
            return
        parts = name.split(self.delimiter)
        for i in range(1, len(parts) + 1):  # création des parents si besoin
            path = self.delimiter.join(parts[:i])
            if path in existing:
                continue
            typ, data = self.conn.create(_quote(path))
            if typ != "OK" and b"exist" not in (data[0] or b"").lower():
                raise MailError(f"Création du dossier « {path} » impossible : {data}")
            self.conn.subscribe(_quote(path))
            existing.add(path)
        self._folders = None

    @_reconnecting
    def move(self, folder, uids, dest):
        if not uids:
            return
        self._select(folder, readonly=False)
        caps = self._caps()
        for i in range(0, len(uids), 500):
            chunk = uid_set(uids[i : i + 500])
            if "MOVE" in caps:
                typ, data = self.conn.uid("MOVE", chunk, _quote(dest))
                self._check(typ, data, "MOVE")
                continue
            typ, data = self.conn.uid("COPY", chunk, _quote(dest))
            self._check(typ, data, "COPY")
            typ, data = self.conn.uid("STORE", chunk, "+FLAGS.SILENT", "(\\Deleted)")
            self._check(typ, data, "STORE")
            if "UIDPLUS" in caps:
                self.conn.uid("EXPUNGE", chunk)
            else:
                self.conn.expunge()

    @_reconnecting
    def append(self, folder, raw, flags=""):
        typ, data = self.conn.append(_quote(folder), flags or None, imaplib.Time2Internaldate(time.time()), raw)
        self._check(typ, data, "APPEND")
