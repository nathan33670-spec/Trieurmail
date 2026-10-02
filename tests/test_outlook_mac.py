"""Backend Outlook classique testé avec un faux Outlook (réponses JSON du script JXA)."""
import json

import pytest

from trieurmail.mail.backend import MailError
from trieurmail.mail.outlook_mac_backend import OutlookMacBackend, _explain

HEADERS = "Message-ID: <x1@acme.fr>\r\nList-Unsubscribe: <mailto:u@x>\r\nTo: moi@ent.fr\r\n"


class FakeOutlook:
    def __init__(self):
        self.calls = []

    def __call__(self, payload):
        req = json.loads(payload)
        self.calls.append(req)
        cmd, a = req["cmd"], req["args"]
        out = {
            "folders": [
                {"id": 10, "path": "Inbox", "ai": 0}, {"id": 11, "path": "Inbox/Projets", "ai": 0},
                {"id": 12, "path": "Drafts", "ai": 0}, {"id": 13, "path": "Sent Items", "ai": 0},
            ],
            "search": [[501, False, True], [502, True, False]],
            "headers": [{"id": i, "subject": "Facture", "from_name": "EDF", "from_addr": "NoReply@edf.fr",
                         "date": 1_790_000_000_000, "read": False, "flag": "flagged", "replied": False,
                         "priority": "priority high", "headers": HEADERS, "to": ["moi@ent.fr"], "cc": [],
                         "preview": "Votre facture est disponible", "attachments": 1} for i in a.get("ids", [])],
            "create": 99, "move": True, "reply": "draft", "addresses": ["Moi@Ent.fr"],
        }.get(cmd)
        return json.dumps(out)


def test_outlook_mac_backend_mapping():
    fake = FakeOutlook()
    b = OutlookMacBackend(runner=fake)
    folders = {f.name: f for f in b.list_folders()}
    assert set(folders) == {"INBOX", "INBOX/Projets", "Drafts", "Sent Items"}
    assert folders["Drafts"].special_use == "drafts" and folders["Sent Items"].special_use == "sent"
    uv, uids = b.search("INBOX", None, None)
    assert uids == [501, 502]
    assert b.fetch_flags("INBOX", [501]) == {501: (False, True, None)}
    [h] = b.fetch_headers("INBOX", [501])
    assert h.from_addr == "noreply@edf.fr" and h.is_bulk and h.flagged and h.high_importance
    assert h.message_id == "<x1@acme.fr>" and h.date == 1_790_000_000
    b.create_folder("Finances/Factures")
    assert [c["args"]["name"] for c in fake.calls if c["cmd"] == "create"] == ["Finances", "Factures"]
    b.move("INBOX", [501], "Finances/Factures")
    assert fake.calls[-1] == {"cmd": "move", "args": {"ids": [501], "dest": 99}}
    r = b.reply_draft("INBOX", 501, to="Sophie <s@a.fr>", cc="", subject="RE: x", body="Oui\nmerci", send=False)
    assert r == {"status": "draft", "folder": "Drafts"}
    assert fake.calls[-1]["args"]["html"].startswith("<div>Oui<br>merci</div>")
    assert b.account_addresses() == ["moi@ent.fr"]


def test_outlook_errors_are_explained():
    assert "Automatisation" in _explain("execution error: Not authorized to send Apple events (-1743)")
    assert "Nouvel Outlook" in _explain("Error: Can't get object. (-1728)")
    with pytest.raises(MailError):
        OutlookMacBackend(runner=lambda p: "[]").list_folders()
