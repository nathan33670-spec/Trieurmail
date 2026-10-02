"""Synchronisation incrémentale IMAP → cache, et index de dates pour la timeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ..mail.backend import MailError
from .context import AppContext, Scope
from .jobs import Job

CHUNK = 200


async def sync_scope(ctx: AppContext, scope: Scope, job: Optional[Job] = None, unseen_only: bool = False,
                     progress_span: tuple[float, float] = (0.0, 1.0)) -> dict:
    """Ne télécharge que les en-têtes des messages inconnus du cache ;
    pour les messages déjà connus, seuls les drapeaux (lu / suivi) sont rafraîchis."""
    backend = ctx.backend
    db = ctx.db
    lo, hi = progress_span
    stats = {"new": 0, "updated": 0, "removed": 0, "folders": 0}
    folders = scope.folders
    for fi, folder in enumerate(folders):
        base = lo + (hi - lo) * fi / max(1, len(folders))
        step = (hi - lo) / max(1, len(folders))
        if job:
            job.update(base, f"Recherche dans « {folder} »…")
        try:
            uidvalidity, uids = await ctx.mail(backend.search, folder, scope.since, scope.before, unseen_only)
        except MailError as exc:
            if job:
                job.update(message=f"Dossier ignoré : {folder} ({exc})")
            continue
        stats["folders"] += 1
        cached_uv = db.folder_uidvalidity(folder)
        if cached_uv is not None and cached_uv != uidvalidity:
            db.reset_folder(folder, uidvalidity)
        else:
            db.touch_folder(folder, uidvalidity)

        known = db.known_uids(folder)
        uid_set = set(uids)
        new = [u for u in uids if u not in known]
        existing = [u for u in uids if u in known]

        if existing:
            flags = await ctx.mail(backend.fetch_flags, folder, existing)
            db.update_flags(folder, flags)
            stats["updated"] += len(flags)

        # messages en cache disparus du serveur (déplacés / supprimés / lus)
        cached, _ = db.query_headers([folder], scope.since_ts, scope.until_ts, unseen_only=unseen_only)
        margin = 86400  # SEARCH IMAP travaille à la journée : tolérance aux bords
        lo_ts = (scope.since_ts or 0) + margin
        hi_ts = (scope.until_ts or 2**40) - margin
        gone = [h for h in cached if h.uid not in uid_set and lo_ts <= h.date <= hi_ts]
        if gone:
            if unseen_only:
                db.set_seen([h.key for h in gone], True)
            else:
                db.delete_uids(folder, [h.uid for h in gone])
                stats["removed"] += len(gone)

        for i in range(0, len(new), CHUNK):
            chunk = new[i : i + CHUNK]
            if job:
                job.update(base + step * i / max(1, len(new)),
                           f"« {folder} » : en-têtes {i + 1}–{i + len(chunk)} / {len(new)}")
            headers = await ctx.mail(backend.fetch_headers, folder, chunk)
            db.upsert_headers(headers)
            stats["new"] += len(headers)
    return stats


async def timeline(ctx: AppContext, folders: list[str], rebuild: bool = False) -> dict:
    """Histogramme du volume d'emails (index de dates incrémental : seuls les
    nouveaux uids sont demandés au serveur)."""
    backend = ctx.backend
    db = ctx.db
    for folder in folders:
        if rebuild:
            db.clear_date_index(folder)
        start = db.date_index_max_uid(folder) + 1
        since_ts = db.date_index_max_ts(folder)
        try:
            uidvalidity, items = await ctx.mail(backend.fetch_dates, folder, start, since_ts)
        except MailError:
            continue
        known_uv = db.date_index_uidvalidity(folder)
        if known_uv is not None and known_uv != uidvalidity:
            db.clear_date_index(folder)
            uidvalidity, items = await ctx.mail(backend.fetch_dates, folder, 1, 0)
        db.add_dates(folder, uidvalidity, items)
    stamps = db.timestamps(folders)
    return bucketize(stamps)


def bucketize(stamps: list[int]) -> dict:
    if not stamps:
        return {"granularity": "month", "buckets": [], "total": 0}
    lo, hi = min(stamps), max(stamps)
    span_days = (hi - lo) / 86400
    granularity = "day" if span_days <= 62 else "week" if span_days <= 400 else "month"

    def bucket_start(ts: int) -> datetime:
        d = datetime.fromtimestamp(ts, timezone.utc)
        if granularity == "day":
            return d.replace(hour=0, minute=0, second=0, microsecond=0)
        if granularity == "week":
            d = d - timedelta(days=d.weekday())
            return d.replace(hour=0, minute=0, second=0, microsecond=0)
        return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def next_start(d: datetime) -> datetime:
        if granularity == "day":
            return d + timedelta(days=1)
        if granularity == "week":
            return d + timedelta(days=7)
        return (d.replace(day=28) + timedelta(days=4)).replace(day=1)

    counts: dict[datetime, int] = {}
    for ts in stamps:
        b = bucket_start(ts)
        counts[b] = counts.get(b, 0) + 1
    buckets = []
    cur, end = bucket_start(lo), bucket_start(hi)
    while cur <= end:
        buckets.append({"start": cur.date().isoformat(), "end": (next_start(cur).date() - timedelta(days=1)).isoformat(),
                        "count": counts.get(cur, 0)})
        cur = next_start(cur)
    return {"granularity": granularity, "buckets": buckets, "total": len(stamps)}
