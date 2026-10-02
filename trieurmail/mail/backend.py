"""Interface commune aux fournisseurs de messagerie."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from .models import FolderInfo, MailBody, MailHeader, Uid


class MailError(Exception):
    pass


class MailBackend(ABC):
    """Toutes les méthodes sont bloquantes : elles sont appelées via asyncio.to_thread."""

    delimiter: str = "/"

    @abstractmethod
    def list_folders(self) -> list[FolderInfo]: ...

    @abstractmethod
    def search(self, folder: str, since: Optional[date], before: Optional[date], unseen: bool = False) -> tuple[int, list[Uid]]:
        """Retourne (uidvalidity, uids) des messages correspondant à la période."""

    @abstractmethod
    def fetch_headers(self, folder: str, uids: list[Uid]) -> list[MailHeader]: ...

    @abstractmethod
    def fetch_flags(self, folder: str, uids: list[Uid]) -> dict[Uid, tuple[bool, bool, Optional[bool]]]:
        """uid -> (seen, flagged, answered)"""

    @abstractmethod
    def fetch_dates(self, folder: str, min_uid: int, since_ts: int = 0) -> tuple[int, list[tuple[Uid, int]]]:
        """Dates de réception (uid, timestamp) pour la timeline, incrémentales :
        IMAP utilise ``min_uid``, les autres fournisseurs ``since_ts``."""

    @abstractmethod
    def fetch_body(self, folder: str, uid: Uid) -> MailBody: ...

    @abstractmethod
    def set_seen(self, folder: str, uids: list[Uid], seen: bool) -> None: ...

    @abstractmethod
    def create_folder(self, name: str) -> None: ...

    @abstractmethod
    def move(self, folder: str, uids: list[Uid], dest: str) -> None: ...

    @abstractmethod
    def append(self, folder: str, raw: bytes, flags: str = "") -> None: ...

    def close(self) -> None:  # pragma: no cover - optionnel
        pass

    # -- capacités optionnelles ---------------------------------------------
    def reply_draft(self, folder: str, uid: Uid, *, to: str, cc: str, subject: str, body: str,
                    send: bool) -> Optional[dict]:
        """Réponse native (fil de discussion conservé). None = non supporté,
        l'application construit alors le message elle-même (MIME + SMTP)."""
        return None

    def account_addresses(self) -> list[str]:
        """Adresses de l'utilisateur connues du fournisseur."""
        return []

    def special_folder(self, use: str) -> Optional[str]:
        for f in self.list_folders():
            if f.special_use == use:
                return f.name
        return None
