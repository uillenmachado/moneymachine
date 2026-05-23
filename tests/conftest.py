"""Fixtures globais de teste."""

from __future__ import annotations

import pytest

from core import config


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante que testes não usem .env real."""
    monkeypatch.setenv("MDD_ENV", "test")
    monkeypatch.setenv("MDD_LOG_LEVEL", "WARNING")
    config.get_settings.cache_clear()
