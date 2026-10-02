from trieurmail.llm.client import extract_json, strip_reasoning
from trieurmail.mail import imap_utf7
from trieurmail.mail.imap_backend import group_fetch_response, uid_set
from trieurmail.mail.parsing import clean_for_llm, html_to_text, snippet_from_partial
from trieurmail.services.sorter import normalize_folders, normalize_path
from trieurmail.services.sync import bucketize


def test_utf7_roundtrip():
    for name in ["INBOX", "Reçus/Été 2024", "Brouillons & Notes", "日本語"]:
        assert imap_utf7.decode(imap_utf7.encode(name)) == name
    assert imap_utf7.encode("Envoyés") == "Envoy&AOk-s"


def test_uid_set():
    assert uid_set([5, 1, 2, 3, 8, 10, 11]) == "1:3,5,8,10:11"
    assert uid_set([]) == ""


def test_group_fetch_response():
    data = [
        (b'1 (UID 12 FLAGS (\\Seen) RFC822.SIZE 99 BODY[HEADER.FIELDS (FROM)] {20}', b"From: a@b.c\r\n\r\n"),
        (b' BODY[TEXT]<0> {5}', b"hello"),
        b')',
        b'2 (UID 13 FLAGS ())',
    ]
    msgs = group_fetch_response(data)
    assert len(msgs) == 2
    assert msgs[0]["header"].startswith(b"From") and msgs[0]["text"] == b"hello"
    assert b"UID 13" in msgs[1]["meta"]


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('<think>hmm {"x":0}</think>```json\n{"a": [1,2,],}\n```') == {"a": [1, 2]}
    assert extract_json('Voici : {"items": [{"id": "1"}]} merci') == {"items": [{"id": "1"}]}
    assert strip_reasoning("<think>x</think> ok") == "ok"


def test_clean_for_llm_removes_quotes_and_signature():
    text = "Bonjour,\nPeux-tu valider ?\n\n--\nCamille\nLe 3 mars 2025, Paul a écrit :\n> ancien"
    assert clean_for_llm(text, 1000) == "Bonjour,\nPeux-tu valider ?"


def test_html_to_text_and_snippet():
    assert html_to_text("<style>x{}</style><p>Salut&nbsp;toi</p><br>ok") == "Salut toi\n\nok"
    header = b"Content-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable"
    assert snippet_from_partial(header, b"Caf=C3=A9 pr=C3=AAt") == "Café prêt"


def test_normalize_folders():
    assert normalize_path("INBOX/Truc") == ""
    assert normalize_path(" Finances / Factures / 2024 ") == "Finances/Factures"
    out = normalize_folders([{"path": "A"}, "a", {"name": "B/C", "description": "d"}, 3])
    assert [f["path"] for f in out] == ["A", "B/C"]


def test_bucketize():
    day = 86400
    res = bucketize([0 + 10 * day, 0 + 12 * day, 0 + 40 * day])
    assert res["granularity"] == "day" and res["total"] == 3
    assert sum(b["count"] for b in res["buckets"]) == 3
