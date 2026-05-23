"""Estado mutável do Risk Engine — posições, PnL, equity, peak.

Mantém:
- posição por símbolo (quantidade base, signed: + long, - short);
- preço médio de entrada por símbolo;
- mark price corrente por símbolo (atualizado via `update_mark`);
- realized PnL (cumulativo na sessão);
- equity peak (high-water mark da sessão para cálculo de drawdown).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from core.types import Fill, Side


class Position(msgspec.Struct):
    """Posição agregada em um símbolo. Quantidade signed."""

    symbol: str
    quantity: Decimal = Decimal(0)  # +long / -short
    avg_entry_price: Decimal = Decimal(0)
    mark_price: Decimal = Decimal(0)

    @property
    def notional_usd(self) -> Decimal:
        return abs(self.quantity) * self.mark_price

    @property
    def unrealized_pnl(self) -> Decimal:
        if self.quantity == 0 or self.mark_price == 0:
            return Decimal(0)
        return (self.mark_price - self.avg_entry_price) * self.quantity


class RiskState:
    """Estado mutável centralizado. Não thread-safe — acesso via lock externo."""

    def __init__(self, capital_usd: Decimal) -> None:
        self._capital_usd = capital_usd
        self._positions: dict[str, Position] = {}
        self._realized_pnl: Decimal = Decimal(0)
        self._equity_peak: Decimal = capital_usd
        self._open_orders_count: dict[str, int] = {}

    # ─────────── Inventário ───────────

    def position(self, symbol: str) -> Position:
        if symbol not in self._positions:
            self._positions[symbol] = Position(symbol=symbol)
        return self._positions[symbol]

    def update_mark(self, symbol: str, price: Decimal) -> None:
        self.position(symbol).mark_price = price
        self._refresh_equity_peak()

    def apply_fill(self, fill: Fill, symbol: str, side: Side) -> None:
        """Atualiza posição + realized PnL a partir de um fill executado.

        Convenção: BUY incrementa quantidade, SELL decrementa.
        Realized PnL acumula quando a operação reduz/reverte a posição.
        """
        pos = self.position(symbol)
        signed_qty = fill.quantity if side.value == "BUY" else -fill.quantity

        if pos.quantity == 0:
            # Abertura
            pos.quantity = signed_qty
            pos.avg_entry_price = fill.price
        elif (pos.quantity > 0 and signed_qty > 0) or (pos.quantity < 0 and signed_qty < 0):
            # Aumenta posição no mesmo sentido — recalcula preço médio
            new_qty = pos.quantity + signed_qty
            pos.avg_entry_price = (
                pos.avg_entry_price * abs(pos.quantity) + fill.price * abs(signed_qty)
            ) / abs(new_qty)
            pos.quantity = new_qty
        else:
            # Redução / reversão
            closing_qty = min(abs(signed_qty), abs(pos.quantity))
            pnl_per_unit = (fill.price - pos.avg_entry_price) * (
                Decimal(1) if pos.quantity > 0 else Decimal(-1)
            )
            self._realized_pnl += pnl_per_unit * closing_qty - fill.fee
            new_qty = pos.quantity + signed_qty
            if (pos.quantity > 0 and new_qty < 0) or (pos.quantity < 0 and new_qty > 0):
                # Reverteu — novo preço médio é o preço do fill
                pos.avg_entry_price = fill.price
            pos.quantity = new_qty
            if pos.quantity == 0:
                pos.avg_entry_price = Decimal(0)

        self._refresh_equity_peak()

    # ─────────── Open orders tracking ───────────

    def inc_open_orders(self, symbol: str) -> None:
        self._open_orders_count[symbol] = self._open_orders_count.get(symbol, 0) + 1

    def dec_open_orders(self, symbol: str) -> None:
        current = self._open_orders_count.get(symbol, 0)
        if current > 0:
            self._open_orders_count[symbol] = current - 1

    def open_orders(self, symbol: str) -> int:
        return self._open_orders_count.get(symbol, 0)

    # ─────────── Aggregates ───────────

    @property
    def realized_pnl(self) -> Decimal:
        return self._realized_pnl

    @property
    def unrealized_pnl(self) -> Decimal:
        return sum((p.unrealized_pnl for p in self._positions.values()), Decimal(0))

    @property
    def equity(self) -> Decimal:
        return self._capital_usd + self._realized_pnl + self.unrealized_pnl

    @property
    def equity_peak(self) -> Decimal:
        return self._equity_peak

    @property
    def drawdown_pct(self) -> Decimal:
        if self._equity_peak == 0:
            return Decimal(0)
        return (self._equity_peak - self.equity) / self._equity_peak

    def _refresh_equity_peak(self) -> None:
        self._equity_peak = max(self._equity_peak, self.equity)


__all__ = ["Position", "RiskState"]
