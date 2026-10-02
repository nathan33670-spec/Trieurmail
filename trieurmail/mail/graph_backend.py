"""Backend Microsoft 365 / Exchange Online via Microsoft Graph.

Fonctionne avec le Nouvel Outlook pour Mac : on lit la même boîte que lui, par
l'API officielle, avec votre propre connexion (aucun accès serveur ni IMAP requis).

Optimisations :
- identifiants immuables (``Prefer: IdType="ImmutableId"``) : un email garde son
  identifiant après déplacement, le cache reste valide ;
- recherche par période en ne demandant que id / lu / drapeau (pages de 500),
  ce qui sert aussi au rafraîchissement des drapeaux sans requête supplémentaire ;
- en-têtes des seuls nouveaux emails via ``$batch`` (20 requêtes par appel HTTP) ;
- déplacements, marquage lu/non lu groupés par ``$batch`` ;
- respect de ``Retry-After`` en cas de limitation (429 / 503).
"""
from __future__ import annotations

import base64
import threading
import time
from datetime import date, datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx

from .backend import MailBackend, MailError
from .graph_auth import GraphAuth
from .models import Attachment, FolderInfo, MailBody, MailHeader, Uid
from .parsing import BULK_SENDER_RE, html_to_text

GRAPH = "https://graph.microsoft.com/v1.0"
PREFER = 'IdType="ImmutableId"'
WELL_KNOWN = {"drafts": "drafts", "sentitems": "sent", "deleteditems": "trash", "junkemail": "junk", "archive": "archive"}
HEADER_SELECT = (
    "id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,flag,hasAttachments,importance,"
    "internetMessageId,conversationId,conversationIndex,bodyPreview,inferenceClassification"
)
# PidTagLastVerbExecuted : 102 = répondu, 103 = répondu à tous, 104 = transféré
LAST_VERB = "Integer 0x1081"
PAGE = 500


