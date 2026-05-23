"""Testes do IngestionService — buffers, flush por tamanho/intervalo."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal

import pytest

from core.types import BookLevel, OrderBookSnapshot, Side, Trade
from data.ingestion import IngestionService


class FakeWSClient:
    """Mock do BinanceWSClient — emite snapshots/trades de listas pré-definidas."""

    def __init__(
        self,
        snaps: list[OrderBookSnapshot] | None = None,
        trades: list[Trade] | None = None,
    ) -> None:
        self._snaps = snaps or []
        self._trades = trades or []
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        await self._stopped.wait()

    async def stop(self) -> None:
        self._stopped.set()

    async def book_stream(self) -> AsyncIterator[OrderBookSnapshot]:
        for s in self._snaps:
            yield s

    async def trade_stream(self) -> AsyncIterator[Trade]:
        for t in self._trades:
            yield t


class FakeStore:
    def __init__(self) -> None:
        self.books: list[OrderBookSnapshot] = []
        self.trades: list[Trade] = []
        self.book_flushes = 0
        self.trade_flushes = 0

    async def insert_book_batch(self, snaps: Sequence[OrderBookSnapshot]) -> None:
        self.books.extend(snaps)
        self.book_flushes += 1

    async def insert_trade_batch(self, trades: Sequence[Trade]) -> None:
        self.trades.extend(trades)
        self.trade_flushes += 1


def _snap(seq: int) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ns=1_700_000_000_000_000_000 + seq,
        bids=(BookLevel(Decimal("50000"), Decimal("1")),),
        asks=(BookLevel(Decimal("50001"), Decimal("1")),),
        sequence=seq,
    )


def _trade(tid: int) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        timestamp_ns=1_700_000_000_000_000_000 + tid,
        price=Decimal("50000"),
        quantity=Decimal("0.01"),
        side=Side.BUY,
        trade_id=str(tid),
    )


class TestConstruction:
    def test_rejects_invalid_batch(self) -> None:
        with pytest.raises(ValueError, match="batch_size"):
            IngestionService(
                FakeWSClient(),  # type: ignore[arg-type]
                FakeStore(),  # type: ignore[arg-type]
                batch_size=0,
            )

    def test_rejects_invalid_flush(self) -> None:
        with pytest.raises(ValueError, match="flush_interval_s"):
            IngestionService(
                FakeWSClient(),  # type: ignore[arg-type]
                FakeStore(),  # type: ignore[arg-type]
                flush_interval_s=0,
            )


class TestFlushBySize:
    async def test_book_flush_when_batch_full(self) -> None:
        snaps = [_snap(i) for i in range(5)]
        ws = FakeWSClient(snaps=snaps)
        store = FakeStore()
        service = IngestionService(ws, store, batch_size=5, flush_interval_s=60)  # type: ignore[arg-type]
        task = asyncio.create_task(service.run())
        await asyncio.sleep(0.05)
        await service.stop()
        await task
        assert len(store.books) == 5
        assert store.book_flushes >= 1

    async def test_trade_flush_when_batch_full(self) -> None:
        trades = [_trade(i) for i in range(3)]
        ws = FakeWSClient(trades=trades)
        store = FakeStore()
        service = IngestionService(ws, store, batch_size=3, flush_interval_s=60)  # type: ignore[arg-type]
        task = asyncio.create_task(service.run())
        await asyncio.sleep(0.05)
        await service.stop()
        await task
        assert len(store.trades) == 3


class TestFlushOnStop:
    async def test_pending_buffer_flushed_on_stop(self) -> None:
        # batch_size grande para garantir que NÃO houve flush por tamanho.
        snaps = [_snap(i) for i in range(2)]
        trades = [_trade(i) for i in range(2)]
        ws = FakeWSClient(snaps=snaps, trades=trades)
        store = FakeStore()
        service = IngestionService(ws, store, batch_size=100, flush_interval_s=60)  # type: ignore[arg-type]
        task = asyncio.create_task(service.run())
        await asyncio.sleep(0.05)
        await service.stop()
        await task
        assert len(store.books) == 2
        assert len(store.trades) == 2


class TestPeriodicFlush:
    async def test_periodic_flush_below_batch_size(self) -> None:
        snaps = [_snap(0)]
        ws = FakeWSClient(snaps=snaps)
        store = FakeStore()
        service = IngestionService(ws, store, batch_size=100, flush_interval_s=0.05)  # type: ignore[arg-type]
        task = asyncio.create_task(service.run())
        await asyncio.sleep(0.15)  # >= 2 flush ticks
        await service.stop()
        await task
        assert len(store.books) == 1
        assert store.book_flushes >= 1
