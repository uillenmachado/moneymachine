"""Smoke test ao vivo contra Binance Testnet WS.

Marcado como `live` — não roda em CI. Execução manual:
    python -m uv run pytest -m live -q

Confirma que em até 30s recebemos >=10 snapshots e >=1 trade.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from data.binance_ws import BinanceWSClient

pytestmark = [pytest.mark.live, pytest.mark.slow]


async def test_testnet_collects_books_and_trades() -> None:
    client = BinanceWSClient(
        symbols=["BTCUSDT"],
        book_depth=20,
        update_speed_ms=100,
        with_trades=True,
        testnet=True,
    )

    run_task = asyncio.create_task(client.run())
    books: list[object] = []
    trades: list[object] = []

    async def collect_books() -> None:
        async for snap in client.book_stream():
            books.append(snap)
            if len(books) >= 10:
                return

    async def collect_trades() -> None:
        async for trade in client.trade_stream():
            trades.append(trade)
            if len(trades) >= 1:
                return

    try:
        await asyncio.wait_for(
            asyncio.gather(collect_books(), collect_trades()),
            timeout=30.0,
        )
    finally:
        await client.stop()
        run_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run_task

    assert len(books) >= 10, f"esperava >=10 books, veio {len(books)}"
    assert len(trades) >= 1, f"esperava >=1 trade, veio {len(trades)}"
