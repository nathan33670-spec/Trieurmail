"""Feature 2 : extraire les emails non lus les plus prioritaires.

Pipeline économe :
1. synchronisation des seuls non lus de la période ;
2. pré-score heuristique local pour tous ;
3. seuls les N meilleurs candidats (hors newsletters) vont à l'IA, par lots ;
4. résultats IA mis en cache par Message-ID : un email n'est jamais réévalué.
"""
from __future__ import annotations

import time
from datetime import date

from ..llm import prompts
from ..mail.models import MailHeader
from .common import chunks, fmt_date, run_batches, sender_label
from .context import AppContext
from .heuristics import heuristic_priority, tier
from .jobs import Job
from .sync import sync_scope

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def today_label() -> str:
    d = date.today()
    return f"{JOURS[d.weekday()]} {d.strftime('%d/%m/%Y')}"


ACTIONS = {"répondre", "traiter", "lire", "planifier", "ignorer"}


def close_contacts(ctx: AppContext) -> set[str]:
    rows = ctx.db.execute("SELECT DISTINCT from_addr FROM messages WHERE answered=1")
    return {r["from_addr"] for r in rows}


def _line(i: int, h: MailHeader, me: set[str], max_chars: int) -> str:
    to = set(h.to_addrs.split(","))
    dest = "moi (direct)" if me & to else "moi (copie)" if me & set(h.cc_addrs.split(",")) else "liste/autre"
    snippet = h.snippet[: min(400, max_chars)]
    return f"[{i}] De: {sender_label(h)} | À: {dest} | {fmt_date(h.date)} | Objet: {h.subject}\n{snippet}"


async def compute_priorities(ctx: AppContext, job: Job) -> dict:
    s = ctx.settings
    scope = ctx.scope()
    await sync_scope(ctx, scope, job, unseen_only=True, progress_span=(0.0, 0.25))
    headers, _ = ctx.db.query_headers(scope.folders, scope.since_ts, scope.until_ts, unseen_only=True)
    me = ctx.my_addresses()
    contacts = close_contacts(ctx)
    now = time.time()
    heur = {h.key: heuristic_priority(h, me, contacts, now) for h in headers}

    eligible = [h for h in headers if s.profile.include_newsletters_in_priority or not h.is_bulk]
    eligible.sort(key=lambda h: heur[h.key], reverse=True)
    candidates = eligible[: s.llm.max_priority_candidates]

    sig = ctx.signature("prio-v1", s.llm.fast_model(), s.profile.about, s.profile.full_name)
    cached = ctx.db.get_insights([h.mid for h in candidates], "priority", sig)
    todo = [h for h in candidates if h.mid not in cached]

    system = prompts.PRIORITY_SYSTEM.format(
        profile=prompts.profile_block(s.profile), today=today_label(), language=s.profile.language
    )

    async def rate(batch: list[MailHeader]) -> dict:
        lines = "\n\n".join(_line(i + 1, h, me, s.llm.max_chars_per_email) for i, h in enumerate(batch))
        data = await ctx.llm.chat_json(
            [{"role": "system", "content": system}, {"role": "user", "content": lines}],
            model=s.llm.fast_model(), temperature=0.1, max_tokens=80 * len(batch) + 100,
        )
        items = data.get("items", data) if isinstance(data, dict) else data
        out = {}
        for item in items if isinstance(items, list) else []:
            try:
                idx = int(str(item.get("id")).strip("[] ")) - 1
                h = batch[idx]
                score = int(float(item.get("score", 0)))
            except (ValueError, TypeError, IndexError, AttributeError):
                continue
            action = str(item.get("action", "lire")).lower()
            out[h.mid] = {
                "score": max(0, min(100, score)),
                "action": action if action in ACTIONS else "lire",
                "reason": str(item.get("reason", ""))[:160],
                "deadline": str(item.get("deadline", "") or "")[:60],
            }
        ctx.db.put_insights("priority", sig, out)
        return out

    if todo:
        job.update(0.3, f"Analyse IA de {len(todo)} emails ({len(candidates) - len(todo)} déjà en cache)…")
        results = await run_batches(job, list(chunks(todo, s.llm.batch_size)), rate, "Analyse IA lot", (0.3, 0.98))
        for r in results:
            if r:
                cached.update(r)

    items = []
    for h in headers:
        ai = cached.get(h.mid)
        hs = heur[h.key]
        final = round(0.75 * ai["score"] + 0.25 * hs) if ai else round(hs * 0.8)
        items.append({
            **h.to_dict(), "heuristic": hs, "score": final, "tier": tier(final), "ai": bool(ai),
            "action": ai["action"] if ai else ("ignorer" if h.is_bulk else "lire"),
            "reason": ai["reason"] if ai else ("Envoi automatisé / newsletter" if h.is_bulk else "Pré-score local"),
            "deadline": ai["deadline"] if ai else "",
        })
    items.sort(key=lambda x: (x["score"], x["date"]), reverse=True)
    result = {
        "computed_at": int(time.time()),
        "unread": len(headers),
        "analysed": len(candidates),
        "from_cache": len(candidates) - len(todo),
        "items": items,
    }
    ctx.db.kv_set("priority:last", result)
    return result
