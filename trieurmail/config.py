"""Paramètres de l'application, persistés en JSON dans le dossier de données."""
from __future__ import annotations

import json
import os
import threading
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

SECRET_MASK = "••••••••"


def data_dir() -> Path:
    path = Path(os.environ.get("TRIEURMAIL_HOME", Path.home() / ".trieurmail"))
    path.mkdir(parents=True, exist_ok=True)
    return path


class LLMSettings(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    api_key: str = ""
    model: str = ""
    # Modèle plus léger optionnel pour les tâches de masse (tri, priorisation).
    model_fast: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout: float = 180.0
    concurrency: int = Field(2, ge=1, le=16)
    batch_size: int = Field(12, ge=1, le=60)
    max_chars_per_email: int = Field(1500, ge=200, le=20000)
    json_mode: bool = True
    # Nombre max d'emails non lus envoyés à l'IA pour la priorisation.
    max_priority_candidates: int = Field(60, ge=5, le=500)

    def fast_model(self) -> str:
        return self.model_fast or self.model


class MailSettings(BaseModel):
    provider: Literal["demo", "imap"] = "demo"
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    username: str = ""
    password: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = ""  # vide = identique à l'IMAP
    smtp_password: str = ""
    from_name: str = ""
    from_address: str = ""
    drafts_folder: str = ""  # vide = détection automatique (\Drafts)
    sorted_root: str = ""  # dossier parent optionnel pour les dossiers créés


class ScopeSettings(BaseModel):
    since: Optional[date] = None
    until: Optional[date] = None  # inclusif
    folders: list[str] = Field(default_factory=lambda: ["INBOX"])


class ProfileSettings(BaseModel):
    """Contexte utilisateur injecté dans les prompts (priorisation, réponses)."""

    full_name: str = ""
    about: str = ""
    signature: str = ""
    language: str = "français"
    include_newsletters_in_priority: bool = False


class Settings(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    mail: MailSettings = Field(default_factory=MailSettings)
    scope: ScopeSettings = Field(default_factory=ScopeSettings)
    profile: ProfileSettings = Field(default_factory=ProfileSettings)
    theme: Literal["auto", "light", "dark"] = "auto"

    def public(self) -> dict:
        """Version sans secrets, pour l'interface."""
        data = self.model_dump(mode="json")
        for section, key in (("llm", "api_key"), ("mail", "password"), ("mail", "smtp_password")):
            if data[section][key]:
                data[section][key] = SECRET_MASK
        return data


class SettingsStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_dir() / "config.json"
        self._lock = threading.Lock()
        self._settings = self._load()

    def _load(self) -> Settings:
        if self.path.exists():
            try:
                return Settings.model_validate_json(self.path.read_text("utf-8"))
            except Exception:
                backup = self.path.with_suffix(".invalid.json")
                self.path.replace(backup)
        return Settings()

    @property
    def settings(self) -> Settings:
        return self._settings

    def update(self, patch: dict) -> Settings:
        """Fusionne un patch partiel ; les secrets masqués conservent leur valeur."""
        with self._lock:
            current = self._settings.model_dump(mode="json")
            for section, values in patch.items():
                if isinstance(values, dict) and isinstance(current.get(section), dict):
                    for key, value in values.items():
                        if value == SECRET_MASK:
                            continue
                        current[section][key] = value
                else:
                    current[section] = values
            self._settings = Settings.model_validate(current)
            self._save()
            return self._settings

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._settings.model_dump(mode="json"), indent=2, ensure_ascii=False), "utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)
