"""Tâches de fond avec progression, interrogées par l'interface."""
from __future__ import annotations

import asyncio
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional


class JobCancelled(Exception):
    pass


@dataclass
class Job:
    kind: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "running"  # running | done | error | cancelled
    progress: float = 0.0
    message: str = "Démarrage…"
    result: Any = None
    error: str = ""
    created: float = field(default_factory=time.time)
    finished: Optional[float] = None
    task: Optional[asyncio.Task] = field(default=None, repr=False)
    cancel_requested: bool = False

    def update(self, progress: Optional[float] = None, message: Optional[str] = None) -> None:
        if self.cancel_requested:
            raise JobCancelled()
        if progress is not None:
            self.progress = max(0.0, min(1.0, progress))
        if message is not None:
            self.message = message

    def as_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "status": self.status, "progress": round(self.progress, 3),
            "message": self.message, "result": self.result, "error": self.error,
            "created": self.created, "finished": self.finished,
        }


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}

    def start(self, kind: str, fn: Callable[[Job], Awaitable[Any]], exclusive: bool = True) -> Job:
        if exclusive:
            for job in self.jobs.values():
                if job.kind == kind and job.status == "running":
                    return job
        job = Job(kind=kind)
        self.jobs[job.id] = job

        async def runner() -> None:
            try:
                job.result = await fn(job)
                job.status = "done"
                job.progress = 1.0
                job.message = "Terminé"
            except (JobCancelled, asyncio.CancelledError):
                job.status = "cancelled"
                job.message = "Annulé"
            except Exception as exc:  # noqa: BLE001 - remonté à l'interface
                job.status = "error"
                job.error = str(exc) or exc.__class__.__name__
                job.message = "Erreur"
                traceback.print_exc()
            finally:
                job.finished = time.time()
                self._gc()

        job.task = asyncio.create_task(runner())
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if job and job.status == "running":
            job.cancel_requested = True

    def running(self) -> list[Job]:
        return [j for j in self.jobs.values() if j.status == "running"]

    def _gc(self) -> None:
        limit = time.time() - 3600
        for jid in [j.id for j in self.jobs.values() if j.finished and j.finished < limit]:
            self.jobs.pop(jid, None)
