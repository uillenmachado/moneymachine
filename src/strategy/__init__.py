"""Strategy Engine — calcula quotes-alvo a partir de book + estado interno.

Implementação completa na Fase 4. Aqui apenas o protocolo da estratégia.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

import msgspec

from core.types import OrderBookSnapshot, Side


class QuoteIntent(msgspec.Struct, frozen=True):
    """Intenção de cotação emitida pela estratégia para o OMS."""

    symbol: str
    side: Side
    price: Decimal
    quantity: Decimal
    level_index: int  # 0 = mais próximo do mid; 1 = segundo nível; etc.


class Strategy(Protocol):
    """Contrato para qualquer estratégia (Grid, MM, híbrida)."""

    def on_book(self, book: OrderBookSnapshot) -> tuple[QuoteIntent, ...]:
        """Recebe novo book, retorna intenções de cotação desejadas."""
        ...

    def on_fill(self, symbol: str, side: Side, price: Decimal, quantity: Decimal) -> None:
        """Notificação de fill — atualiza inventário e estado interno."""
        ...
