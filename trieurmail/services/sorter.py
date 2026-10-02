"""Feature 1 : tri de l'historique.

Étapes (l'utilisateur valide entre chaque) :
1. ``propose``  : l'IA propose une arborescence à partir d'un résumé compact
                  des expéditeurs (1 seul appel, quelle que soit la taille de la boîte) ;
2. l'utilisateur modifie / confirme l'arborescence ;
3. ``assign``   : chaque *expéditeur* (et non chaque email) est rangé : 40 groupes par appel.
                  Les règles déjà apprises sont appliquées sans IA ;
4. l'utilisateur ajuste l'aperçu ;
5. ``apply``    : création des dossiers et déplacements IMAP groupés.
Les associations expéditeur → dossier sont mémorisées comme règles pour trier
les nouveaux emails plus tard sans aucun appel IA.
"""
from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from typing import Optional

from ..llm import prompts
from ..mail.models import MailHeader, split_key
from .common import chunks, run_batches
from .context import AppContext
from .jobs import Job
from .sync import sync_scope

GROUPS_IN_PROPOSAL = 140
GROUPS_PER_ASSIGN_CALL = 40
GENERIC_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.fr", "hotmail.com", "hotmail.fr", "live.fr", "live.com",
    "yahoo.com", "yahoo.fr", "orange.fr", "wanadoo.fr", "free.fr", "sfr.fr", "laposte.net", "icloud.com", "me.com",
    "proton.me", "protonmail.com", "gmx.fr", "gmx.com", "bbox.fr", "neuf.fr",
}


def _domain(addr: str) -> str:
    return addr.split("@")[-1].lower() if "@" in addr else addr.lower()


def group_key(h: MailHeader) -> str:
    """Envois automatisés regroupés par domaine (noreply@, news@, factures@...),
    personnes regroupées par adresse."""
    dom = _domain(h.from_addr)
    if h.is_bulk and dom not in GENERIC_DOMAINS:
        return "@" + dom
    return h.from_addr or "(inconnu)"


def build_groups(headers: list[MailHeader]) -> list[dict]:
    buckets: dict[str, list[MailHeader]] = defaultdict(list)
    for h in headers:
        buckets[group_key(h)].append(h)
    groups = []
    for i, (sender, items) in enumerate(sorted(buckets.items(), key=lambda kv: -len(kv[1]))):
        names = Counter(h.from_name for h in items if h.from_name)
        subjects: list[str] = []
        seen_norm: set[str] = set()
        for h in sorted(items, key=lambda h: -h.date):
            norm = re.sub(r"\d+", "#", h.subject.lower())[:50]
            if norm not in seen_norm:
                seen_norm.add(norm)
                subjects.append(h.subject[:70])
            if len(subjects) == 3:
                break
        groups.append({
            "id": f"g{i + 1}",
            "sender": sender,
            "name": names.most_common(1)[0][0] if names else "",
            "count": len(items),
            "unread": sum(1 for h in items if not h.seen),
            "bulk": sum(h.is_bulk for h in items) > len(items) / 2,
            "subjects": subjects,
            "keys": [h.key for h in items],
            "last": max(h.date for h in items),
        })
    return groups


def _group_line(g: dict, with_id: bool) -> str:
    who = f"{g['name']} <{g['sender']}>" if g["name"] else g["sender"]
    kind = "auto" if g["bulk"] else "humain"
    subjects = " ; ".join(g["subjects"])
    if with_id:
        return f"{g['id']} | {who} | {g['count']} | {kind} | {subjects}"
    return f"{g['count']} | {who} | {kind} | {subjects}"


def normalize_path(path: str) -> str:
    parts = [re.sub(r"\s+", " ", p).strip(" .") for p in re.split(r"[/\\>]", str(path))]
    parts = [p[:40] for p in parts if p]
    if not parts or parts[0].upper() in ("INBOX", "BOÎTE DE RÉCEPTION"):
        return ""
    return "/".join(parts[:2])


def normalize_folders(raw: list) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw or []:
        if isinstance(item, str):
            item = {"path": item}
        if not isinstance(item, dict):
            continue
        path = normalize_path(item.get("path") or item.get("name") or "")
        if not path or path.lower() in seen:
            continue
        seen.add(path.lower())
        out.append({"path": path, "description": str(item.get("description", ""))[:200]})
    return out


def _public_plan(plan: dict) -> dict:
    """Plan allégé pour l'interface (sans la liste des clés de messages)."""
    data = {k: v for k, v in plan.items() if k != "groups"}
    data["groups"] = [{k: v for k, v in g.items() if k != "keys"} for g in plan.get("groups", [])]
    counts: Counter = Counter()
    for g in plan.get("groups", []):
        counts[plan.get("assignments", {}).get(g["id"], "")] += g["count"]
    data["folder_counts"] = dict(counts)
    return data


