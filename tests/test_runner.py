"""Testes do TradingRunner — usa FakeWS e FakeREST (zero rede)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest

from core.config import RiskSettings, Settings
from core.runner import TradingRunner
from core.types import BookLevel, OrderBookSnapshot
from oms.binance_rest import BinanceRESTError
from strategy.grid import AdaptiveGrid, GridParams

pytestmark = pytest.mark.unit


class FakeWS:
    def __init__(self, books: list[OrderBookSnapshot]) -> None:
        self._books = books
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        # Mantém vivo até stop ser chamado.
        await self._stop_event.wait()

    async def book_stream(self) -> AsyncIterator[OrderBookSnapshot]:
        for b in self._books:
            yield b
            await asyncio.sleep(0)

    async def stop(self) -> None:
        self._stop_event.set()


class FakeREST:
    def __init__(self) -> None:
        self.placed: list[dict[str, Any]] = []
        self.cancel_all_calls: list[str] = []
        self.next_error: BinanceRESTError | None = None

    async def place_order(self, **params: Any) -> dict[str, Any]:
        if self.next_error is not None:
            err = self.next_error
            self.next_error = None
            raise err
        self.placed.append(params)
        return {"orderId": len(self.placed), "status": "NEW", "executedQty": "0"}

    async def cancel_order(self, **_params: Any) -> dict[str, Any]:
        return {"status": "CANCELED"}

    async def cancel_all(self, symbol: str) -> list[dict[str, Any]]:
        self.cancel_all_calls.append(symbol)
        return []

    async def open_orders(self, _symbol: str | None = None) -> list[dict[str, Any]]:
        return []

    async def close(self) -> None:
        return


def _settings() -> Settings:
    return Settings(
        env="development",
        capital_usd=10000.0,
        risk=RiskSettings(
            max_daily_drawdown_pct=3.0,
            max_position_per_side_pct=30.0,
        ),
    )


def _book(mid: str = "100") -> OrderBookSnapshot:
    m = Decimal(mid)
    return OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ns=0,
        bids=(BookLevel(price=m - Decimal("0.05"), quantity=Decimal("1")),),
        asks=(BookLevel(price=m + Decimal("0.05"), quantity=Decimal("1")),),
    )


async def test_runner_submits_quotes_for_each_book() -> None:
    ws = FakeWS([_book("100"), _book("100.10")])
    rest = FakeREST()
    runner = TradingRunner(
        settings=_settings(),
        ws_client=ws,  # type: ignore[arg-type]
        rest_client=rest,  # type: ignore[arg-type]
        symbols=["BTCUSDT"],
        strategies={"BTCUSDT": AdaptiveGrid("BTCUSDT", GridParams(levels=2))},
    )
    await runner.run()
    # 2 books * 4 quotes (2 levels * 2 sides) = 8 placements
    assert len(rest.placed) == 8
    # cancel_all chamado a cada book + 1 shutdown
    assert len(rest.cancel_all_calls) >= 2


async def test_runner_skips_when_halted() -> None:
    ws = FakeWS([_book("100"), _book("100.10")])
    rest = FakeREST()
    runner = TradingRunner(
        settings=_settings(),
        ws_client=ws,  # type: ignore[arg-type]
        rest_client=rest,  # type: ignore[arg-type]
        symbols=["BTCUSDT"],
    )
    runner._risk.trigger_halt("test")
    await runner.run()
    # Nenhum place — só cancel_all.
    assert rest.placed == []


async def test_runner_tolerates_exchange_error() -> None:
    ws = FakeWS([_book("100")])
    rest = FakeREST()
    rest.next_error = BinanceRESTError(-1013, "filter failure", 400)
    runner = TradingRunner(
        settings=_settings(),
        ws_client=ws,  # type: ignore[arg-type]
        rest_client=rest,  # type: ignore[arg-type]
        symbols=["BTCUSDT"],
        strategies={"BTCUSDT": AdaptiveGrid("BTCUSDT", GridParams(levels=1))},
    )
    # Não deve levantar.
    await runner.run()
