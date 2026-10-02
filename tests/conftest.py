import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fake_llm import make_app  # noqa: E402
from trieurmail.config import SettingsStore  # noqa: E402
from trieurmail.db import Database  # noqa: E402
from trieurmail.llm.client import LLMClient  # noqa: E402
from trieurmail.services.context import AppContext  # noqa: E402


@pytest.fixture
def fake_llm_app():
    return make_app()


@pytest.fixture
def ctx(tmp_path, monkeypatch, fake_llm_app):
    monkeypatch.setenv("TRIEURMAIL_HOME", str(tmp_path))
    store = SettingsStore(tmp_path / "config.json")
    store.update({"llm": {"base_url": "http://fake/v1", "model": "fake-large", "model_fast": "fake-small"},
                  "scope": {"folders": ["INBOX"], "since": None, "until": None}})
    context = AppContext(store, Database(tmp_path / "cache.sqlite"))
    context._llm = LLMClient(store.settings.llm, context.db, transport=httpx.ASGITransport(app=fake_llm_app))
    return context
