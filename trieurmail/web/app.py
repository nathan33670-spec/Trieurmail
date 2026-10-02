"""API HTTP + service de l'interface (SPA statique, sans étape de build)."""
from __future__ import annotations

import html as html_lib
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..llm.client import LLMClient, LLMError
from ..mail.backend import MailError
from ..services import drafter, priority, sorter, summarizer
from ..services.context import AppContext
from ..services.sync import sync_scope, timeline

STATIC = Path(__file__).parent / "static"


# -- corps des requêtes ----------------------------------------------------
class ScopeIn(BaseModel):
    folders: list[str]
    since: Optional[str] = None
    until: Optional[str] = None


class SeenIn(BaseModel):
    keys: list[str]
    seen: bool = True


class SummaryIn(BaseModel):
    key: str
    force: bool = False


class KeysIn(BaseModel):
    keys: list[str] = []
    unread_only: bool = False


class DraftIn(BaseModel):
    key: str
    instructions: str = ""
    tone: str = "pro"


class SendIn(BaseModel):
    key: str
    to: str
    cc: str = ""
    subject: str
    body: str
    send: bool = False


class ProposeIn(BaseModel):
    hint: str = ""


class TreeIn(BaseModel):
    folders: list[dict]


class AssignIn(BaseModel):
    assignments: dict[str, str]



