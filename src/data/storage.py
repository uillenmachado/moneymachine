"""Persistência de market data em TimescaleDB.

Usa asyncpg direto (sem ORM) para minimizar latência no hot path.
Schema definido em `infra/timescaledb/init/01_schema.sql`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import asyncpg
import msgspec
import structlog

from core.types import OrderBookSnapshot, Trade

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger(__name__)

_INSERT_BOOK_SQL = """
INSERT INTO book_snapshots (ts, symbol, bids, asks, sequence)
VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)
"""

_INSERT_TRADE_SQL = """
INSERT INTO trades_tape (ts, symbol, price, quantity, side, trade_id)
VALUES ($1, $2, $3, $4, $5, $6)
"""

_json_encoder = msgspec.json.Encoder()


def _encode_levels(levels: Sequence[object]) -> str:
    payload = [[str(lvl.price), str(lvl.quantity)] for lvl in levels]  # type: ignore[attr-defined]
    return _json_encoder.encode(payload).decode("utf-8")


def _ts_from_ns(ts_ns: int) -> datetime:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=UTC)


class TimescaleStore:
    """Wrapper assíncrono sobre um pool asyncpg para hypertables."""

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 4) -> None:
        # asyncpg quer dsn no formato postgresql:// (sem +asyncpg).
        self._dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
        )
        logger.info("timescale_connected", min_size=self._min_size, max_size=self._max_size)

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None

    async def insert_book(self, snap: OrderBookSnapshot) -> None:
        if self._pool is None:
            msg = "store not connected"
            raise RuntimeError(msg)
        await self._pool.execute(
            _INSERT_BOOK_SQL,
            _ts_from_ns(snap.timestamp_ns),
            snap.symbol,
            _encode_levels(snap.bids),
            _encode_levels(snap.asks),
            snap.sequence,
        )

    async def insert_trade(self, trade: Trade) -> None:
        if self._pool is None:
            msg = "store not connected"
            raise RuntimeError(msg)
        await self._pool.execute(
            _INSERT_TRADE_SQL,
            _ts_from_ns(trade.timestamp_ns),
            trade.symbol,
            trade.price,
            trade.quantity,
            trade.side.value,
            trade.trade_id,
        )

    async def insert_book_batch(self, snaps: Sequence[OrderBookSnapshot]) -> None:
        if not snaps:
            return
        if self._pool is None:
            msg = "store not connected"
            raise RuntimeError(msg)
        rows = [
            (
                _ts_from_ns(s.timestamp_ns),
                s.symbol,
                _encode_levels(s.bids),
                _encode_levels(s.asks),
                s.sequence,
            )
            for s in snaps
        ]
        await self._pool.executemany(_INSERT_BOOK_SQL, rows)

    async def insert_trade_batch(self, trades: Sequence[Trade]) -> None:
        if not trades:
            return
        if self._pool is None:
            msg = "store not connected"
            raise RuntimeError(msg)
        rows = [
            (
                _ts_from_ns(t.timestamp_ns),
                t.symbol,
                t.price,
                t.quantity,
                t.side.value,
                t.trade_id,
            )
            for t in trades
        ]
        await self._pool.executemany(_INSERT_TRADE_SQL, rows)


__all__ = ["TimescaleStore", "_encode_levels", "_ts_from_ns"]


# Marca uso aparente para o type-checker (Decimal é usado implicitamente via Trade).
_ = Decimal
