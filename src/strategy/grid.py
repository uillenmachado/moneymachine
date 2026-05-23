"""Grid Adaptativo — gera quotes simétricos ao redor do mid price.

Parâmetros principais:
- `levels`: número de níveis por lado (ex.: 5 bid + 5 ask).
- `spacing_bps`: espaçamento entre níveis em basis points (1 bps = 0.01%).
- `quote_size`: tamanho de cada quote (em base, ex.: 0.001 BTC).
- `skew`: assimetria entre bid e ask em bps (positivo = mais agressivo no bid).

Adaptação à volatilidade fica para uma camada superior (estratégia composta).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec

from core.types import Side
from strategy import QuoteIntent

if TYPE_CHECKING:
    from core.types import OrderBookSnapshot

_BPS = Decimal("10000")


class GridParams(msgspec.Struct, frozen=True):
    levels: int = 5
    spacing_bps: Decimal = Decimal("5")  # 5 bps = 0.05%
    quote_size: Decimal = Decimal("0.001")
    skew_bps: Decimal = Decimal("0")


class AdaptiveGrid:
    """Estratégia stateless — recebe book e emite quotes para cada nível."""

    def __init__(self, symbol: str, params: GridParams) -> None:
        self._symbol = symbol
        self._params = params

    def on_book(self, book: OrderBookSnapshot) -> tuple[QuoteIntent, ...]:
        mid = book.mid_price
        if mid is None:
            return ()

        intents: list[QuoteIntent] = []
        skew_adj = self._params.skew_bps / _BPS

        for i in range(1, self._params.levels + 1):
            offset = (self._params.spacing_bps * Decimal(i)) / _BPS
            bid_price = mid * (Decimal(1) - offset - skew_adj)
            ask_price = mid * (Decimal(1) + offset - skew_adj)
            intents.append(
                QuoteIntent(
                    symbol=self._symbol,
                    side=Side.BUY,
                    price=bid_price,
                    quantity=self._params.quote_size,
                    level_index=i - 1,
                )
            )
            intents.append(
                QuoteIntent(
                    symbol=self._symbol,
                    side=Side.SELL,
                    price=ask_price,
                    quantity=self._params.quote_size,
                    level_index=i - 1,
                )
            )
        return tuple(intents)

    def on_fill(self, _symbol: str, _side: Side, _price: Decimal, _quantity: Decimal) -> None:
        # Stateless — sem inventário interno. Camada superior (Risk) acumula posição.
        return


__all__ = ["AdaptiveGrid", "GridParams"]
