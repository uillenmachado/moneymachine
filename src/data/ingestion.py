"""Serviço de ingestão: WS Binance → buffers → TimescaleDB.

Mantém dois buffers (book + trades) e faz flush por tamanho OU intervalo,
o que vier primeiro. Métricas em `metrics`.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import structlog

from core.types import OrderBookSnapshot, Trade

if TYPE_CHECKING:
    from data.binance_ws import BinanceWSClient
    from data.storage import TimescaleStore

logger = structlog.get_logger(__name__)


class IngestionService:
    """Consome streams do `BinanceWSClient` e persiste em batches."""

    def __init__(
        self,
        client: BinanceWSClient,
        store: TimescaleStore,
        *,
        batch_size: int = 50,
        flush_interval_s: float = 1.0,
    ) -> None:
        if batch_size <= 0:
            msg = "batch_size must be > 0"
            raise ValueError(msg)
        if flush_interval_s <= 0:
            msg = "flush_interval_s must be > 0"
            raise ValueError(msg)
        self._client = client
        self._store = store
        self._batch_size = batch_size
        self._flush_interval_s = flush_interval_s
        self._book_buf: list[OrderBookSnapshot] = []
        self._trade_buf: list[Trade] = []
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        tasks = [
            asyncio.create_task(self._client.run(), name="ws_client"),
            asyncio.create_task(self._consume_books(), name="consume_books"),
            asyncio.create_task(self._consume_trades(), name="consume_trades"),
            asyncio.create_task(self._periodic_flush(), name="periodic_flush"),
        ]
        try:
            await self._stopped.wait()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self._flush_all()

    async def stop(self) -> None:
        self._stopped.set()
        await self._client.stop()

    async def _consume_books(self) -> None:
        async for snap in self._client.book_stream():
            self._book_buf.append(snap)
            if len(self._book_buf) >= self._batch_size:
                await self._flush_books()

    async def _consume_trades(self) -> None:
        async for trade in self._client.trade_stream():
            self._trade_buf.append(trade)
            if len(self._trade_buf) >= self._batch_size:
                await self._flush_trades()

    async def _periodic_flush(self) -> None:
        while not self._stopped.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stopped.wait(),
                    timeout=self._flush_interval_s,
                )
            await self._flush_all()

    async def _flush_books(self) -> None:
        if not self._book_buf:
            return
        batch = self._book_buf
        self._book_buf = []
        await self._store.insert_book_batch(batch)
        logger.debug("flushed_books", n=len(batch))

    async def _flush_trades(self) -> None:
        if not self._trade_buf:
            return
        batch = self._trade_buf
        self._trade_buf = []
        await self._store.insert_trade_batch(batch)
        logger.debug("flushed_trades", n=len(batch))

    async def _flush_all(self) -> None:
        await self._flush_books()
        await self._flush_trades()
