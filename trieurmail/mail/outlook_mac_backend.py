"""Pilotage d'Outlook pour Mac **classique** (« Legacy Outlook ») par AppleScript (JXA).

⚠️ Le Nouvel Outlook pour Mac ne prend pas en charge AppleScript et Microsoft a
renoncé à l'ajouter : ce mode ne fonctionne qu'avec Outlook classique. Pour le
Nouvel Outlook, utilisez le mode « Microsoft 365 » (Graph), qui lit la même boîte.

Les scripts sont écrits en JavaScript for Automation pour échanger du JSON avec
Python ; chaque appel traite des lots (50 messages) pour limiter le coût des
lancements d'osascript.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import date, datetime
from typing import Any, Optional

from .backend import MailBackend, MailError
from .models import Attachment, FolderInfo, MailBody, MailHeader
from .parsing import (
    BULK_SENDER_RE, decode_mime, html_to_text, is_bulk, is_high_importance, make_snippet, parse_addr_list, parse_bytes,
)

INBOX_NAMES = {"inbox", "boîte de réception", "boite de reception", "courrier entrant"}
SPECIAL_NAMES = {
    "drafts": {"drafts", "brouillons"},
    "sent": {"sent items", "sent", "éléments envoyés", "envoyés", "messages envoyés"},
    "trash": {"deleted items", "éléments supprimés", "corbeille", "trash"},
    "junk": {"junk email", "junk e-mail", "courrier indésirable", "spam"},
    "archive": {"archive", "archives"},
}
CHUNK = 50

JXA = r"""
const app = Application('Microsoft Outlook');
function safe(f, d) { try { const v = f(); return (v === undefined || v === null) ? d : v; } catch (e) { return d; } }
function accounts() {
  let list = [];
  for (const kind of ['exchangeAccounts', 'imapAccounts', 'popAccounts']) list = list.concat(safe(() => app[kind](), []));
  return list;
}
function walkAll() {
  const out = [];
  const walk = (items, prefix, ai) => items.forEach(f => {
    const name = safe(() => f.name(), '?');
    const path = prefix ? prefix + '/' + name : name;
    out.push({ spec: f, id: f.id(), path: path, ai: ai });
    walk(safe(() => f.mailFolders(), []), path, ai);
  });
  accounts().forEach((acc, ai) => walk(safe(() => acc.mailFolders(), []), '', ai));
  if (!out.length) walk(safe(() => app.mailFolders(), []), '', 0);
  return out;
}
function folder(id) {
  try { const f = app.mailFolders.byId(id); f.name(); return f; } catch (e) {}
  const hit = walkAll().find(x => x.id === id);
  if (!hit) throw new Error('Dossier introuvable : ' + id);
  return hit.spec;
}
function msg(id) { return app.messages.byId(id); }
function addr(r) { const e = safe(() => r.emailAddress(), {}); return e.address || ''; }
const cmds = {
  ping: () => ({ version: safe(() => app.version(), '?'), running: app.running() }),
  addresses: () => accounts().map(a => safe(() => a.emailAddress(), '')).filter(Boolean),
  folders: () => walkAll().map(x => ({ id: x.id, path: x.path, ai: x.ai })),
  search: (a) => {
    const f = folder(a.folder);
    const c = [];
    if (a.since) c.push({ timeReceived: { _greaterThanEquals: new Date(a.since) } });
    if (a.before) c.push({ timeReceived: { _lessThan: new Date(a.before) } });
    if (a.unseen) c.push({ isRead: false });
    const coll = c.length ? f.messages.whose(c.length > 1 ? { _and: c } : c[0]) : f.messages;
    const ids = coll.id(), read = coll.isRead(), flag = coll.todoFlag();
    return ids.map((id, i) => [id, read[i], String(flag[i]) === 'flagged']);
  },
  dates: (a) => {
    const f = folder(a.folder);
    const coll = a.since ? f.messages.whose({ timeReceived: { _greaterThanEquals: new Date(a.since) } }) : f.messages;
    const ids = coll.id(), dates = coll.timeReceived();
    return ids.map((id, i) => [id, dates[i] ? dates[i].getTime() : 0]);
  },
  headers: (a) => a.ids.map(id => {
    const m = msg(id);
    const s = safe(() => m.sender(), {});
    return {
      id: id, subject: safe(() => m.subject(), ''), from_name: s.name || '', from_addr: s.address || '',
      date: safe(() => m.timeReceived().getTime(), 0), read: safe(() => m.isRead(), false),
      flag: String(safe(() => m.todoFlag(), '')), replied: safe(() => m.repliedTo(), false),
      priority: String(safe(() => m.priority(), '')), headers: safe(() => m.headers(), ''),
      to: safe(() => m.toRecipients(), []).map(addr), cc: safe(() => m.ccRecipients(), []).map(addr),
      preview: String(safe(() => m.plainTextContent(), '')).slice(0, 600),
      attachments: safe(() => m.attachments.length, 0),
    };
  }),
  flags: (a) => a.ids.map(id => { const m = msg(id); return [id, safe(() => m.isRead(), false), String(safe(() => m.todoFlag(), '')) === 'flagged', safe(() => m.repliedTo(), false)]; }),
  body: (a) => {
    const m = msg(a.id);
    const s = safe(() => m.sender(), {});
    return {
      html: safe(() => m.content(), ''), text: safe(() => m.plainTextContent(), ''),
      subject: safe(() => m.subject(), ''), from: (s.name ? s.name + ' <' + s.address + '>' : (s.address || '')),
      to: safe(() => m.toRecipients(), []).map(addr).join(', '), cc: safe(() => m.ccRecipients(), []).map(addr).join(', '),
      headers: safe(() => m.headers(), ''),
      attachments: safe(() => m.attachments(), []).map(x => ({ name: safe(() => x.name(), 'pièce jointe'), size: safe(() => x.fileSize(), 0), type: safe(() => x.contentType(), '') })),
    };
  },
  seen: (a) => { a.ids.forEach(id => { msg(id).isRead = a.seen; }); return true; },
  move: (a) => { const d = folder(a.dest); a.ids.forEach(id => app.move(msg(id), { to: d })); return true; },
  create: (a) => {
    const parent = a.parent !== null ? folder(a.parent) : accounts()[a.ai || 0];
    parent.mailFolders.push(app.MailFolder({ name: a.name }));
    return parent.mailFolders.whose({ name: a.name })()[0].id();
  },
  reply: (a) => {
    const r = app.replyTo(msg(a.id), { openingWindow: false, replyToAll: false });
    r.subject = a.subject;
    const recips = (kind, list) => {
      safe(() => r[kind](), []).forEach(x => { try { app.delete(x); } catch (e) {} });
      list.forEach(ad => app.make({ new: kind === 'toRecipients' ? 'toRecipient' : 'ccRecipient', at: r, withProperties: { emailAddress: { address: ad } } }));
    };
    recips('toRecipients', a.to);
    recips('ccRecipients', a.cc);
    r.content = a.html + safe(() => r.content(), '');
    if (a.send) app.send(r);
    return a.send ? 'sent' : 'draft';
  },
};
function run(argv) {
  const req = JSON.parse(argv[0]);
  return JSON.stringify(cmds[req.cmd](req.args || {}));
}
"""


def _ms(d: Optional[date]) -> Optional[int]:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000) if d else None


def _explain(stderr: str) -> str:
    if "-1743" in stderr:
        return ("macOS refuse le pilotage d'Outlook : autorisez votre terminal dans Réglages Système → "
                "Confidentialité et sécurité → Automatisation → Microsoft Outlook.")
    if "-600" in stderr or "-10810" in stderr or "isn't running" in stderr:
        return "Outlook n'est pas lancé ou ne répond pas."
    if "-1708" in stderr or "-1728" in stderr or "Can't get" in stderr or "Impossible d" in stderr:
        return ("Outlook ne répond pas aux commandes AppleScript. Le Nouvel Outlook pour Mac ne les prend pas "
                "en charge : utilisez le mode « Microsoft 365 », ou repassez en Outlook classique.")
    return stderr.strip().splitlines()[-1][:300] if stderr.strip() else "Erreur AppleScript inconnue"


class OutlookMacBackend(MailBackend):
    def __init__(self, runner=None):
        if runner is None and sys.platform != "darwin":
            raise MailError("Le pilotage d'Outlook n'est disponible que sur macOS.")
        self._runner = runner or self._osascript
        self._lock = threading.RLock()
        self._folders: Optional[list[FolderInfo]] = None
        self._ids: dict[str, int] = {}
        self._flags: dict[tuple[str, Any], tuple[bool, bool]] = {}
        self._addresses: Optional[list[str]] = None
        self.delimiter = "/"

    @staticmethod
    def _osascript(payload: str) -> str:
        try:
            proc = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA, payload],
                                  capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired as exc:
            raise MailError("Outlook met trop de temps à répondre.") from exc
        except FileNotFoundError as exc:
            raise MailError("osascript introuvable (macOS requis).") from exc
        if proc.returncode != 0:
            raise MailError(_explain(proc.stderr))
        return proc.stdout

    def _call(self, cmd: str, **args) -> Any:
        out = self._runner(json.dumps({"cmd": cmd, "args": args}))
        try:
            return json.loads(out)
        except ValueError as exc:
            raise MailError(f"Réponse d'Outlook illisible : {out[:200]}") from exc

    # -- dossiers -----------------------------------------------------------
    def list_folders(self):
        with self._lock:
            if self._folders is not None:
                return self._folders
            raw = self._call("folders")
            if not raw:
                raise MailError(_explain("Can't get"))
            multi = len({f["ai"] for f in raw}) > 1
            inbox_prefix: Optional[str] = None
            folders, ids = [], {}
            for f in raw:
                parts = f["path"].split("/")
                if inbox_prefix is None and f["ai"] == 0 and len(parts) == 1 and parts[0].lower() in INBOX_NAMES:
                    inbox_prefix = f["path"]
                if inbox_prefix and f["ai"] == 0 and (f["path"] == inbox_prefix or f["path"].startswith(inbox_prefix + "/")):
                    path = "INBOX" + f["path"][len(inbox_prefix):]
                elif multi:
                    path = f"Compte {f['ai'] + 1}/{f['path']}"
                else:
                    path = f["path"]
                special = next((use for use, names in SPECIAL_NAMES.items() if parts[-1].lower() in names and len(parts) == 1), None)
                ids[path] = f["id"]
                folders.append(FolderInfo(path, "/", [], special))
            folders.sort(key=lambda x: (x.name != "INBOX", not x.name.startswith("INBOX"), x.name.lower()))
            self._folders, self._ids = folders, ids
            return folders

    def _fid(self, folder: str) -> int:
        self.list_folders()
        if folder not in self._ids:
            raise MailError(f"Dossier inconnu : {folder}")
        return self._ids[folder]

    def create_folder(self, name):
        with self._lock:
            self.list_folders()
            parts = name.split("/")
            for i in range(1, len(parts) + 1):
                path = "/".join(parts[:i])
                if path in self._ids:
                    continue
                parent = "/".join(parts[: i - 1])
                new_id = self._call("create", parent=self._ids[parent] if parent else None, ai=0, name=parts[i - 1])
                self._ids[path] = new_id
                self._folders.append(FolderInfo(path, "/", [], None))

    # -- lecture ------------------------------------------------------------
    def search(self, folder, since, before, unseen=False):
        rows = self._call("search", folder=self._fid(folder), since=_ms(since), before=_ms(before), unseen=unseen)
        with self._lock:
            for uid, read, flagged in rows:
                self._flags[(folder, uid)] = (bool(read), bool(flagged))
        return 1, [r[0] for r in rows]

    def fetch_headers(self, folder, uids):
        out = []
        for i in range(0, len(uids), CHUNK):
            for m in self._call("headers", ids=uids[i : i + CHUNK]):
                parsed = parse_bytes(m["headers"].encode("utf-8", "replace")) if m["headers"] else None
                from_addr = (m["from_addr"] or "").lower()
                out.append(MailHeader(
                    folder=folder, uidvalidity=1, uid=m["id"],
                    message_id=(parsed.get("Message-ID", "") if parsed else "").strip() or f"outlook-{m['id']}",
                    subject=m["subject"] or "(sans objet)", from_name=m["from_name"], from_addr=from_addr,
                    to_addrs=",".join(a.lower() for a in m["to"] if a) or (parse_addr_list(parsed.get("To", "")) if parsed else ""),
                    cc_addrs=",".join(a.lower() for a in m["cc"] if a),
                    date=int(m["date"] / 1000), seen=bool(m["read"]), flagged=m["flag"] == "flagged",
                    answered=bool(m["replied"]), snippet=make_snippet(m["preview"]),
                    has_attachments=bool(m["attachments"]),
                    is_bulk=is_bulk(parsed, from_addr) if parsed else bool(BULK_SENDER_RE.search(from_addr)),
                    in_reply_to=(parsed.get("In-Reply-To", "") if parsed else "").strip(),
                    references=" ".join((parsed.get("References", "") if parsed else "").split()),
                    high_importance="high" in m["priority"] or (is_high_importance(parsed) if parsed else False),
                ))
        return out

    def fetch_flags(self, folder, uids):
        with self._lock:
            known = {u: (*self._flags[(folder, u)], None) for u in uids if (folder, u) in self._flags}
        missing = [u for u in uids if u not in known]
        for i in range(0, len(missing), CHUNK * 4):
            for uid, read, flagged, replied in self._call("flags", ids=missing[i : i + CHUNK * 4]):
                known[uid] = (bool(read), bool(flagged), bool(replied))
        return known

    def fetch_dates(self, folder, min_uid, since_ts=0):
        rows = self._call("dates", folder=self._fid(folder), since=(since_ts - 1) * 1000 if since_ts else None)
        return 1, [(uid, int(ms / 1000)) for uid, ms in rows]

    def fetch_body(self, folder, uid):
        m = self._call("body", id=uid)
        parsed = parse_bytes(m["headers"].encode("utf-8", "replace")) if m["headers"] else None
        text = m["text"] or (html_to_text(m["html"]) if m["html"] else "")
        headers = {"From": m["from"], "To": m["to"], "Cc": m["cc"], "Subject": m["subject"]}
        if parsed is not None:
            for name in ("Reply-To", "Message-ID", "References", "Date"):
                if parsed.get(name):
                    headers[name] = decode_mime(parsed.get(name))
        return MailBody(
            text=text, html=m["html"] or "",
            attachments=[Attachment(a["name"], a["type"], int(a["size"] or 0)) for a in m["attachments"]],
            headers={k: v for k, v in headers.items() if v},
        )

    # -- écriture -----------------------------------------------------------
    def set_seen(self, folder, uids, seen):
        for i in range(0, len(uids), CHUNK * 4):
            self._call("seen", ids=uids[i : i + CHUNK * 4], seen=seen)

    def move(self, folder, uids, dest):
        dest_id = self._fid(dest)
        for i in range(0, len(uids), CHUNK * 2):
            self._call("move", ids=uids[i : i + CHUNK * 2], dest=dest_id)

    def append(self, folder, raw, flags=""):
        raise MailError("Outlook classique : utilisez la réponse native (brouillon créé par Outlook).")

    def reply_draft(self, folder, uid, *, to, cc, subject, body, send):
        import html as html_lib
        from email.utils import getaddresses

        status = self._call(
            "reply", id=uid, subject=subject, send=send,
            to=[a for _, a in getaddresses([to]) if a], cc=[a for _, a in getaddresses([cc]) if a],
            html="<div>" + html_lib.escape(body).replace("\n", "<br>") + "</div><br>",
        )
        return {"status": status, "folder": self.special_folder("drafts") or "Brouillons"}

    def account_addresses(self):
        if self._addresses is None:
            try:
                self._addresses = [a.lower() for a in self._call("addresses")]
            except MailError:
                self._addresses = []
        return self._addresses
