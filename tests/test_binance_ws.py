"""Testes unit do BinanceWSClient (parsing + URL building)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.types import Side
from data.binance_ws import MAINNET_URL, TESTNET_URL, BinanceWSClient
from data.gap_detector import GapDetectedError


def make_client(**kwargs: object) -> BinanceWSClient:
    defaults: dict[str, object] = {"symbols": ["BTCUSDT"], "testnet": True}
    defaults.update(kwargs)
    return BinanceWSClient(**defaults)  # type: ignore[arg-type]


class TestConstruction:
    def test_rejects_empty_symbols(self) -> None:
        with pytest.raises(ValueError, match="symbols"):
            BinanceWSClient(symbols=[])

    def test_rejects_invalid_depth(self) -> None:
        with pytest.raises(ValueError, match="book_depth"):
            BinanceWSClient(symbols=["BTCUSDT"], book_depth=15)

    def test_rejects_invalid_speed(self) -> None:
        with pytest.raises(ValueError, match="update_speed_ms"):
            BinanceWSClient(symbols=["BTCUSDT"], update_speed_ms=500)


class TestURLBuilding:
    def test_testnet_url(self) -> None:
        c = make_client(testnet=True)
        url = c._build_url()
        assert url.startswith(TESTNET_URL)
        assert "btcusdt@depth20@100ms" in url
        assert "btcusdt@trade" in url

    def test_mainnet_url(self) -> None:
        c = make_client(testnet=False)
        url = c._build_url()
        assert url.startswith(MAINNET_URL)

    def test_without_trades(self) -> None:
        c = make_client(with_trades=False)
        url = c._build_url()
        assert "@trade" not in url

    def test_multi_symbol(self) -> None:
        c = make_client(symbols=["BTCUSDT", "ETHUSDT"])
        url = c._build_url()
        assert "btcusdt@depth20@100ms" in url
        assert "ethusdt@depth20@100ms" in url


class TestParseBook:
    def test_parses_valid_payload(self) -> None:
        c = make_client()
        snap = c._parse_book(
            "btcusdt@depth20@100ms",
            {
                "lastUpdateId": 42,
                "bids": [["50000.00", "1.5"], ["49999.50", "0.5"]],
                "asks": [["50001.00", "2.0"]],
            },
        )
        assert snap is not None
        assert snap.symbol == "BTCUSDT"
        assert snap.sequence == 42
        assert snap.best_bid == Decimal("50000.00")
        assert snap.best_ask == Decimal("50001.00")
        assert snap.spread == Decimal("1.00")
        assert len(snap.bids) == 2

    def test_returns_none_on_missing_fields(self) -> None:
        c = make_client()
        assert c._parse_book("btcusdt@depth20@100ms", {}) is None

    def test_rejects_sequence_regression(self) -> None:
        c = make_client()
        payload: dict[str, object] = {
            "lastUpdateId": 10,
            "bids": [["1", "1"]],
            "asks": [["2", "1"]],
        }
        c._parse_book("s", payload)
        with pytest.raises(GapDetectedError):
            c._parse_book("s", {**payload, "lastUpdateId": 5})


class TestParseTrade:
    def test_parses_aggressor_buy(self) -> None:
        c = make_client()
        trade = c._parse_trade(
            "btcusdt@trade",
            {
                "e": "trade",
                "E": 1_700_000_000_000,
                "s": "BTCUSDT",
                "t": 99,
                "p": "50000.00",
                "q": "0.01",
                "T": 1_700_000_000_000,
                "m": False,  # buyer NÃO é maker -> aggressor é buyer
            },
        )
        assert trade is not None
        assert trade.symbol == "BTCUSDT"
        assert trade.price == Decimal("50000.00")
        assert trade.quantity == Decimal("0.01")
        assert trade.side is Side.BUY
        assert trade.trade_id == "99"

    def test_parses_aggressor_sell(self) -> None:
        c = make_client()
        trade = c._parse_trade(
            "btcusdt@trade",
            {
                "e": "trade",
                "E": 1_700_000_000_000,
                "s": "BTCUSDT",
                "t": 100,
                "p": "50000.00",
                "q": "0.01",
                "T": 1_700_000_000_000,
                "m": True,
            },
        )
        assert trade is not None
        assert trade.side is Side.SELL

    def test_returns_none_on_missing_fields(self) -> None:
        c = make_client()
        assert c._parse_trade("btcusdt@trade", {}) is None
