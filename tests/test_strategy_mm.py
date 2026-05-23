"""Testes do AvellanedaStoikov MM."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.types import BookLevel, OrderBookSnapshot, Side
from strategy.mm import AvellanedaStoikov, MMParams

pytestmark = pytest.mark.unit


def _book(mid: str = "100", bid_qty: str = "1", ask_qty: str = "1") -> OrderBookSnapshot:
    m = Decimal(mid)
    return OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ns=0,
        bids=(BookLevel(price=m - Decimal("0.05"), quantity=Decimal(bid_qty)),),
        asks=(BookLevel(price=m + Decimal("0.05"), quantity=Decimal(ask_qty)),),
    )


def _params(**kw: object) -> MMParams:
    defaults: dict[str, object] = {
        "gamma": 0.1,
        "kappa": 1.5,
        "horizon_s": 60.0,
        "vol_window": 10,
        "ofi_lambda_bps": 2.0,
        "quote_size": Decimal("0.001"),
        "max_inventory": Decimal("0.05"),
    }
    defaults.update(kw)
    return MMParams(**defaults)  # type: ignore[arg-type]


def test_warmup_returns_no_quotes() -> None:
    mm = AvellanedaStoikov("BTCUSDT", _params())
    # Primeiro snapshot: sem histórico de vol ⇒ sem quotes.
    assert mm.on_book(_book()) == ()


def test_emits_bid_and_ask_after_warmup() -> None:
    mm = AvellanedaStoikov("BTCUSDT", _params())
    # Aquecimento da janela de vol.
    for i in range(5):
        mm.on_book(_book(mid=str(100 + i * 0.01)))
    quotes = mm.on_book(_book(mid="100.10"))
    sides = {q.side for q in quotes}
    assert Side.BUY in sides
    assert Side.SELL in sides


def test_long_inventory_skips_bid() -> None:
    mm = AvellanedaStoikov("BTCUSDT", _params(max_inventory=Decimal("0.01")))
    # Aquece.
    for i in range(5):
        mm.on_book(_book(mid=str(100 + i * 0.01)))
    # Inventário no cap → não cota mais bid.
    mm.on_fill("BTCUSDT", Side.BUY, Decimal("100"), Decimal("0.01"))
    quotes = mm.on_book(_book(mid="100.10"))
    assert all(q.side == Side.SELL for q in quotes)


def test_short_inventory_skips_ask() -> None:
    mm = AvellanedaStoikov("BTCUSDT", _params(max_inventory=Decimal("0.01")))
    for i in range(5):
        mm.on_book(_book(mid=str(100 + i * 0.01)))
    mm.on_fill("BTCUSDT", Side.SELL, Decimal("100"), Decimal("0.01"))
    quotes = mm.on_book(_book(mid="100.10"))
    assert all(q.side == Side.BUY for q in quotes)


def test_inventory_tracks_fills() -> None:
    mm = AvellanedaStoikov("BTCUSDT", _params())
    mm.on_fill("BTCUSDT", Side.BUY, Decimal("100"), Decimal("0.02"))
    mm.on_fill("BTCUSDT", Side.SELL, Decimal("100"), Decimal("0.01"))
    assert mm.inventory == Decimal("0.01")


def test_bid_below_ask() -> None:
    mm = AvellanedaStoikov("BTCUSDT", _params())
    for i in range(8):
        mm.on_book(_book(mid=str(100 + i * 0.02)))
    quotes = mm.on_book(_book(mid="100.20"))
    bid = next(q for q in quotes if q.side == Side.BUY)
    ask = next(q for q in quotes if q.side == Side.SELL)
    assert bid.price < ask.price


def test_empty_book_returns_no_quotes() -> None:
    mm = AvellanedaStoikov("BTCUSDT", _params())
    empty = OrderBookSnapshot(symbol="BTCUSDT", timestamp_ns=0, bids=(), asks=())
    assert mm.on_book(empty) == ()