def create_app(ctx: Optional[AppContext] = None) -> FastAPI:
    holder: dict[str, AppContext] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        holder["ctx"] = ctx or AppContext()
        yield
        await holder["ctx"].aclose()

    app = FastAPI(title="Trieurmail", lifespan=lifespan)

    def C() -> AppContext:
        return holder["ctx"]

    @app.exception_handler(MailError)
    async def mail_error(_: Request, exc: MailError):
        return JSONResponse({"detail": f"Messagerie : {exc}"}, status_code=400)

    @app.exception_handler(LLMError)
    async def llm_error(_: Request, exc: LLMError):
        return JSONResponse({"detail": f"IA : {exc}"}, status_code=400)

    def header_or_404(key: str):
        h = C().db.get_header(key)
        if h is None:
            raise HTTPException(404, "Email introuvable dans le cache (resynchronisez).")
        return h

    def with_insights(headers) -> list[dict]:
        db = C().db
        mids = [h.mid for h in headers]
        briefs = db.any_insights(mids, "brief")
        prio = db.any_insights(mids, "priority")
        out = []
        for h in headers:
            d = h.to_dict()
            d["brief"] = briefs.get(h.mid)
            if h.mid in prio:
                d["ai_priority"] = prio[h.mid]
            out.append(d)
        return out

    # -- état & réglages ---------------------------------------------------
    @app.get("/api/state")
    async def state():
        c = C()
        s = c.settings
        configured_llm = bool(s.llm.base_url and s.llm.model)
        configured_mail = s.mail.provider == "demo" or bool(s.mail.imap_host and s.mail.username)
        plan = c.db.get_plan()
        return {
            "settings": s.public(),
            "configured": {"llm": configured_llm, "mail": configured_mail},
            "usage": c.llm.usage.as_dict(),
            "cache": c.db.stats(),
            "jobs": [j.as_dict() for j in c.jobs.running()],
            "plan_status": plan.get("status") if plan else None,
            "priority_at": (c.db.kv_get("priority:last") or {}).get("computed_at"),
        }

    @app.put("/api/settings")
    async def put_settings(patch: dict[str, Any]):
        try:
            s = await C().update_settings(patch)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return s.public()

    @app.post("/api/test/llm")
    async def test_llm(patch: dict[str, Any] | None = None):
        c = C()
        llm_settings = c.settings.llm
        if patch:
            merged = {**llm_settings.model_dump(), **{k: v for k, v in patch.items() if v != "••••••••"}}
            llm_settings = type(llm_settings).model_validate(merged)
        client = LLMClient(llm_settings)
        try:
            try:
                models = await client.list_models()
            except Exception as exc:  # certains serveurs n'exposent pas /models
                models, models_error = [], str(exc)
            else:
                models_error = ""
            reply = ""
            if llm_settings.model:
                reply = await client.chat(
                    [{"role": "user", "content": "Réponds uniquement : OK"}], max_tokens=200, use_cache=False
                )
            return {"models": models, "models_error": models_error, "reply": reply[:200]}
        except Exception as exc:
            raise HTTPException(400, f"IA : {exc}") from exc
        finally:
            await client.aclose()

    @app.post("/api/test/mail")
    async def test_mail():
        folders = await C().mail(C().backend.list_folders)
        return {"folders": len(folders)}

    @app.get("/api/folders")
    async def folders():
        items = await C().mail(C().backend.list_folders)
        return [
            {"name": f.name, "special": f.special_use, "selectable": f.selectable, "delimiter": f.delimiter}
            for f in items
        ]

    @app.get("/api/timeline")
    async def get_timeline(folders: list[str] = Query(default=[]), rebuild: bool = False):
        return await timeline(C(), folders or C().scope().folders, rebuild)


    @app.put("/api/scope")
    async def put_scope(scope: ScopeIn):
        s = await C().update_settings({"scope": {
            "folders": scope.folders or ["INBOX"], "since": scope.since or None, "until": scope.until or None,
        }})
        return s.public()["scope"]

    # -- tâches ------------------------------------------------------------
    @app.get("/api/jobs/{job_id}")
    async def job_status(job_id: str):
        job = C().jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Tâche inconnue")
        return job.as_dict()

    @app.post("/api/jobs/{job_id}/cancel")
    async def job_cancel(job_id: str):
        C().jobs.cancel(job_id)
        return {"ok": True}

    # -- messages ----------------------------------------------------------
    @app.post("/api/sync")
    async def sync():
        c = C()
        job = c.jobs.start("sync", lambda j: sync_scope(c, c.scope(), j))
        return job.as_dict()

    @app.get("/api/messages")
    async def messages(unread: bool = False, q: str = "", offset: int = 0, limit: int = 60):
        c = C()
        scope = c.scope()
        headers, total = c.db.query_headers(
            scope.folders, scope.since_ts, scope.until_ts, unseen_only=unread, search=q.strip(),
            limit=min(limit, 500), offset=offset,
        )
        return {"total": total, "items": with_insights(headers)}

    @app.get("/api/message")
    async def message(key: str, images: bool = False):
        c = C()
        h = header_or_404(key)
        body = await summarizer.get_body(c, h)
        summaries = c.db.any_insights([h.mid], "summary")
        return {
            **h.to_dict(),
            "text": body.text,
            "html_doc": render_html(body.html, images) if body.html else "",
            "has_remote_images": bool(re.search(r"<img[^>]+src=[\"']?https?:", body.html or "", re.I)),
            "attachments": [a.__dict__ for a in body.attachments],
            "headers": body.headers,
            "summary": summaries.get(h.mid),
        }


    @app.post("/api/message/seen")
    async def mark_seen(data: SeenIn):
        c = C()
        by_folder: dict[str, list[int]] = {}
        for h in c.db.get_headers(data.keys):
            by_folder.setdefault(h.folder, []).append(h.uid)
        for folder, uids in by_folder.items():
            await c.mail(c.backend.set_seen, folder, uids, data.seen)
        c.db.set_seen(data.keys, data.seen)
        return {"ok": True}

    # -- synthèses ---------------------------------------------------------

    @app.post("/api/summary")
    async def summary(data: SummaryIn):
        return await summarizer.summarize_one(C(), header_or_404(data.key), data.force)


    def resolve_keys(data: KeysIn):
        c = C()
        if data.keys:
            return c.db.get_headers(data.keys)
        scope = c.scope()
        headers, _ = c.db.query_headers(scope.folders, scope.since_ts, scope.until_ts, unseen_only=data.unread_only,
                                        limit=150)
        return headers

    @app.post("/api/briefs")
    async def briefs(data: KeysIn):
        c = C()
        headers = resolve_keys(data)[:200]
        job = c.jobs.start("briefs", lambda j: summarizer.brief_many(c, headers, j), exclusive=False)
        return job.as_dict()

    @app.post("/api/digest")
    async def digest(data: KeysIn):
        c = C()
        headers = resolve_keys(data)
        if not headers:
            raise HTTPException(400, "Aucun email à synthétiser dans la sélection.")
        job = c.jobs.start("digest", lambda j: summarizer.digest(c, headers, j))
        return job.as_dict()

    # -- priorités ---------------------------------------------------------
    @app.post("/api/priority")
    async def run_priority():
        c = C()
        job = c.jobs.start("priority", lambda j: priority.compute_priorities(c, j))
        return job.as_dict()

    @app.get("/api/priority")
    async def last_priority():
        return C().db.kv_get("priority:last") or {"items": [], "computed_at": None}

    # -- réponses ----------------------------------------------------------
    @app.get("/api/reply-context")
    async def reply_ctx(key: str):
        return await drafter.reply_context(C(), header_or_404(key))


    @app.post("/api/draft")
    async def draft(data: DraftIn):
        c = C()
        h = header_or_404(data.key)

        async def events():
            try:
                async for delta in drafter.draft_stream(c, h, data.instructions, data.tone):
                    yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
                yield "data: {\"done\": true}\n\n"
            except Exception as exc:  # noqa: BLE001
                yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


    @app.post("/api/draft/save")
    async def save_draft(data: SendIn):
        c = C()
        return await drafter.save_or_send(c, header_or_404(data.key), to=data.to, cc=data.cc,
                                          subject=data.subject, body=data.body, send=data.send)

    # -- tri ---------------------------------------------------------------

    @app.post("/api/sort/propose")
    async def sort_propose(data: ProposeIn):
        c = C()
        return c.jobs.start("sort", lambda j: sorter.propose(c, j, data.hint)).as_dict()

    @app.get("/api/sort/plan")
    async def sort_plan():
        return sorter.public_plan(C().db.get_plan()) or {}


    @app.put("/api/sort/plan/{plan_id}/tree")
    async def sort_tree(plan_id: int, data: TreeIn):
        try:
            return sorter.update_tree(C(), plan_id, data.folders)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/sort/plan/{plan_id}/assign")
    async def sort_assign(plan_id: int):
        c = C()
        return c.jobs.start("sort", lambda j: sorter.assign(c, plan_id, j)).as_dict()


    @app.put("/api/sort/plan/{plan_id}/assignments")
    async def sort_assignments(plan_id: int, data: AssignIn):
        try:
            return sorter.update_assignments(C(), plan_id, data.assignments)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/sort/plan/{plan_id}/apply")
    async def sort_apply(plan_id: int):
        c = C()
        return c.jobs.start("sort", lambda j: sorter.apply(c, plan_id, j)).as_dict()

    @app.get("/api/sort/rules")
    async def sort_rules():
        return C().db.get_rules()

    @app.post("/api/sort/rules/apply")
    async def sort_rules_apply():
        c = C()
        return c.jobs.start("sort", lambda j: sorter.apply_rules(c, j)).as_dict()

    @app.delete("/api/sort/rules")
    async def sort_rules_delete():
        C().db.delete_rules()
        return {"ok": True}

    @app.post("/api/cache/clear-ai")
    async def clear_ai():
        C().db.clear_ai_cache()
        return {"ok": True}

    # -- interface ---------------------------------------------------------
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app


def render_html(raw: str, allow_images: bool) -> str:
    """Document HTML isolé : affiché dans une iframe sandbox (sans scripts),
    avec une CSP bloquant le pistage par images distantes sauf accord explicite."""
    img = "data: cid: https: http:" if allow_images else "data: cid:"
    csp = f"default-src 'none'; img-src {img}; style-src 'unsafe-inline' https:; font-src data: https:;"
    head = (
        f'<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{html_lib.escape(csp)}">'
        '<base target="_blank"><style>body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:14px;'
        "line-height:1.5;color:#1f2330;margin:16px;word-wrap:break-word}img{max-width:100%;height:auto}"
        "table{max-width:100%}</style>"
    )
    raw = re.sub(r"<script.*?</script>", "", raw, flags=re.S | re.I)
    if re.search(r"<head[^>]*>", raw, re.I):
        return re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + head, raw, count=1, flags=re.I)
    return f"<!doctype html><html><head>{head}</head><body>{raw}</body></html>"
