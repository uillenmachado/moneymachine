"""Testes do AdaptiveGrid."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.types import BookLevel, OrderBookSnapshot, Side
from strategy.grid import AdaptiveGrid, GridParams

pytestmark = pytest.mark.unit


def _book(mid: str = "100", spread: str = "0.1") -> OrderBookSnapshot:
    m = Decimal(mid)
    s = Decimal(spread)
    return OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ns=0,
        bids=(BookLevel(price=m - s, quantity=Decimal("1")),),
        asks=(BookLevel(price=m + s, quantity=Decimal("1")),),
    )


def test_emits_2n_quotes() -> None:
    g = AdaptiveGrid("BTCUSDT", GridParams(levels=3, quote_size=Decimal("0.001")))
    quotes = g.on_book(_book())
    assert len(quotes) == 6  # 3 bids + 3 asks


def test_bids_below_asks_above_mid() -> None:
    g = AdaptiveGrid("BTCUSDT", GridParams(levels=2))
    quotes = g.on_book(_book(mid="100", spread="0"))
    bids = [q for q in quotes if q.side == Side.BUY]
    asks = [q for q in quotes if q.side == Side.SELL]
    assert all(b.price < Decimal("100") for b in bids)
    assert all(a.price > Decimal("100") for a in asks)


def test_levels_spaced_by_bps() -> None:
    g = AdaptiveGrid("BTCUSDT", GridParams(levels=2, spacing_bps=Decimal("10")))
    quotes = g.on_book(_book(mid="100", spread="0"))
    bids = sorted([q for q in quotes if q.side == Side.BUY], key=lambda q: q.level_index)
    # Nível 0 a 10 bps (0.1%) → 99.90; nível 1 a 20 bps → 99.80
    assert bids[0].price == Decimal("99.9000")
    assert bids[1].price == Decimal("99.8000")


def test_empty_book_returns_no_quotes() -> None:
    g = AdaptiveGrid("BTCUSDT", GridParams())
    empty = OrderBookSnapshot(symbol="BTCUSDT", timestamp_ns=0, bids=(), asks=())
    assert g.on_book(empty) == ()


def test_quote_size_consistent() -> None:
    g = AdaptiveGrid("BTCUSDT", GridParams(levels=2, quote_size=Decimal("0.005")))
    quotes = g.on_book(_book())
    assert all(q.quantity == Decimal("0.005") for q in quotes)


def test_on_fill_is_noop() -> None:
    g = AdaptiveGrid("BTCUSDT", GridParams())
    # Não deve levantar nem alterar nada (stateless).
    g.on_fill("BTCUSDT", Side.BUY, Decimal("100"), Decimal("0.001"))
