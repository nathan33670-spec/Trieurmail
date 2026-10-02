from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class FolderInfo:
    name: str
    delimiter: str = "/"
    flags: list[str] = field(default_factory=list)
    special_use: Optional[str] = None  # drafts, sent, trash, junk, archive, all

    @property
    def selectable(self) -> bool:
        return "\\noselect" not in [f.lower() for f in self.flags]


@dataclass
class MailHeader:
    """Métadonnées légères d'un email (ce qui est mis en cache)."""

    folder: str
    uidvalidity: int
    uid: int
    message_id: str = ""
    subject: str = ""
    from_name: str = ""
    from_addr: str = ""
    to_addrs: str = ""  # adresses séparées par des virgules
    cc_addrs: str = ""
    date: int = 0  # timestamp UTC
    seen: bool = False
    flagged: bool = False
    answered: bool = False
    snippet: str = ""
    size: int = 0
    has_attachments: bool = False
    is_bulk: bool = False  # newsletter / envoi automatisé
    in_reply_to: str = ""
    references: str = ""
    high_importance: bool = False

    @property
    def key(self) -> str:
        return f"{self.folder}\x1f{self.uidvalidity}\x1f{self.uid}"

    @property
    def mid(self) -> str:
        """Identifiant stable même après déplacement (Message-ID)."""
        return self.message_id or self.key

    def to_dict(self) -> dict:
        data = asdict(self)
        data["key"] = self.key
        return data


@dataclass
class Attachment:
    filename: str
    content_type: str
    size: int


@dataclass
class MailBody:
    text: str = ""
    html: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


def split_key(key: str) -> tuple[str, int, int]:
    folder, uidvalidity, uid = key.split("\x1f")
    return folder, int(uidvalidity), int(uid)
