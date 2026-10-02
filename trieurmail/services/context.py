"""État partagé de l'application : paramètres, cache, connexions."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Optional

from ..config import Settings, SettingsStore, data_dir
from ..db import Database
from ..llm.client import LLMClient
from ..mail.graph_auth import GraphAuth
from ..mail import MailBackend, create_backend
from .jobs import JobManager


class Scope:
    """Période et dossiers sélectionnés via la timeline."""

    def __init__(self, folders: list[str], since: Optional[date], until: Optional[date]):
        self.folders = folders
        self.since = since
        self.until = until

    @property
    def before(self) -> Optional[date]:
        return self.until + timedelta(days=1) if self.until else None

    @property
    def since_ts(self) -> Optional[int]:
        return int(datetime.combine(self.since, time.min).timestamp()) if self.since else None

    @property
    def until_ts(self) -> Optional[int]:
        return int(datetime.combine(self.before, time.min).timestamp()) if self.before else None


class AppContext:
    def __init__(self, store: Optional[SettingsStore] = None, db: Optional[Database] = None):
        self.store = store or SettingsStore()
        self.db = db or Database(data_dir() / "cache.sqlite")
        self.jobs = JobManager()
        self._backend: Optional[MailBackend] = None
        self._llm: Optional[LLMClient] = None
        self._graph_auth: Optional[GraphAuth] = None
        self._mail_lock = asyncio.Lock()

    @property
    def settings(self) -> Settings:
        return self.store.settings

    @property
    def graph_auth(self) -> GraphAuth:
        m = self.settings.mail
        if self._graph_auth is None or (self._graph_auth.client_id, self._graph_auth.tenant) != (
            m.graph_client_id, m.graph_tenant or "organizations"
        ):
            self._graph_auth = GraphAuth(m.graph_client_id, m.graph_tenant, data_dir() / "graph_token.json")
        return self._graph_auth

    @property
    def backend(self) -> MailBackend:
        if self._backend is None:
            m = self.settings.mail
            self._backend = create_backend(m, self.graph_auth if m.provider == "graph" else None)
        return self._backend

    def reset_mailbox(self) -> None:
        """Autre boîte mail : le cache des messages n'est plus valable."""
        if self._backend is not None:
            self._backend.close()
        self._backend = None
        for table in ("messages", "folder_state", "date_index", "bodies", "insights", "sort_plans", "rules", "kv"):
            self.db.execute(f"DELETE FROM {table}")

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient(self.settings.llm, self.db)
        return self._llm

    async def mail(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Exécute un appel bloquant (IMAP, Graph, AppleScript) hors de la boucle asyncio, en série."""
        async with self._mail_lock:
            return await asyncio.to_thread(fn, *args, **kwargs)

    async def update_settings(self, patch: dict) -> Settings:
        before = self.settings
        after = self.store.update(patch)
        if after.mail != before.mail:
            identity = lambda m: (m.provider, m.imap_host, m.username, m.graph_tenant)  # noqa: E731
            if identity(after.mail) != identity(before.mail):
                await asyncio.to_thread(self.reset_mailbox)
            else:
                if self._backend is not None:
                    await asyncio.to_thread(self._backend.close)
                self._backend = None
        if after.llm != before.llm:
            await self.close_llm()
        return after

    async def close_llm(self) -> None:
        if self._llm is not None:
            usage = self._llm.usage
            await self._llm.aclose()
            self._llm = None
            self.llm.usage = usage  # conserve les statistiques

    async def aclose(self) -> None:
        if self._llm is not None:
            await self._llm.aclose()
        if self._backend is not None:
            await asyncio.to_thread(self._backend.close)

    def scope(self) -> Scope:
        s = self.settings.scope
        return Scope(list(s.folders or ["INBOX"]), s.since, s.until)

    def signature(self, *parts: str) -> str:
        """Empreinte des paramètres influençant un résultat IA (invalidation du cache)."""
        return hashlib.sha1("\x1f".join(parts).encode()).hexdigest()[:16]

    def my_addresses(self) -> set[str]:
        m = self.settings.mail
        if m.provider == "demo":
            from ..mail.demo_backend import ME

            return {ME}
        addresses = {a.lower() for a in (m.from_address, m.username, m.smtp_username) if a and "@" in a}
        if m.provider == "graph" and self.graph_auth.account:
            addresses.add(self.graph_auth.account.lower())
        elif m.provider == "outlook_mac" and self._backend is not None:
            addresses.update(self._backend.account_addresses())
        return addresses
