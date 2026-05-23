"""Testes do EventDrivenBacktest."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backtest.engine import EventDrivenBacktest
from core.types import BookLevel, OrderBookSnapshot, Side
from strategy import QuoteIntent
from strategy.grid import AdaptiveGrid, GridParams

pytestmark = pytest.mark.unit


def _book(ts: int, mid: str, spread: str = "0.10") -> OrderBookSnapshot:
    m = Decimal(mid)
    s = Decimal(spread)
    return OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ns=ts,
        bids=(BookLevel(price=m - s, quantity=Decimal("10")),),
        asks=(BookLevel(price=m + s, quantity=Decimal("10")),),
    )


def test_no_fills_when_spread_wide() -> None:
    strat = AdaptiveGrid("BTCUSDT", GridParams(levels=1, spacing_bps=Decimal("100")))
    bt = EventDrivenBacktest(strat)
    stats = bt.run([_book(0, "100"), _book(1, "100"), _book(2, "100")])
    assert stats.fills == 0
    assert stats.quotes_emitted == 6


def test_fills_when_price_crosses_bid() -> None:
    # Spacing 5 bps em mid 100 ⇒ bid em 99.95. Se mid descer e best_ask <= 99.95 ⇒ fill.
    strat = AdaptiveGrid("BTCUSDT", GridParams(levels=1, spacing_bps=Decimal("5")))
    bt = EventDrivenBacktest(strat, maker_fee=Decimal("0"))
    # Primeiro snapshot: emite quotes a 99.95 / 100.05.
    # Segundo: ask cai para 99.90 ⇒ bid 99.95 vira fill.
    stats = bt.run(
        [
            _book(0, "100", spread="0.05"),
            _book(1, "99.85", spread="0.05"),
        ]
    )
    assert stats.fills >= 1


def test_realized_pnl_on_round_trip() -> None:
    """Mecanismo de PnL realized -- usa estrategia trivial que compra e depois vende."""

    class OneShotStrategy:
        def __init__(self) -> None:
            self.tick = 0

        def on_book(self, book: OrderBookSnapshot) -> tuple[QuoteIntent, ...]:
            _ = book
            self.tick += 1
            if self.tick == 1:
                return (QuoteIntent("BTCUSDT", Side.BUY, Decimal("99.95"), Decimal("1"), 0),)
            if self.tick == 2:
                return (QuoteIntent("BTCUSDT", Side.SELL, Decimal("100.05"), Decimal("1"), 0),)
            return ()

        def on_fill(self, *_args: object, **_kw: object) -> None:
            return

    bt = EventDrivenBacktest(OneShotStrategy(), maker_fee=Decimal("0"))
    bt.run(
        [
            _book(0, "100", spread="0.05"),  # emite buy 99.95
            _book(1, "99.85", spread="0.05"),  # ask 99.90 ≤ 99.95 -> compra. emite sell 100.05
            _book(2, "100.15", spread="0.05"),  # bid 100.10 ≥ 100.05 -> vende
        ]
    )
    assert bt.stats.inventory == Decimal("0")
    assert bt.stats.realized_pnl_usd == Decimal("0.10")


def test_fees_accumulate() -> None:
    strat = AdaptiveGrid(
        "BTCUSDT",
        GridParams(levels=1, spacing_bps=Decimal("5"), quote_size=Decimal("1")),
    )
    bt = EventDrivenBacktest(strat, maker_fee=Decimal("0.0001"))
    bt.run(
        [
            _book(0, "100", spread="0.05"),
            _book(1, "99.85", spread="0.05"),
        ]
    )
    assert bt.stats.fees_paid_usd > Decimal("0")


def test_timeline_populated() -> None:
    strat = AdaptiveGrid("BTCUSDT", GridParams(levels=1))
    bt = EventDrivenBacktest(strat)
    stats = bt.run([_book(i, "100") for i in range(5)])
    assert len(stats.timeline) == 5


def test_inventory_tracks_buys() -> None:
    strat = AdaptiveGrid(
        "BTCUSDT",
        GridParams(levels=1, spacing_bps=Decimal("5"), quote_size=Decimal("0.5")),
    )
    bt = EventDrivenBacktest(strat, maker_fee=Decimal("0"))
    bt.run(
        [
            _book(0, "100", spread="0.05"),
            _book(1, "99.85", spread="0.05"),  # compra 0.5
        ]
    )
    assert bt.stats.inventory == Decimal("0.5")
    # Avg entry deve ser o preço do bid (99.95)
    assert bt.stats.avg_entry == Decimal("99.95")


def test_side_buy_only_fills_against_ask() -> None:
    """Sanity: fill rule respeita o lado."""
    strat = AdaptiveGrid("BTCUSDT", GridParams(levels=1, spacing_bps=Decimal("5")))
    bt = EventDrivenBacktest(strat)
    # Book estático: nenhum cruzamento ⇒ zero fills.
    stats = bt.run([_book(i, "100", spread="0.50") for i in range(3)])
    assert stats.fills == 0
    # Confirma quotes existem
    assert stats.quotes_emitted == 6
    # Confirma sides emitidos
    quotes = strat.on_book(_book(0, "100"))
    assert {Side.BUY, Side.SELL} == {q.side for q in quotes}
