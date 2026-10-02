"""Interface commune aux fournisseurs de messagerie."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from .models import FolderInfo, MailBody, MailHeader


class MailError(Exception):
    pass


class MailBackend(ABC):
    """Toutes les méthodes sont bloquantes : elles sont appelées via asyncio.to_thread."""

    delimiter: str = "/"

    @abstractmethod
    def list_folders(self) -> list[FolderInfo]: ...

    @abstractmethod
    def search(self, folder: str, since: Optional[date], before: Optional[date], unseen: bool = False) -> tuple[int, list[int]]:
        """Retourne (uidvalidity, uids) des messages correspondant à la période."""

    @abstractmethod
    def fetch_headers(self, folder: str, uids: list[int]) -> list[MailHeader]: ...

    @abstractmethod
    def fetch_flags(self, folder: str, uids: list[int]) -> dict[int, tuple[bool, bool, bool]]:
        """uid -> (seen, flagged, answered)"""

    @abstractmethod
    def fetch_dates(self, folder: str, min_uid: int) -> tuple[int, list[tuple[int, int]]]:
        """Dates de réception (uid, timestamp) à partir d'un uid, pour la timeline."""

    @abstractmethod
    def fetch_body(self, folder: str, uid: int) -> MailBody: ...

    @abstractmethod
    def set_seen(self, folder: str, uids: list[int], seen: bool) -> None: ...

    @abstractmethod
    def create_folder(self, name: str) -> None: ...

    @abstractmethod
    def move(self, folder: str, uids: list[int], dest: str) -> None: ...

    @abstractmethod
    def append(self, folder: str, raw: bytes, flags: str = "") -> None: ...

    def close(self) -> None:  # pragma: no cover - optionnel
        pass

    def special_folder(self, use: str) -> Optional[str]:
        for f in self.list_folders():
            if f.special_use == use:
                return f.name
        return None
