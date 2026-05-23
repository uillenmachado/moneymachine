"""Testa tipos do domain — preço/quantidade em Decimal, snapshots imutáveis."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.types import BookLevel, OrderBookSnapshot


@pytest.mark.unit
def test_book_snapshot_mid_and_spread() -> None:
    snap = OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ns=1_700_000_000_000_000_000,
        bids=(BookLevel(Decimal("100"), Decimal("1")),),
        asks=(BookLevel(Decimal("102"), Decimal("1")),),
    )
    assert snap.best_bid == Decimal("100")
    assert snap.best_ask == Decimal("102")
    assert snap.mid_price == Decimal("101")
    assert snap.spread == Decimal("2")


@pytest.mark.unit
def test_book_snapshot_empty_side_returns_none() -> None:
    snap = OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ns=0,
        bids=(),
        asks=(BookLevel(Decimal("102"), Decimal("1")),),
    )
    assert snap.best_bid is None
    assert snap.mid_price is None
    assert snap.spread is None
