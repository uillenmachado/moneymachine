"""Smoke tests da Fase 0 — validam que o pacote importa e a configuração carrega."""

from __future__ import annotations

import pytest

from core import __version__
from core.config import Environment, get_settings


@pytest.mark.unit
def test_version_importable() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") == 2


@pytest.mark.unit
def test_settings_load() -> None:
    s = get_settings()
    assert s.env == Environment.TEST
    assert s.capital_usd > 0
    assert s.risk.max_daily_drawdown_pct > 0


@pytest.mark.unit
def test_settings_dsn_format() -> None:
    dsn = get_settings().db.dsn
    assert dsn.startswith("postgresql+asyncpg://")
    assert "mdd" in dsn
