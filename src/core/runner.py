"""Runner principal — conecta WS Binance -> Strategy -> OMS -> Risk em loop contínuo.

Loop simplificado (v1):
- Por símbolo, mantém uma estratégia ativa (AdaptiveGrid por padrão).
- A cada book snapshot recebido:
  1. RiskEngine.update_mark(symbol, mid).
  2. Se halted -> cancela tudo, dorme breve, segue.
  3. Estratégia gera intents.
  4. Cancela ordens antigas no símbolo (estratégia stateless: refresh full).
  5. Submete novos intents via OMS (gate de risco automático).
- Trades públicos atualizam volatilidade futura (já capturada via book snapshots por enquanto).

Loop fecha gracefully em SIGINT/SIGTERM via flag interna.
"""

from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from core.types import OrderBookSnapshot
from oms.binance_rest import BinanceRESTClient, BinanceRESTError
from oms.manager import OrderManager, OrderRejectedError
from risk.engine import RiskEngine, TradeIntent
from risk.limits import RiskLimits
from strategy.grid import AdaptiveGrid, GridParams

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core.config import Settings
    from data.binance_ws import BinanceWSClient
    from strategy import QuoteIntent

log = structlog.get_logger(__name__)


class TradingRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        ws_client: BinanceWSClient,
        rest_client: BinanceRESTClient,
        symbols: Iterable[str],
        strategies: dict[str, AdaptiveGrid] | None = None,
    ) -> None:
        self._settings = settings
        self._ws = ws_client
        self._rest = rest_client
        self._symbols = list(symbols)
        limits = RiskLimits.from_settings(settings.risk, settings.capital_usd)
        self._risk = RiskEngine(limits)
        self._oms = OrderManager(rest_client, self._risk)
        self._strategies: dict[str, AdaptiveGrid] = strategies or {
            sym: AdaptiveGrid(sym, GridParams()) for sym in self._symbols
        }
        self._stopping = asyncio.Event()

    async def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        log.info("runner.start", symbols=self._symbols, halted=self._risk.is_halted())
        ws_task = asyncio.create_task(self._ws.run(), name="ws-loop")
        try:
            async for book in self._ws.book_stream():
                if self._stopping.is_set():
                    break
                await self._on_book(book)
        finally:
            await self._ws.stop()
            with contextlib.suppress(Exception):
                await ws_task
            await self._shutdown()

    async def _on_book(self, book: OrderBookSnapshot) -> None:
        mid = book.mid_price
        if mid is None:
            return
        self._risk.update_mark(book.symbol, mid)

        if self._risk.is_halted():
            await self._oms.cancel_all(book.symbol)
            return

        strategy = self._strategies.get(book.symbol)
        if strategy is None:
            return
        intents = strategy.on_book(book)
        if not intents:
            return

        # Política simples: refresh total — cancela tudo no símbolo e recoloca.
        await self._oms.cancel_all(book.symbol)
        for q in intents:
            await self._submit_one(q)

    async def _submit_one(self, quote: QuoteIntent) -> None:
        intent = TradeIntent(
            symbol=quote.symbol,
            side=quote.side,
            quantity=quote.quantity,
            price=_round_price(quote.price),
        )
        try:
            await self._oms.submit(intent)
        except OrderRejectedError as exc:
            log.warning("submit.risk_reject", reason=str(exc), symbol=quote.symbol)
        except BinanceRESTError as exc:
            log.warning(
                "submit.exchange_reject",
                code=exc.code,
                msg=exc.message,
                symbol=quote.symbol,
            )

    async def _shutdown(self) -> None:
        log.info("runner.shutdown.begin")
        with contextlib.suppress(Exception):
            for sym in self._symbols:
                await self._oms.cancel_all(sym)
        with contextlib.suppress(Exception):
            await self._rest.close()
        log.info("runner.shutdown.done")


def _round_price(price: Decimal) -> Decimal:
    # Placeholder: arredonda para 2 casas. tickSize real virá do exchangeInfo na Fase 6.1.
    return price.quantize(Decimal("0.01"))


__all__ = ["TradingRunner"]
