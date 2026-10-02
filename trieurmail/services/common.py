"""Briques partagées par les services IA."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable, Iterable, TypeVar

from ..mail.models import MailBody, MailHeader, split_key
from .context import AppContext
from .jobs import Job

T = TypeVar("T")


def fmt_date(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else ""


def sender_label(h: MailHeader) -> str:
    return f"{h.from_name} <{h.from_addr}>" if h.from_name else h.from_addr


def chunks(items: list[T], size: int) -> Iterable[list[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def get_body(ctx: AppContext, h: MailHeader) -> MailBody:
    """Corps complet, avec cache local (un email n'est téléchargé qu'une fois)."""
    cached = ctx.db.get_body(h.mid)
    if cached is not None:
        return cached
    folder, _, uid = split_key(h.key)
    body = await ctx.mail(ctx.backend.fetch_body, folder, uid)
    ctx.db.put_body(h.mid, body)
    return body


async def run_batches(
    job: Job | None,
    batches: list[Any],
    fn: Callable[[Any], Awaitable[Any]],
    label: str,
    span: tuple[float, float] = (0.0, 1.0),
) -> list[Any]:
    """Exécute les lots en parallèle (borné par le sémaphore du client LLM)
    en rapportant la progression ; un lot en échec n'interrompt pas les autres."""
    done = 0
    lo, hi = span
    errors: list[str] = []

    async def wrapped(batch: Any) -> Any:
        nonlocal done
        try:
            return await fn(batch)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            return None
        finally:
            done += 1
            if job:
                job.update(lo + (hi - lo) * done / max(1, len(batches)), f"{label} {done}/{len(batches)}")

    results = await asyncio.gather(*(wrapped(b) for b in batches))
    if errors and all(r is None for r in results):
        raise RuntimeError(errors[0])
    return list(results)
