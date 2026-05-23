"""Market Making — Avellaneda-Stoikov + skew por Order Flow Imbalance (OFI).

Modelo Avellaneda-Stoikov (2008) — reservation price + spread ótimo:

    r(s, q, t) = s - q * γ * σ² * (T - t)
    spread     = γ * σ² * (T - t) + (2/γ) * ln(1 + γ/k)

Onde:
- s = mid price
- q = inventário (signed)
- γ = aversão a risco (gamma > 0)
- σ = volatilidade instantânea (estimada via realized vol)
- T - t = horizonte até final do "shift" (constante simplificada)
- k = liquidez (intensidade da chegada de ordens market)

Skew por OFI (Cont, Kukanov, Stoikov 2014):
    skew_bps += λ * normalized_OFI

OFI = (Δbest_bid_qty - Δbest_ask_qty) — sinal de pressão.

Esta implementação é a "v1": σ estimado por janela móvel simples,
OFI calculado snapshot a snapshot. Calibração de γ, κ, λ via backtest na Fase 5.
"""

from __future__ import annotations

import math
from collections import deque
from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec

from core.types import Side
from strategy import QuoteIntent

if TYPE_CHECKING:
    from core.types import OrderBookSnapshot

_BPS = Decimal("10000")


class MMParams(msgspec.Struct, frozen=True):
    """Parâmetros do market maker. Calibrados via backtest (Fase 5)."""

    gamma: float = 0.1  # aversão ao risco
    kappa: float = 1.5  # intensidade de chegada de ordens
    horizon_s: float = 60.0  # T-t simplificado: 1 minuto
    vol_window: int = 60  # snapshots para estimar σ
    ofi_lambda_bps: float = 2.0  # peso do OFI em bps
    quote_size: Decimal = Decimal("0.001")
    max_inventory: Decimal = Decimal("0.05")  # |q| cap


class AvellanedaStoikov:
    """MM stateful — mantém janela de mids, last best bid/ask qty, inventário."""

    def __init__(self, symbol: str, params: MMParams) -> None:
        self._symbol = symbol
        self._params = params
        self._mid_history: deque[float] = deque(maxlen=params.vol_window)
        self._last_bid_qty: Decimal | None = None
        self._last_ask_qty: Decimal | None = None
        self._inventory: Decimal = Decimal(0)

    @property
    def inventory(self) -> Decimal:
        return self._inventory

    def on_book(self, book: OrderBookSnapshot) -> tuple[QuoteIntent, ...]:
        mid = book.mid_price
        if mid is None or not book.bids or not book.asks:
            return ()

        # Atualiza histórico de mid e calcula σ (em retornos log).
        mid_f = float(mid)
        self._mid_history.append(mid_f)
        sigma = self._estimate_vol()
        if sigma <= 0.0:
            return ()

        # OFI: variação do tamanho no melhor nível.
        cur_bid_qty = book.bids[0].quantity
        cur_ask_qty = book.asks[0].quantity
        ofi = self._compute_ofi(cur_bid_qty, cur_ask_qty)
        self._last_bid_qty = cur_bid_qty
        self._last_ask_qty = cur_ask_qty

        # Reservation price e half spread (Avellaneda-Stoikov).
        gamma = self._params.gamma
        kappa = self._params.kappa
        horizon = self._params.horizon_s
        q = float(self._inventory)

        sigma_sq_t = sigma * sigma * horizon
        reservation_offset = q * gamma * sigma_sq_t
        half_spread = 0.5 * gamma * sigma_sq_t + (1.0 / gamma) * math.log(1.0 + gamma / kappa)

        # Skew por OFI (clampa para evitar quotes esquisitas).
        ofi_skew_bps = max(-50.0, min(50.0, ofi * self._params.ofi_lambda_bps))

        # Conversão para Decimal só na hora de emitir os quotes.
        reservation = mid - Decimal(str(reservation_offset))
        half_d = Decimal(str(half_spread))
        skew_d = (Decimal(str(ofi_skew_bps)) / _BPS) * mid

        bid_price = reservation - half_d - skew_d
        ask_price = reservation + half_d - skew_d

        # Não quota o lado que excederia o cap de inventário.
        intents: list[QuoteIntent] = []
        if self._inventory < self._params.max_inventory:
            intents.append(
                QuoteIntent(
                    symbol=self._symbol,
                    side=Side.BUY,
                    price=bid_price,
                    quantity=self._params.quote_size,
                    level_index=0,
                )
            )
        if self._inventory > -self._params.max_inventory:
            intents.append(
                QuoteIntent(
                    symbol=self._symbol,
                    side=Side.SELL,
                    price=ask_price,
                    quantity=self._params.quote_size,
                    level_index=0,
                )
            )
        return tuple(intents)

    def on_fill(self, _symbol: str, side: Side, _price: Decimal, quantity: Decimal) -> None:
        if side == Side.BUY:
            self._inventory += quantity
        else:
            self._inventory -= quantity

    # ─────────── Internals ───────────

    def _estimate_vol(self) -> float:
        """Volatilidade realizada por log-retornos consecutivos."""
        if len(self._mid_history) < 2:
            return 0.0
        mids = list(self._mid_history)
        returns = [math.log(mids[i] / mids[i - 1]) for i in range(1, len(mids)) if mids[i - 1] > 0]
        if not returns:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(var)

    def _compute_ofi(self, cur_bid_qty: Decimal, cur_ask_qty: Decimal) -> float:
        if self._last_bid_qty is None or self._last_ask_qty is None:
            return 0.0
        d_bid = float(cur_bid_qty - self._last_bid_qty)
        d_ask = float(cur_ask_qty - self._last_ask_qty)
        return d_bid - d_ask


__all__ = ["AvellanedaStoikov", "MMParams"]
