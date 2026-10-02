"""Backend IMAP testé contre une fausse connexion imaplib (réponses brutes réalistes)."""
from trieurmail.mail.imap_backend import ImapBackend

HEADER = (
    b"From: =?utf-8?q?Sophie_B=C3=A9rnard?= <Sophie@Acme.fr>\r\nTo: moi@exemple.fr\r\n"
    b"Subject: =?utf-8?b?UsOpdW5pb24gZGVtYWlu?=\r\nDate: Tue, 29 Sep 2026 10:00:00 +0200\r\n"
    b"Message-ID: <abc@acme.fr>\r\nList-Unsubscribe: <mailto:x@y>\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
)


class FakeConn:
    capabilities = ("IMAP4REV1", "MOVE")

    def __init__(self):
        self.calls = []

    def list(self):
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Drafts) "/" "Brouillons"',
            b'(\\HasNoChildren) "/" "Envoy&AOk-s"',
            (b'(\\HasNoChildren) "/" {12}', b"Dossier fou"),
            b'(\\Noselect \\HasChildren) "/" "[Gmail]"',
        ]

    def select(self, name, readonly=True):
        self.calls.append(("select", name, readonly))
        return "OK", [b"3"]

    def response(self, code):
        return code, [b"777"]

    def uid(self, cmd, *args):
        self.calls.append((cmd, *args))
        if cmd == "SEARCH":
            return "OK", [b"4 5"]
        if cmd == "FETCH" and "HEADER.FIELDS" in args[1]:
            return "OK", [
                (b"1 (UID 4 FLAGS (\\Seen \\Flagged) RFC822.SIZE 1200 INTERNALDATE \"29-Sep-2026 10:00:01 +0200\" "
                 b"BODY[HEADER.FIELDS (FROM)] {%d}" % len(HEADER), HEADER),
                (b" BODY[TEXT]<0> {11}", b"Bonjour toi"),
                b")",
            ]
        return "OK", [None]


def make():
    b = ImapBackend("imap.test", 993, True, "u", "p")
    b.conn = FakeConn()
    return b


def test_list_folders_decodes_names_and_special_use():
    folders = {f.name: f for f in make().list_folders()}
    assert set(folders) == {"INBOX", "Brouillons", "Envoyés", "Dossier fou", "[Gmail]"}
    assert folders["Brouillons"].special_use == "drafts"
    assert folders["Envoyés"].special_use == "sent"
    assert not folders["[Gmail]"].selectable


def test_search_and_headers():
    b = make()
    uv, uids = b.search("Envoyés", None, None, unseen=True)
    assert (uv, uids) == (777, [4, 5])
    assert b.conn.calls[0] == ("select", '"Envoy&AOk-s"', True)
    assert b.conn.calls[1] == ("SEARCH", "UNSEEN")
    [h] = b.fetch_headers("Envoyés", [4])
    assert h.uid == 4 and h.seen and h.flagged and not h.answered
    assert h.from_name == "Sophie Bérnard" and h.from_addr == "sophie@acme.fr"
    assert h.subject == "Réunion demain" and h.is_bulk and h.snippet == "Bonjour toi"
    assert h.size == 1200 and h.message_id == "<abc@acme.fr>"


def test_move_uses_native_move():
    b = make()
    b.move("INBOX", [1, 2, 3, 9], "Finances/Factures")
    assert ("MOVE", "1:3,9", '"Finances/Factures"') in b.conn.calls
    assert ("select", '"INBOX"', False) in b.conn.calls