def public_plan(plan: Optional[dict]) -> Optional[dict]:
    return _public_plan(plan) if plan else None


async def propose(ctx: AppContext, job: Job, hint: str = "") -> dict:
    s = ctx.settings
    scope = ctx.scope()
    await sync_scope(ctx, scope, job, progress_span=(0.0, 0.5))
    headers, total = ctx.db.query_headers(scope.folders, scope.since_ts, scope.until_ts)
    if not headers:
        raise RuntimeError("Aucun email dans la période sélectionnée.")
    job.update(0.55, f"Analyse de {total} emails / regroupement par expéditeur…")
    groups = build_groups(headers)
    shown = groups[:GROUPS_IN_PROPOSAL]
    lines = "\n".join(_group_line(g, with_id=False) for g in shown)
    rest = groups[GROUPS_IN_PROPOSAL:]
    if rest:
        lines += f"\n… et {len(rest)} autres expéditeurs ({sum(g['count'] for g in rest)} emails)"
    folders = await ctx.mail(ctx.backend.list_folders)
    existing = ", ".join(f.name for f in folders if not f.special_use and f.name.upper() != "INBOX") or "aucun"
    job.update(0.65, f"L'IA conçoit l'arborescence ({len(groups)} expéditeurs)…")
    data = await ctx.llm.chat_json(
        [{"role": "system", "content": prompts.PROPOSE_TREE_SYSTEM.format(language=s.profile.language)},
         {"role": "user", "content": prompts.PROPOSE_TREE_USER.format(
             existing=existing, groups=lines, hint=f"\nConsigne de l'utilisateur : {hint}" if hint.strip() else "")}],
        max_tokens=max(1200, s.llm.max_tokens), temperature=0.3,
    )
    raw = data.get("folders", []) if isinstance(data, dict) else data
    proposal = normalize_folders(raw)
    if not proposal:
        raise RuntimeError("L'IA n'a proposé aucun dossier exploitable. Réessayez ou changez de modèle.")
    plan = {
        "status": "proposed",
        "created": int(time.time()),
        "scope": {"folders": scope.folders, "since": str(scope.since or ""), "until": str(scope.until or "")},
        "total": total,
        "folders": proposal,
        "rationale": str(data.get("rationale", "")) if isinstance(data, dict) else "",
        "groups": groups,
        "assignments": {},
    }
    plan["id"] = ctx.db.save_plan(plan)
    return _public_plan(plan)


def update_tree(ctx: AppContext, plan_id: int, folders: list) -> dict:
    plan = ctx.db.get_plan(plan_id)
    if not plan:
        raise KeyError("Plan introuvable")
    plan["folders"] = normalize_folders(folders)
    valid = {f["path"] for f in plan["folders"]}
    plan["assignments"] = {g: f for g, f in plan.get("assignments", {}).items() if f in valid or f == ""}
    ctx.db.save_plan(plan, plan_id)
    return _public_plan(plan)


def update_assignments(ctx: AppContext, plan_id: int, assignments: dict[str, str]) -> dict:
    plan = ctx.db.get_plan(plan_id)
    if not plan:
        raise KeyError("Plan introuvable")
    valid = {f["path"] for f in plan["folders"]}
    for gid, folder in assignments.items():
        plan["assignments"][gid] = folder if folder in valid else ""
    ctx.db.save_plan(plan, plan_id)
    return _public_plan(plan)


async def assign(ctx: AppContext, plan_id: int, job: Job) -> dict:
    s = ctx.settings
    plan = ctx.db.get_plan(plan_id)
    if not plan:
        raise KeyError("Plan introuvable")
    folders = plan["folders"]
    if not folders:
        raise RuntimeError("L'arborescence est vide.")
    valid = {f["path"] for f in folders}
    rules = ctx.db.get_rules()
    assignments: dict[str, str] = {}
    todo = []
    for g in plan["groups"]:
        if g["sender"] in rules and rules[g["sender"]] in valid:
            assignments[g["id"]] = rules[g["sender"]]
        else:
            todo.append(g)
    numbered = "\n".join(
        f"{i + 1} = {f['path']}" + (f" ({f['description']})" if f["description"] else "") for i, f in enumerate(folders)
    )
    system = prompts.ASSIGN_SYSTEM.format(folders=numbered)
    by_id = {g["id"]: g for g in todo}

    async def run(batch: list[dict]) -> dict:
        data = await ctx.llm.chat_json(
            [{"role": "system", "content": system},
             {"role": "user", "content": prompts.ASSIGN_USER.format(
                 groups="\n".join(_group_line(g, with_id=True) for g in batch))}],
            model=s.llm.fast_model(), temperature=0.0, max_tokens=20 * len(batch) + 60,
        )
        items = data.get("a") or data.get("assignments") or data.get("items") if isinstance(data, dict) else data
        out = {}
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("id", "")).strip()
            if gid not in by_id:
                continue
            target = item.get("f", item.get("folder", 0))
            try:
                idx = int(target)
                out[gid] = folders[idx - 1]["path"] if 1 <= idx <= len(folders) else ""
            except (TypeError, ValueError):
                path = normalize_path(str(target))
                out[gid] = path if path in valid else ""
        return out

    if todo:
        job.update(0.05, f"{len(plan['groups']) - len(todo)} expéditeurs rangés par règles, {len(todo)} par l'IA…")
        for r in await run_batches(job, list(chunks(todo, GROUPS_PER_ASSIGN_CALL)), run, "Classement lot", (0.05, 0.98)):
            if r:
                assignments.update(r)
    for g in plan["groups"]:
        assignments.setdefault(g["id"], "")
    plan["assignments"] = assignments
    plan["status"] = "assigned"
    ctx.db.save_plan(plan, plan_id)
    return _public_plan(plan)


