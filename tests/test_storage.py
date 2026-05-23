"""Testes unit do helper de encoding do storage (sem DB)."""

from __future__ import annotations

import json
from datetime import UTC
from decimal import Decimal

from core.types import BookLevel
from data.storage import _encode_levels, _ts_from_ns


def test_encode_levels_preserves_decimal_strings() -> None:
    levels = (
        BookLevel(Decimal("50000.12345678"), Decimal("0.001")),
        BookLevel(Decimal("49999"), Decimal("2.5")),
    )
    payload = json.loads(_encode_levels(levels))
    assert payload == [["50000.12345678", "0.001"], ["49999", "2.5"]]


def test_ts_from_ns_returns_utc() -> None:
    ts = _ts_from_ns(1_700_000_000_000_000_000)
    assert ts.tzinfo is UTC
    assert ts.year >= 2023
