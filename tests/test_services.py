from datetime import date, timedelta

from trieurmail.services import drafter, priority, sorter, summarizer
from trieurmail.services.jobs import Job
from trieurmail.services.sync import sync_scope, timeline


async def test_sync_is_incremental(ctx):
    first = await sync_scope(ctx, ctx.scope())
    assert first["new"] > 100
    second = await sync_scope(ctx, ctx.scope())
    assert second["new"] == 0 and second["updated"] == first["new"]


async def test_timeline_and_scope(ctx):
    tl = await timeline(ctx, ["INBOX"])
    assert tl["total"] > 100 and tl["buckets"]
    await ctx.update_settings({"scope": {"since": str(date.today() - timedelta(days=30))}})
    stats = await sync_scope(ctx, ctx.scope())
    assert 0 < stats["new"] < tl["total"]


async def test_priority_uses_cache(ctx, fake_llm_app):
    res = await priority.compute_priorities(ctx, Job("priority"))
    assert res["unread"] > 0 and res["items"]
    top = res["items"][0]
    assert top["score"] >= res["items"][-1]["score"]
    assert any("URGENT" in i["subject"] for i in res["items"][:3])
    assert not any(i["ai"] for i in res["items"] if i["is_bulk"])  # newsletters jamais envoyées à l'IA
    calls = fake_llm_app.state.calls
    res2 = await priority.compute_priorities(ctx, Job("priority"))
    assert fake_llm_app.state.calls == calls  # aucun nouvel appel
    assert res2["from_cache"] == res2["analysed"]


async def test_summary_brief_digest(ctx):
    await sync_scope(ctx, ctx.scope())
    headers, _ = ctx.db.query_headers(["INBOX"], limit=5)
    one = await summarizer.summarize_one(ctx, headers[0])
    assert one["summary"] and one["reply_suggestions"]
    briefs = await summarizer.brief_many(ctx, headers, Job("b"))
    assert set(briefs) == {h.mid for h in headers}
    dig = await summarizer.digest(ctx, headers, Job("d"))
    assert "## À traiter" in dig["markdown"]


async def test_draft_stream_and_save(ctx):
    await sync_scope(ctx, ctx.scope())
    headers, _ = ctx.db.query_headers(["INBOX"], limit=1)
    text = "".join([d async for d in drafter.draft_stream(ctx, headers[0], "", "pro")])
    assert "raisonnement" not in text and text.startswith("Bonjour")
    rc = await drafter.reply_context(ctx, headers[0])
    assert rc["subject"].startswith("Re:")
    res = await drafter.save_or_send(ctx, headers[0], to=rc["to"], cc="", subject=rc["subject"], body=text, send=False)
    assert res["status"] == "draft"
    assert ctx.backend.folders[res["folder"]]


async def test_sort_full_flow(ctx):
    plan = await sorter.propose(ctx, Job("sort"))
    assert plan["folders"] and plan["groups"]
    assert "keys" not in plan["groups"][0]
    plan = sorter.update_tree(ctx, plan["id"], plan["folders"] + [{"path": "Perso", "description": "Famille"}])
    plan = await sorter.assign(ctx, plan["id"], Job("sort"))
    assert plan["status"] == "assigned"
    moved_expected = sum(c for f, c in plan["folder_counts"].items() if f)
    assert moved_expected > 0
    perso_group = next(g for g in plan["groups"] if "orange.fr" in g["sender"])
    plan = sorter.update_assignments(ctx, plan["id"], {perso_group["id"]: "Perso"})
    result = await sorter.apply(ctx, plan["id"], Job("sort"))
    assert result["status"] == "applied"
    assert result["applied"]["moved"] == moved_expected + perso_group["count"]
    assert "Finances/Factures" in ctx.backend.folders and ctx.backend.folders["Perso"]
    rules = ctx.db.get_rules()
    assert rules[perso_group["sender"]] == "Perso"
    # les règles rangent les nouveaux emails sans IA
    ctx.backend._store("INBOX", {"name": "EDF", "addr": "noreply@edf.fr", "bulk": True, "subject": "Facture",
                                 "body": "x", "date": 1_900_000_000, "seen": False})
    res = await sorter.apply_rules(ctx, Job("rules"))
    assert res["moved"] == 1
