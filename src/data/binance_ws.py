"""Cliente WebSocket para Binance Spot (combined streams).

Suporta `<symbol>@depth20@100ms` (partial book top-20) e `<symbol>@trade`.
Implementa reconexão com backoff exponencial e validação de continuidade
via `SequenceValidator` / `EventTimeValidator`.

Referência: https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import msgspec
import structlog
import websockets
from websockets.asyncio.client import ClientConnection

from core.types import BookLevel, OrderBookSnapshot, Side, Trade
from data.gap_detector import (
    EventTimeValidator,
    GapDetectedError,
    SequenceValidator,
    StalenessMonitor,
)
from metrics import (
    WS_EVENT_LATENCY_MS,
    WS_MESSAGES_RECEIVED,
    WS_RECONNECTS,
)

logger = structlog.get_logger(__name__)

MAINNET_URL = "wss://stream.binance.com:9443"
TESTNET_URL = "wss://stream.testnet.binance.vision"

_decoder = msgspec.json.Decoder()


class BinanceWSClient:
    """Cliente WS de Binance Spot para um conjunto de símbolos.

    Cada instância gerencia uma única conexão multiplexada (combined stream).
    Snapshots de livro e trades são entregues via `book_stream()` / `trade_stream()`
    como async iterators sobre `asyncio.Queue`.
    """

    _MAX_BACKOFF_S = 30.0
    _PING_INTERVAL_S = 20.0
    _PING_TIMEOUT_S = 10.0
    _QUEUE_MAX = 4096

    def __init__(
        self,
        symbols: list[str],
        *,
        book_depth: int = 20,
        update_speed_ms: int = 100,
        with_trades: bool = True,
        testnet: bool = True,
    ) -> None:
        if not symbols:
            msg = "symbols must not be empty"
            raise ValueError(msg)
        if book_depth not in (5, 10, 20):
            msg = "book_depth must be 5, 10 or 20"
            raise ValueError(msg)
        if update_speed_ms not in (100, 1000):
            msg = "update_speed_ms must be 100 or 1000"
            raise ValueError(msg)
        self._symbols = [s.lower() for s in symbols]
        self._book_depth = book_depth
        self._update_speed_ms = update_speed_ms
        self._with_trades = with_trades
        self._base_url = TESTNET_URL if testnet else MAINNET_URL
        self._book_queue: asyncio.Queue[OrderBookSnapshot] = asyncio.Queue(
            maxsize=self._QUEUE_MAX,
        )
        self._trade_queue: asyncio.Queue[Trade] = asyncio.Queue(maxsize=self._QUEUE_MAX)
        self._stopped = asyncio.Event()
        self._seq_validators: dict[str, SequenceValidator] = {}
        self._time_validators: dict[str, EventTimeValidator] = {}
        self._staleness: dict[str, StalenessMonitor] = {}

    def _build_url(self) -> str:
        streams: list[str] = []
        for sym in self._symbols:
            streams.append(f"{sym}@depth{self._book_depth}@{self._update_speed_ms}ms")
            if self._with_trades:
                streams.append(f"{sym}@trade")
        return f"{self._base_url}/stream?streams={'/'.join(streams)}"

    async def run(self) -> None:
        """Loop principal: conecta, processa, reconecta com backoff."""
        backoff = 1.0
        while not self._stopped.is_set():
            try:
                await self._connect_and_consume()
                backoff = 1.0
            except (
                websockets.ConnectionClosed,
                GapDetectedError,
                TimeoutError,
                OSError,
            ) as exc:
                reason = type(exc).__name__
                WS_RECONNECTS.labels(venue="binance", reason=reason).inc()
                logger.warning(
                    "ws_disconnect",
                    reason=reason,
                    error=str(exc),
                    backoff_s=backoff,
                )
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stopped.wait(), timeout=backoff)
                backoff = min(backoff * 2, self._MAX_BACKOFF_S)

    async def _connect_and_consume(self) -> None:
        url = self._build_url()
        logger.info("ws_connecting", url=url, symbols=self._symbols)
        async with websockets.connect(
            url,
            ping_interval=self._PING_INTERVAL_S,
            ping_timeout=self._PING_TIMEOUT_S,
            max_size=2**20,
        ) as ws:
            logger.info("ws_connected")
            await self._consume(ws)

    async def _consume(self, ws: ClientConnection) -> None:
        async for raw in ws:
            if self._stopped.is_set():
                return
            payload = _decoder.decode(raw)
            stream = payload.get("stream")
            data = payload.get("data")
            if not isinstance(stream, str) or not isinstance(data, dict):
                continue
            WS_MESSAGES_RECEIVED.labels(stream=stream).inc()
            self._touch_staleness(stream)
            if "@depth" in stream:
                snapshot = self._parse_book(stream, data)
                if snapshot is not None:
                    await self._enqueue(self._book_queue, snapshot)
            elif stream.endswith("@trade"):
                trade = self._parse_trade(stream, data)
                if trade is not None:
                    await self._enqueue(self._trade_queue, trade)

    def _touch_staleness(self, stream: str) -> None:
        mon = self._staleness.get(stream)
        if mon is None:
            mon = StalenessMonitor(stream)
            self._staleness[stream] = mon
        mon.touch()

    def _parse_book(self, stream: str, data: dict[str, Any]) -> OrderBookSnapshot | None:
        last_update_id = data.get("lastUpdateId")
        bids_raw = data.get("bids")
        asks_raw = data.get("asks")
        if not isinstance(last_update_id, int) or not isinstance(bids_raw, list):
            return None
        if not isinstance(asks_raw, list):
            return None
        validator = self._seq_validators.get(stream)
        if validator is None:
            validator = SequenceValidator(stream=stream)
            self._seq_validators[stream] = validator
        validator.check(last_update_id)
        symbol = stream.split("@", 1)[0].upper()
        return OrderBookSnapshot(
            symbol=symbol,
            timestamp_ns=time.time_ns(),
            bids=tuple(BookLevel(Decimal(p), Decimal(q)) for p, q in bids_raw),
            asks=tuple(BookLevel(Decimal(p), Decimal(q)) for p, q in asks_raw),
            sequence=last_update_id,
        )

    def _parse_trade(self, stream: str, data: dict[str, Any]) -> Trade | None:
        event_ms = data.get("E")
        trade_ms = data.get("T")
        price = data.get("p")
        qty = data.get("q")
        trade_id = data.get("t")
        is_buyer_maker = data.get("m")
        symbol = data.get("s")
        if not isinstance(event_ms, int) or not isinstance(trade_ms, int):
            return None
        if not isinstance(price, str) or not isinstance(qty, str):
            return None
        if not isinstance(symbol, str) or not isinstance(is_buyer_maker, bool):
            return None
        validator = self._time_validators.get(stream)
        if validator is None:
            validator = EventTimeValidator(stream=stream)
            self._time_validators[stream] = validator
        validator.check(event_ms)
        latency_ms = max(0, int(time.time() * 1000) - event_ms)
        WS_EVENT_LATENCY_MS.labels(stream=stream).observe(latency_ms)
        # Binance: m=True significa que o buyer é o maker -> trade foi um SELL agressivo.
        aggressor = Side.SELL if is_buyer_maker else Side.BUY
        return Trade(
            symbol=symbol,
            timestamp_ns=trade_ms * 1_000_000,
            price=Decimal(price),
            quantity=Decimal(qty),
            side=aggressor,
            trade_id=str(trade_id),
        )

    async def _enqueue(self, queue: asyncio.Queue[Any], item: Any) -> None:
        if queue.full():
            # Drop o mais antigo para preservar freshness do hot path.
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        await queue.put(item)

    async def book_stream(self) -> AsyncIterator[OrderBookSnapshot]:
        while not self._stopped.is_set():
            yield await self._book_queue.get()

    async def trade_stream(self) -> AsyncIterator[Trade]:
        while not self._stopped.is_set():
            yield await self._trade_queue.get()

    async def stop(self) -> None:
        self._stopped.set()