def _full_path(ctx: AppContext, path: str) -> str:
    delim = ctx.backend.delimiter or "/"
    root = ctx.settings.mail.sorted_root.strip()
    parts = ([root] if root else []) + path.split("/")
    return delim.join(p.replace(delim, "-") for p in parts)


async def apply(ctx: AppContext, plan_id: int, job: Job) -> dict:
    plan = ctx.db.get_plan(plan_id)
    if not plan:
        raise KeyError("Plan introuvable")
    if plan.get("status") == "applied":
        raise RuntimeError("Ce plan a déjà été appliqué.")
    assignments = plan.get("assignments", {})
    moves: dict[tuple[str, str], list[int]] = defaultdict(list)
    rules: dict[str, str] = {}
    for g in plan["groups"]:
        target = assignments.get(g["id"], "")
        if not target:
            continue
        rules[g["sender"]] = target
        dest = _full_path(ctx, target)
        for key in g["keys"]:
            folder, _, uid = split_key(key)
            if folder != dest:
                moves[(folder, dest)].append(uid)
    await ctx.mail(ctx.backend.list_folders)  # détermine le séparateur du serveur
    targets = sorted({dest for _, dest in moves})
    for i, dest in enumerate(targets):
        job.update(0.1 * i / max(1, len(targets)), f"Création du dossier « {dest} »")
        await ctx.mail(ctx.backend.create_folder, dest)
    total = sum(len(v) for v in moves.values())
    moved = 0
    for (folder, dest), uids in moves.items():
        for chunk in chunks(uids, 250):
            job.update(0.1 + 0.88 * moved / max(1, total), f"Déplacement vers « {dest} » ({moved}/{total})")
            await ctx.mail(ctx.backend.move, folder, chunk, dest)
            ctx.db.forget_moved(folder, chunk)
            moved += len(chunk)
    ctx.db.save_rules(rules)
    ctx.db.kv_set("priority:last", None)  # les emails déplacés ont changé d'identifiant IMAP
    plan["status"] = "applied"
    plan["applied"] = {"moved": moved, "folders": len(targets), "at": int(time.time())}
    ctx.db.save_plan(plan, plan_id)
    return _public_plan(plan)


async def apply_rules(ctx: AppContext, job: Job) -> dict:
    """Tri des nouveaux emails avec les règles apprises : zéro appel IA."""
    rules = ctx.db.get_rules()
    if not rules:
        raise RuntimeError("Aucune règle enregistrée : effectuez d'abord un tri complet.")
    scope = ctx.scope()
    await sync_scope(ctx, scope, job, progress_span=(0.0, 0.4))
    headers, _ = ctx.db.query_headers(scope.folders, scope.since_ts, scope.until_ts)
    await ctx.mail(ctx.backend.list_folders)
    moves: dict[tuple[str, str], list[int]] = defaultdict(list)
    for h in headers:
        target = rules.get(group_key(h))
        if target:
            dest = _full_path(ctx, target)
            if dest != h.folder:
                moves[(h.folder, dest)].append(h.uid)
    total = sum(len(v) for v in moves.values())
    moved = 0
    for (folder, dest), uids in moves.items():
        await ctx.mail(ctx.backend.create_folder, dest)
        for chunk in chunks(uids, 250):
            job.update(0.4 + 0.58 * moved / max(1, total), f"Déplacement vers « {dest} »")
            await ctx.mail(ctx.backend.move, folder, chunk, dest)
            ctx.db.forget_moved(folder, chunk)
            moved += len(chunk)
    if moved:
        ctx.db.kv_set("priority:last", None)
    return {"moved": moved, "rules": len(rules)}
