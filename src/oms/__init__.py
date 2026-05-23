"""Order Management System — orquestra ciclo de vida das ordens.

Implementação completa na Fase 4.
"""

from __future__ import annotations

from typing import Protocol

from core.types import Order


class OrderManager(Protocol):
    """Contrato do OMS."""

    async def submit(self, order: Order) -> None: ...

    async def cancel(self, client_order_id: str) -> None: ...

    async def cancel_all(self, symbol: str | None = None) -> None: ...

    async def reconcile(self) -> None:
        """Reconcilia estado local com a exchange (a cada N segundos)."""
        ...
