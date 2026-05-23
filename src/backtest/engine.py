"""Backtest event-driven minimalista para validar estratégias sem rede.

Modelo de fills: maker passivo — quote é considerado executado quando o melhor
preço do lado oposto cruza o preço do quote. Slippage zero (preenche no preço do quote).
Fee maker aplicado em USD sobre o notional.

Walk-forward fica para a Fase 5.2 (depois de calibração inicial).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from core.types import Side

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core.types import OrderBookSnapshot
    from strategy import QuoteIntent, Strategy


@dataclass(slots=True)
class BacktestStats:
    fills: int = 0
    realized_pnl_usd: Decimal = Decimal(0)
    fees_paid_usd: Decimal = Decimal(0)
    inventory: Decimal = Decimal(0)
    avg_entry: Decimal = Decimal(0)
    mark_to_market_usd: Decimal = Decimal(0)
    quotes_emitted: int = 0
    timeline: list[tuple[int, Decimal, Decimal]] = field(default_factory=list)
    # (timestamp_ns, equity, inventory)

    @property
    def equity_usd(self) -> Decimal:
        return self.realized_pnl_usd + self.mark_to_market_usd - self.fees_paid_usd


def _try_fill(quote: QuoteIntent, book: OrderBookSnapshot) -> bool:
    """True se o quote estaria preenchido contra o melhor preço oposto."""
    if quote.side == Side.BUY:
        best_ask = book.best_ask
        return best_ask is not None and best_ask <= quote.price
    best_bid = book.best_bid
    return best_bid is not None and best_bid >= quote.price


class EventDrivenBacktest:
    """Replay de snapshots → estratégia → fills → PnL.

    Maker fee em fração (ex.: Decimal("0.0001") = 1 bps).
    """

    def __init__(self, strategy: Strategy, *, maker_fee: Decimal = Decimal("0.0001")) -> None:
        self._strategy = strategy
        self._maker_fee = maker_fee
        self.stats = BacktestStats()

    def run(self, books: Iterable[OrderBookSnapshot]) -> BacktestStats:
        pending: tuple[QuoteIntent, ...] = ()
        for book in books:
            # Quotes emitidos no tick anterior são testados contra o book atual.
            for q in pending:
                if _try_fill(q, book):
                    self._apply_fill(q, book)
            # Emite novos quotes para o próximo tick.
            pending = self._strategy.on_book(book)
            self.stats.quotes_emitted += len(pending)

            mid = book.mid_price or Decimal(0)
            self.stats.mark_to_market_usd = (mid - self.stats.avg_entry) * self.stats.inventory
            self.stats.timeline.append(
                (book.timestamp_ns, self.stats.equity_usd, self.stats.inventory)
            )
        return self.stats

    def _apply_fill(self, quote: QuoteIntent, book: OrderBookSnapshot) -> None:
        signed_qty = quote.quantity if quote.side == Side.BUY else -quote.quantity
        fill_price = quote.price
        notional = quote.quantity * fill_price
        fee = notional * self._maker_fee
        self.stats.fees_paid_usd += fee
        self.stats.fills += 1

        prev_qty = self.stats.inventory
        new_qty = prev_qty + signed_qty

        # Realized PnL apenas quando reduz posição (sinais opostos).
        if prev_qty != 0 and (prev_qty > 0) != (signed_qty > 0):
            closing_qty = min(abs(prev_qty), abs(signed_qty))
            direction = Decimal(1) if prev_qty > 0 else Decimal(-1)
            self.stats.realized_pnl_usd += (
                (fill_price - self.stats.avg_entry) * closing_qty * direction
            )

        if new_qty == 0:
            self.stats.avg_entry = Decimal(0)
        elif prev_qty == 0 or (prev_qty > 0) == (signed_qty > 0):
            # abre ou aumenta — recalcula entrada média.
            self.stats.avg_entry = (
                (self.stats.avg_entry * abs(prev_qty)) + (fill_price * quote.quantity)
            ) / abs(new_qty)
        elif abs(signed_qty) > abs(prev_qty):
            # reversão: nova entrada média é o preço atual.
            self.stats.avg_entry = fill_price

        self.stats.inventory = new_qty
        self._strategy.on_fill(quote.symbol, quote.side, fill_price, quote.quantity)
        _ = book  # apenas para satisfazer linter; usado pelo timeline mais tarde


__all__ = ["BacktestStats", "EventDrivenBacktest"]
