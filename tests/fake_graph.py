"""Faux Microsoft Graph + Entra ID en mémoire (httpx.MockTransport) pour les tests."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx

WELL_KNOWN = {"inbox": "F-INBOX", "drafts": "F-DRAFTS", "sentitems": "F-SENT", "deleteditems": "F-TRASH",
              "junkemail": "F-JUNK"}


def _id_token(email: str, name: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"preferred_username": email, "name": name}).encode()).decode().rstrip("=")
    return f"x.{body}.y"


class FakeGraph:
    def __init__(self) -> None:
        self.token_polls = 0
        self.requests: list[tuple[str, str]] = []
        self.throttled_once = False
        self.folders = {
            "F-INBOX": {"displayName": "Boîte de réception", "parent": None},
            "F-DRAFTS": {"displayName": "Brouillons", "parent": None},
            "F-SENT": {"displayName": "Éléments envoyés", "parent": None},
            "F-TRASH": {"displayName": "Éléments supprimés", "parent": None},
            "F-JUNK": {"displayName": "Courrier indésirable", "parent": None},
            "F-CLIENTS": {"displayName": "Clients", "parent": "F-INBOX"},
        }
        now = datetime.now(timezone.utc)
        self.messages: dict[str, dict] = {}
        senders = [("Sophie Bernard", "sophie@acme.fr", "focused", "URGENT : valider le budget avant vendredi"),
                   ("Newsletter", "news@shop.fr", "other", "Promo -30 %"),
                   ("EDF", "noreply@edf.fr", "other", "Votre facture"),
                   ("Client A", "contact@client-a.fr", "focused", "Question sur le devis")]
        for i in range(24):
            name, addr, cls, subject = senders[i % 4]
            mid = f"AAMkImmutable{i:03d}=="
            self.messages[mid] = {
                "id": mid, "folder": "F-CLIENTS" if i == 23 else "F-INBOX", "subject": subject,
                "from": {"emailAddress": {"name": name, "address": addr}},
                "toRecipients": [{"emailAddress": {"name": "Moi", "address": "moi@entreprise.fr"}}],
                "ccRecipients": [], "receivedDateTime": (now - timedelta(days=i * 3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "isRead": i % 3 != 0, "flag": {"flagStatus": "notFlagged"}, "hasAttachments": i == 0,
                "importance": "high" if i == 0 else "normal", "internetMessageId": f"<m{i}@x>",
                "conversationId": f"conv{i}", "conversationIndex": base64.b64encode(b"x" * (27 if i == 0 else 22)).decode(),
                "bodyPreview": f"Bonjour, {subject.lower()} — merci de votre retour.",
                "inferenceClassification": cls,
                "body": {"contentType": "html", "content": f"<p>Bonjour,</p><p>{subject}</p>"},
                "singleValueExtendedProperties": [{"id": "Integer 0x1081", "value": "102"}] if i == 4 else [],
            }

    # -- utilitaires -------------------------------------------------------
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def _folder_id(self, ref: str) -> str:
        return WELL_KNOWN.get(ref.lower(), ref)

    def _folder_json(self, fid: str) -> dict:
        f = self.folders[fid]
        kids = sum(1 for x in self.folders.values() if x["parent"] == fid)
        return {"id": fid, "displayName": f["displayName"], "childFolderCount": kids}

    @staticmethod
    def _json(status: int, data=None, headers=None) -> httpx.Response:
        return httpx.Response(status, json=data, headers=headers) if data is not None else httpx.Response(status, headers=headers)

    # -- routeur -----------------------------------------------------------
    def handle(self, request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        if url.netloc == "login.microsoftonline.com":
            return self.login(url.path, parse_qs(request.content.decode()))
        assert request.headers.get("Authorization") == "Bearer AT-1", "jeton manquant"
        if url.path.endswith("/$batch"):
            return self.batch(json.loads(request.content))
        assert request.headers.get("Prefer") == 'IdType="ImmutableId"'
        body = request.content
        status, data = self.route(request.method, url.path.replace("/v1.0", ""), parse_qs(url.query), body,
                                  request.headers.get("Content-Type", ""))
        return self._json(status, data)

    def login(self, path: str, form: dict) -> httpx.Response:
        if path.endswith("/devicecode"):
            return self._json(200, {"device_code": "DC", "user_code": "ABCD-1234", "interval": 0, "expires_in": 900,
                                    "verification_uri": "https://microsoft.com/devicelogin"})
        grant = form["grant_type"][0]
        if grant.endswith("device_code"):
            self.token_polls += 1
            if self.token_polls == 1:
                return self._json(400, {"error": "authorization_pending"})
        return self._json(200, {"access_token": "AT-1", "refresh_token": "RT-1", "expires_in": 3600,
                                "id_token": _id_token("moi@entreprise.fr", "Moi Même")})

    def batch(self, payload: dict) -> httpx.Response:
        assert len(payload["requests"]) <= 20
        responses = []
        for r in payload["requests"]:
            assert r["headers"]["Prefer"] == 'IdType="ImmutableId"'
            if not self.throttled_once and r["method"] == "GET" and "/me/messages/" in r["url"]:
                self.throttled_once = True
                responses.append({"id": r["id"], "status": 429, "headers": {"Retry-After": "0"}, "body": {}})
                continue
            u = urlparse(r["url"])
            status, data = self.route(r["method"], u.path, parse_qs(u.query), json.dumps(r.get("body", {})).encode(),
                                      "application/json")
            responses.append({"id": r["id"], "status": status, "body": data or {}})
        return self._json(200, {"responses": responses})

    def route(self, method: str, path: str, query: dict, body: bytes, ctype: str):
        self.requests.append((method, path))
        parts = [p for p in path.split("/") if p][1:]  # sans "me"
        if parts[0] == "mailFolders":
            if len(parts) == 1:
                if method == "POST":
                    return self._create_folder(None, json.loads(body))
                return 200, {"value": [self._folder_json(f) for f, v in self.folders.items() if v["parent"] is None]}
            fid = self._folder_id(parts[1])
            if fid not in self.folders:
                return 404, {"error": {"code": "ErrorItemNotFound", "message": "absent"}}
            if len(parts) == 2:
                return 200, self._folder_json(fid)
            if parts[2] == "childFolders":
                if method == "POST":
                    return self._create_folder(fid, json.loads(body))
                return 200, {"value": [self._folder_json(f) for f, v in self.folders.items() if v["parent"] == fid]}
            if parts[2] == "messages" and method == "POST":
                assert ctype.startswith("text/plain") and base64.b64decode(body).startswith(b"From")
                mid = f"MIME{len(self.messages)}"
                self.messages[mid] = {"id": mid, "folder": fid, "subject": "mime"}
                return 201, {"id": mid}
            if parts[2] == "messages":
                return 200, self._list(fid, query)
        if parts[0] == "messages":
            mid = parts[1]
            m = self.messages.get(mid)
            if m is None:
                return 404, {"error": {"code": "ErrorItemNotFound", "message": "absent"}}
            if len(parts) == 2 and method == "GET":
                return 200, {k: v for k, v in m.items() if k != "folder"}
            if len(parts) == 2 and method == "PATCH":
                m.update(json.loads(body))
                return 200, {"id": mid}
            action = parts[2]
            if action == "move":
                m["folder"] = json.loads(body)["destinationId"]
                return 201, {"id": mid}
            if action == "attachments":
                return 200, {"value": [{"name": "devis.pdf", "contentType": "application/pdf", "size": 2048, "isInline": False}]}
            if action == "createReply":
                did = f"DRAFT-{mid}"
                self.messages[did] = {"id": did, "folder": "F-DRAFTS", "subject": "RE: " + m["subject"],
                                      "body": {"contentType": "html", "content": "<hr><p>message d'origine</p>"}}
                return 201, {"id": did, "body": self.messages[did]["body"]}
            if action == "send":
                m["folder"] = "F-SENT"
                return 202, None
        return 400, {"error": {"code": "BadRequest", "message": f"route inconnue {method} {path}"}}

    def _create_folder(self, parent, data):
        fid = f"F-{data['displayName'].upper()}-{len(self.folders)}"
        self.folders[fid] = {"displayName": data["displayName"], "parent": parent}
        return 201, {"id": fid, "displayName": data["displayName"]}

    def _list(self, fid: str, query: dict) -> dict:
        items = [m for m in self.messages.values() if m["folder"] == fid]
        flt = query.get("$filter", [""])[0]
        for op, value in re.findall(r"receivedDateTime (ge|lt) (\S+)", flt):
            items = [m for m in items if (m["receivedDateTime"] >= value if op == "ge" else m["receivedDateTime"] < value)]
        if "isRead eq false" in flt:
            items = [m for m in items if not m["isRead"]]
        top = int(query.get("$top", ["10"])[0])
        skip = int(query.get("$skip", ["0"])[0])
        fields = query.get("$select", [""])[0].split(",")
        page = [{k: m.get(k) for k in ["id", *fields] if k} for m in items[skip : skip + top]]
        out = {"value": page}
        if skip + top < len(items):
            q = "&".join(f"{k}={v[0]}" for k, v in query.items() if k != "$skip")
            out["@odata.nextLink"] = f"https://graph.microsoft.com/v1.0/me/mailFolders/{fid}/messages?{q}&$skip={skip + top}"
        return out
