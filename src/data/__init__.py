"""Market Data Handler — ingestão de book L2 e tape via WebSocket.

Implementação completa na Fase 4. Este módulo define apenas o contrato.
"""

from __future__ import annotations

from typing import Protocol

from core.types import OrderBookSnapshot, Trade


class MarketDataSource(Protocol):
    """Contrato para uma fonte de dados de mercado em tempo real."""

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def subscribe_book(self, symbol: str, depth: int = 20) -> None: ...

    async def subscribe_trades(self, symbol: str) -> None: ...

    async def next_book(self) -> OrderBookSnapshot:
        """Aguarda o próximo snapshot do livro."""
        ...

    async def next_trade(self) -> Trade:
        """Aguarda o próximo trade no tape."""
        ...
