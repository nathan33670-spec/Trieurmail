import pytest

from fake_graph import FakeGraph
from trieurmail.mail import graph_backend
from trieurmail.mail.graph_auth import GraphAuth
from trieurmail.mail.graph_backend import GraphBackend
from trieurmail.services import drafter, priority, sorter
from trieurmail.services.jobs import Job
from trieurmail.services.sync import sync_scope, timeline


@pytest.fixture
def graph(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_backend, "PAGE", 5)  # force la pagination
    fake = FakeGraph()
    auth = GraphAuth("client", "organizations", tmp_path / "token.json", transport=fake.transport())
    status = auth.start_device_flow()
    assert status["user_code"] == "ABCD-1234" and status["pending"]
    assert auth.poll_once() == "pending"
    assert auth.poll_once() == "ok"
    assert auth.connected and auth.account == "moi@entreprise.fr"
    assert (tmp_path / "token.json").stat().st_mode & 0o777 == 0o600
    return fake, auth, GraphBackend(auth, transport=fake.transport())


def test_token_persisted_and_logout(tmp_path, graph):
    fake, auth, _ = graph
    again = GraphAuth("client", "organizations", tmp_path / "token.json", transport=fake.transport())
    assert again.connected and again.access_token() == "AT-1"
    assert not GraphAuth("autre", "organizations", tmp_path / "token.json").connected  # autre client ID
    again.logout()
    assert not (tmp_path / "token.json").exists()


def test_folders_and_headers(graph):
    fake, _, backend = graph
    folders = {f.name: f for f in backend.list_folders()}
    assert "INBOX" in folders and "INBOX/Clients" in folders
    assert folders["Brouillons"].special_use == "drafts"
    assert folders["Éléments envoyés"].special_use == "sent"
    _, uids = backend.search("INBOX", None, None)
    assert len(uids) == 23  # pagination suivie
    headers = backend.fetch_headers("INBOX", uids)  # $batch avec un 429 rejoué
    assert fake.throttled_once and len(headers) == 23
    h = {x.uid: x for x in headers}
    first = h["AAMkImmutable000=="]
    assert first.high_importance and first.has_attachments and first.in_reply_to == "conv0"
    assert not first.seen and first.to_addrs == "moi@entreprise.fr"
    assert h["AAMkImmutable001=="].is_bulk and not first.is_bulk
    assert h["AAMkImmutable004=="].answered
    body = backend.fetch_body("INBOX", "AAMkImmutable000==")
    assert "URGENT" in body.text and body.attachments[0].filename == "devis.pdf"
    flags = backend.fetch_flags("INBOX", ["AAMkImmutable000=="])
    assert flags["AAMkImmutable000=="] == (False, False, None)


async def test_services_on_graph(ctx, graph):
    fake, auth, backend = graph
    await ctx.update_settings({"mail": {"provider": "graph", "graph_client_id": "client"}})
    ctx._backend = backend
    ctx._graph_auth = auth
    stats = await sync_scope(ctx, ctx.scope())
    assert stats["new"] == 23
    assert (await sync_scope(ctx, ctx.scope()))["new"] == 0
    tl = await timeline(ctx, ["INBOX"])
    assert tl["total"] == 23
    res = await priority.compute_priorities(ctx, Job("p"))
    assert res["items"][0]["subject"].startswith("URGENT")
    assert "moi@entreprise.fr" in ctx.my_addresses()
    # réponse native : brouillon dans le fil, puis envoi
    h = ctx.db.get_header(next(i["key"] for i in res["items"] if i["subject"].startswith("URGENT")))
    out = await drafter.save_or_send(ctx, h, to="sophie@acme.fr", cc="", subject="RE: budget", body="OK pour moi\nCamille", send=False)
    assert out == {"status": "draft", "folder": "Brouillons"}
    draft = fake.messages[f"DRAFT-{h.uid}"]
    assert draft["body"]["content"].startswith("<div>OK pour moi<br>Camille</div>") and "message d'origine" in draft["body"]["content"]
    assert draft["toRecipients"][0]["emailAddress"]["address"] == "sophie@acme.fr"
    sent = await drafter.save_or_send(ctx, h, to="sophie@acme.fr", cc="", subject="RE: budget", body="OK", send=True)
    assert sent["status"] == "sent" and fake.messages[f"DRAFT-{h.uid}"]["folder"] == "F-SENT"
    # tri complet : création de dossiers et déplacements par $batch
    plan = await sorter.propose(ctx, Job("s"))
    plan = await sorter.assign(ctx, plan["id"], Job("s"))
    gid = next(g["id"] for g in plan["groups"] if g["sender"] == "@edf.fr")
    plan = sorter.update_assignments(ctx, plan["id"], {gid: "Finances/Factures"})
    done = await sorter.apply(ctx, plan["id"], Job("s"))
    assert done["applied"]["moved"] >= 6
    created = {v["displayName"]: k for k, v in fake.folders.items()}
    assert "Finances" in created and fake.folders[created["Factures"]]["parent"] == created["Finances"]
    assert all(m["folder"] == created["Factures"] for m in fake.messages.values()
               if m.get("from", {}).get("emailAddress", {}).get("address") == "noreply@edf.fr")
