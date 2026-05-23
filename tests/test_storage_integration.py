"""Teste de integração: TimescaleStore contra container TimescaleDB real.

Roda APENAS se `MDD_TEST_DSN` estiver definida OU se o default
`postgresql://mdd:change_me_in_local_only@localhost:5432/mdd` aceitar conexão.

Execução:
    docker compose up -d timescaledb
    python -m uv run pytest -m integration -q
"""

from __future__ import annotations

import os
from decimal import Decimal

import asyncpg
import pytest

from core.types import BookLevel, OrderBookSnapshot, Side, Trade
from data.storage import TimescaleStore

pytestmark = pytest.mark.integration

_DEFAULT_DSN = "postgresql://mdd:change_me_in_local_only@localhost:5432/mdd"


def _dsn() -> str:
    return os.environ.get("MDD_TEST_DSN", _DEFAULT_DSN)


@pytest.fixture
async def store() -> TimescaleStore:  # type: ignore[misc]
    dsn = _dsn()
    try:
        conn = await asyncpg.connect(dsn, timeout=2.0)
    except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
        pytest.skip(f"TimescaleDB indisponível em {dsn}: {exc}")
    await conn.close()

    s = TimescaleStore(dsn, min_size=1, max_size=2)
    await s.connect()
    yield s
    await s.close()


@pytest.fixture
async def cleanup_symbol() -> str:  # type: ignore[misc]
    symbol = "MDDTEST"
    yield symbol
    # Limpa após o teste — usa pool próprio para não depender da fixture store.
    conn = await asyncpg.connect(_dsn(), timeout=2.0)
    try:
        await conn.execute("DELETE FROM book_snapshots WHERE symbol = $1", symbol)
        await conn.execute("DELETE FROM trades_tape WHERE symbol = $1", symbol)
    finally:
        await conn.close()


def _snap(symbol: str, ts_ns: int, sequence: int) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol=symbol,
        timestamp_ns=ts_ns,
        bids=(BookLevel(Decimal("50000.12345678"), Decimal("0.1")),),
        asks=(BookLevel(Decimal("50001.87654321"), Decimal("0.2")),),
        sequence=sequence,
    )


def _trade(symbol: str, ts_ns: int, tid: str) -> Trade:
    return Trade(
        symbol=symbol,
        timestamp_ns=ts_ns,
        price=Decimal("50000.5"),
        quantity=Decimal("0.01"),
        side=Side.BUY,
        trade_id=tid,
    )


async def test_insert_book_roundtrip(store: TimescaleStore, cleanup_symbol: str) -> None:
    snap = _snap(cleanup_symbol, ts_ns=1_700_000_000_000_000_000, sequence=42)
    await store.insert_book(snap)

    conn = await asyncpg.connect(_dsn(), timeout=2.0)
    try:
        row = await conn.fetchrow(
            "SELECT symbol, sequence, bids, asks FROM book_snapshots WHERE symbol = $1",
            cleanup_symbol,
        )
    finally:
        await conn.close()

    assert row is not None
    assert row["symbol"] == cleanup_symbol
    assert row["sequence"] == 42
    # JSONB volta como string serializada — basta confirmar que o preço sobreviveu.
    assert "50000.12345678" in row["bids"]
    assert "50001.87654321" in row["asks"]


async def test_insert_trade_roundtrip(store: TimescaleStore, cleanup_symbol: str) -> None:
    trade = _trade(cleanup_symbol, ts_ns=1_700_000_000_000_000_000, tid="t-1")
    await store.insert_trade(trade)

    conn = await asyncpg.connect(_dsn(), timeout=2.0)
    try:
        row = await conn.fetchrow(
            "SELECT price, quantity, side, trade_id FROM trades_tape WHERE symbol = $1",
            cleanup_symbol,
        )
    finally:
        await conn.close()

    assert row is not None
    assert row["trade_id"] == "t-1"
    assert row["side"] == "BUY"
    assert Decimal(row["price"]) == Decimal("50000.5")
    assert Decimal(row["quantity"]) == Decimal("0.01")


async def test_batch_insert(store: TimescaleStore, cleanup_symbol: str) -> None:
    base = 1_700_000_000_000_000_000
    snaps = [_snap(cleanup_symbol, base + i * 1_000_000, sequence=i) for i in range(5)]
    trades = [_trade(cleanup_symbol, base + i * 1_000_000, tid=f"b-{i}") for i in range(5)]

    await store.insert_book_batch(snaps)
    await store.insert_trade_batch(trades)

    conn = await asyncpg.connect(_dsn(), timeout=2.0)
    try:
        n_books = await conn.fetchval(
            "SELECT COUNT(*) FROM book_snapshots WHERE symbol = $1", cleanup_symbol
        )
        n_trades = await conn.fetchval(
            "SELECT COUNT(*) FROM trades_tape WHERE symbol = $1", cleanup_symbol
        )
    finally:
        await conn.close()

    assert n_books == 5
    assert n_trades == 5