def _iso(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(value: str) -> int:
    if not value:
        return 0
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def _addr(obj: Optional[dict]) -> tuple[str, str]:
    ea = (obj or {}).get("emailAddress") or {}
    return (ea.get("name") or "").strip(), (ea.get("address") or "").strip().lower()


def _addr_list(items: Optional[list]) -> str:
    return ",".join(a for _, a in (_addr(r) for r in items or []) if a)


def _recipients(value: str) -> list[dict]:
    from email.utils import getaddresses

    return [{"emailAddress": {"address": a, "name": n or a}} for n, a in getaddresses([value]) if a]


class GraphBackend(MailBackend):
    def __init__(self, auth: GraphAuth, transport: Optional[httpx.BaseTransport] = None):
        self.auth = auth
        self.delimiter = "/"
        self._http = httpx.Client(base_url=GRAPH, timeout=60, transport=transport)
        self._lock = threading.RLock()
        self._folders: Optional[list[FolderInfo]] = None
        self._ids: dict[str, str] = {}  # chemin -> id Graph
        self._flags: dict[tuple[str, str], tuple[bool, bool]] = {}  # (dossier, id) -> (lu, suivi)

    # -- HTTP ---------------------------------------------------------------
    def _request(self, method: str, url: str, **kw) -> Any:
        headers = kw.pop("headers", {})
        refreshed = False
        for attempt in range(5):
            headers.update(Authorization=f"Bearer {self.auth.access_token(force_refresh=refreshed)}", Prefer=PREFER)
            try:
                resp = self._http.request(method, url, headers=headers, **kw)
            except httpx.HTTPError as exc:
                if attempt == 4:
                    raise MailError(f"Microsoft 365 injoignable : {exc}") from exc
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 401 and not refreshed:
                refreshed = True  # jeton révoqué ou expiré : un seul rafraîchissement forcé
                continue
            if resp.status_code in (429, 503, 504):
                time.sleep(min(30, float(resp.headers.get("Retry-After", 2 ** attempt))))
                continue
            if resp.status_code >= 400:
                try:
                    err = resp.json().get("error", {})
                    msg = f"{err.get('code')}: {err.get('message')}"
                except ValueError:
                    msg = resp.text[:300]
                raise MailError(f"Microsoft 365 ({resp.status_code}) {msg}")
            if resp.status_code in (202, 204) or not resp.content:
                return None
            return resp.json()
        raise MailError("Microsoft 365 : trop de requêtes, réessayez dans un instant.")

    def _pages(self, url: str, params: Optional[dict] = None) -> list[dict]:
        out: list[dict] = []
        data = self._request("GET", url, params=params)
        while True:
            out.extend(data.get("value", []))
            nxt = data.get("@odata.nextLink")
            if not nxt:
                return out
            data = self._request("GET", nxt)

    def _batch(self, requests: list[dict]) -> list[dict]:
        """Exécute des sous-requêtes par paquets de 20 ; retourne les réponses dans l'ordre."""
        results: dict[int, dict] = {}
        pending = list(enumerate(requests))
        for _ in range(6):
            if not pending:
                break
            retry: list[tuple[int, dict]] = []
            wait = 0.0
            for i in range(0, len(pending), 20):
                chunk = pending[i : i + 20]
                payload = {"requests": [
                    {"id": str(idx), "method": r["method"], "url": r["url"],
                     "headers": {"Prefer": PREFER, **({"Content-Type": "application/json"} if "body" in r else {})},
                     **({"body": r["body"]} if "body" in r else {})}
                    for idx, r in chunk
                ]}
                data = self._request("POST", "/$batch", json=payload)
                for resp in data.get("responses", []):
                    idx = int(resp["id"])
                    if resp.get("status") in (429, 503):
                        retry.append((idx, requests[idx]))
                        wait = max(wait, float((resp.get("headers") or {}).get("Retry-After", 2)))
                    else:
                        results[idx] = resp
            pending = retry
            if pending:
                time.sleep(min(30, wait))
        for idx, _ in pending:
            results[idx] = {"status": 429, "body": {"error": {"message": "limitation persistante"}}}
        return [results[i] for i in range(len(requests))]

    @staticmethod
    def _raise_failures(responses: list[dict], what: str) -> None:
        failed = [r for r in responses if r.get("status", 500) >= 400]
        if failed:
            msg = ((failed[0].get("body") or {}).get("error") or {}).get("message", "")
            raise MailError(f"{what} : {len(failed)} échec(s). {msg}")

    # -- dossiers -----------------------------------------------------------
    def list_folders(self) -> list[FolderInfo]:
        with self._lock:
            if self._folders is not None:
                return self._folders
            select = {"$select": "id,displayName,childFolderCount", "$top": "250"}
            reqs = [{"method": "GET", "url": f"/me/mailFolders/{wk}?$select=id"} for wk in ("inbox", *WELL_KNOWN)]
            special: dict[str, str] = {}
            inbox_id = ""
            for wk, resp in zip(("inbox", *WELL_KNOWN), self._batch(reqs)):
                if resp.get("status") == 200:
                    fid = resp["body"]["id"]
                    if wk == "inbox":
                        inbox_id = fid
                    else:
                        special[fid] = WELL_KNOWN[wk]
            folders: list[FolderInfo] = []
            ids: dict[str, str] = {}

            def walk(items: list[dict], prefix: str) -> None:
                for f in items:
                    name = (f.get("displayName") or "?").replace("/", "∕")
                    path = "INBOX" if f["id"] == inbox_id else (f"{prefix}/{name}" if prefix else name)
                    ids[path] = f["id"]
                    folders.append(FolderInfo(path, "/", [], special.get(f["id"])))
                    if f.get("childFolderCount"):
                        walk(self._pages(f"/me/mailFolders/{f['id']}/childFolders", select), path)

            walk(self._pages("/me/mailFolders", select), "")
            folders.sort(key=lambda f: (f.name != "INBOX", not f.name.startswith("INBOX"), f.name.lower()))
            self._folders, self._ids = folders, ids
            return folders

    def _folder_id(self, folder: str) -> str:
        self.list_folders()
        if folder not in self._ids:
            raise MailError(f"Dossier inconnu : {folder}")
        return self._ids[folder]

    def create_folder(self, name: str) -> None:
        with self._lock:
            self.list_folders()
            parts = name.split("/")
            for i in range(1, len(parts) + 1):
                path = "/".join(parts[:i])
                if path in self._ids:
                    continue
                parent = "/".join(parts[: i - 1])
                url = f"/me/mailFolders/{self._ids[parent]}/childFolders" if parent else "/me/mailFolders"
                created = self._request("POST", url, json={"displayName": parts[i - 1]})
                self._ids[path] = created["id"]
                self._folders.append(FolderInfo(path, "/", [], None))

    # -- lecture ------------------------------------------------------------
    def search(self, folder, since, before, unseen=False):
        fid = self._folder_id(folder)
        filters = []
        if since:
            filters.append(f"receivedDateTime ge {_iso(since)}")
        if before:
            filters.append(f"receivedDateTime lt {_iso(before)}")
        if unseen:
            filters.append("isRead eq false")
        params = {"$select": "id,isRead,flag", "$top": str(PAGE)}
        if filters:
            params["$filter"] = " and ".join(filters)
        items = self._pages(f"/me/mailFolders/{fid}/messages", params)
        with self._lock:
            for m in items:
                self._flags[(folder, m["id"])] = (bool(m.get("isRead")), (m.get("flag") or {}).get("flagStatus") == "flagged")
        return 1, [m["id"] for m in items]

    def fetch_headers(self, folder, uids):
        expand = quote(f"singleValueExtendedProperties($filter=id eq '{LAST_VERB}')", safe="()$=',")
        reqs = [{"method": "GET", "url": f"/me/messages/{uid}?$select={HEADER_SELECT}&$expand={expand}"} for uid in uids]
        out = []
        for resp in self._batch(reqs):
            if resp.get("status") == 200:
                out.append(self._to_header(folder, resp["body"]))
        return out

    def _to_header(self, folder: str, m: dict) -> MailHeader:
        from_name, from_addr = _addr(m.get("from"))
        verbs = [p.get("value") for p in m.get("singleValueExtendedProperties") or [] if p.get("id", "").lower() == LAST_VERB.lower()]
        try:
            in_thread = len(base64.b64decode(m.get("conversationIndex") or "")) > 22
        except ValueError:
            in_thread = False
        return MailHeader(
            folder=folder, uidvalidity=1, uid=m["id"],
            message_id=m.get("internetMessageId") or m["id"],
            subject=m.get("subject") or "(sans objet)",
            from_name=from_name, from_addr=from_addr,
            to_addrs=_addr_list(m.get("toRecipients")), cc_addrs=_addr_list(m.get("ccRecipients")),
            date=_ts(m.get("receivedDateTime", "")),
            seen=bool(m.get("isRead")),
            flagged=(m.get("flag") or {}).get("flagStatus") == "flagged",
            answered=any(str(v) in ("102", "103") for v in verbs),
            snippet=" ".join((m.get("bodyPreview") or "").split())[:240],
            has_attachments=bool(m.get("hasAttachments")),
            # « Autres » de la boîte de réception Prioritaire = envoi de masse le plus souvent
            is_bulk=m.get("inferenceClassification") == "other" or bool(BULK_SENDER_RE.search(from_addr)),
            in_reply_to=(m.get("conversationId") or "") if in_thread else "",
            references=m.get("conversationId") or "",
            high_importance=m.get("importance") == "high",
        )

    def fetch_flags(self, folder, uids):
        with self._lock:
            known = {u: self._flags[(folder, u)] for u in uids if (folder, u) in self._flags}
        missing = [u for u in uids if u not in known]
        if missing:
            reqs = [{"method": "GET", "url": f"/me/messages/{u}?$select=isRead,flag"} for u in missing]
            for u, resp in zip(missing, self._batch(reqs)):
                if resp.get("status") == 200:
                    b = resp["body"]
                    known[u] = (bool(b.get("isRead")), (b.get("flag") or {}).get("flagStatus") == "flagged")
        return {u: (s, f, None) for u, (s, f) in known.items()}

    def fetch_dates(self, folder, min_uid, since_ts=0):
        fid = self._folder_id(folder)
        params = {"$select": "receivedDateTime", "$top": "1000"}
        if since_ts:
            start = datetime.fromtimestamp(max(0, since_ts - 1), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            params["$filter"] = f"receivedDateTime ge {start}"
        items = self._pages(f"/me/mailFolders/{fid}/messages", params)
        return 1, [(m["id"], _ts(m.get("receivedDateTime", ""))) for m in items]

    def fetch_body(self, folder, uid):
        m = self._request("GET", f"/me/messages/{uid}", params={
            "$select": "subject,body,from,toRecipients,ccRecipients,replyTo,receivedDateTime,internetMessageId,hasAttachments",
        })
        body = MailBody()
        content = (m.get("body") or {}).get("content") or ""
        if (m.get("body") or {}).get("contentType") == "html":
            body.html, body.text = content, html_to_text(content)
        else:
            body.text = content
        if m.get("hasAttachments"):
            atts = self._pages(f"/me/messages/{uid}/attachments", {"$select": "name,contentType,size,isInline"})
            body.attachments = [Attachment(a.get("name") or "pièce jointe", a.get("contentType") or "", int(a.get("size") or 0))
                                for a in atts if not a.get("isInline")]
        fmt = lambda o: f"{o[0]} <{o[1]}>" if o[0] else o[1]  # noqa: E731
        body.headers = {
            "From": fmt(_addr(m.get("from"))),
            "To": ", ".join(fmt(_addr(r)) for r in m.get("toRecipients") or []),
            "Cc": ", ".join(fmt(_addr(r)) for r in m.get("ccRecipients") or []),
            "Subject": m.get("subject") or "",
            "Date": m.get("receivedDateTime", ""),
            "Message-ID": m.get("internetMessageId", ""),
        }
        if m.get("replyTo"):
            body.headers["Reply-To"] = ", ".join(fmt(_addr(r)) for r in m["replyTo"])
        body.headers = {k: v for k, v in body.headers.items() if v}
        return body

    # -- écriture -----------------------------------------------------------
    def set_seen(self, folder, uids, seen):
        reqs = [{"method": "PATCH", "url": f"/me/messages/{u}", "body": {"isRead": seen}} for u in uids]
        self._raise_failures(self._batch(reqs), "Marquage lu/non lu")
        with self._lock:
            for u in uids:
                flagged = self._flags.get((folder, u), (seen, False))[1]
                self._flags[(folder, u)] = (seen, flagged)

    def move(self, folder, uids, dest):
        dest_id = self._folder_id(dest)
        reqs = [{"method": "POST", "url": f"/me/messages/{u}/move", "body": {"destinationId": dest_id}} for u in uids]
        self._raise_failures(self._batch(reqs), f"Déplacement vers « {dest} »")

    def append(self, folder, raw, flags=""):
        """Crée un message à partir de sa source MIME (brouillon)."""
        fid = self._folder_id(folder)
        self._request("POST", f"/me/mailFolders/{fid}/messages", content=base64.b64encode(raw),
                      headers={"Content-Type": "text/plain"})

    def reply_draft(self, folder, uid, *, to, cc, subject, body, send):
        """Réponse native Outlook : le fil de discussion et l'historique cité sont conservés."""
        draft = self._request("POST", f"/me/messages/{uid}/createReply", json={})
        quoted = (draft.get("body") or {}).get("content") or ""
        import html as html_lib

        mine = "<div>" + html_lib.escape(body).replace("\n", "<br>") + "</div><br>"
        patch = {
            "subject": subject,
            "toRecipients": _recipients(to),
            "ccRecipients": _recipients(cc),
            "body": {"contentType": "html", "content": mine + quoted},
        }
        self._request("PATCH", f"/me/messages/{draft['id']}", json=patch)
        if send:
            self._request("POST", f"/me/messages/{draft['id']}/send")
            return {"status": "sent"}
        return {"status": "draft", "folder": self.special_folder("drafts") or "Brouillons"}

    def account_addresses(self) -> list[str]:
        return [self.auth.account.lower()] if self.auth.account else []

    def close(self) -> None:
        self._http.close()
