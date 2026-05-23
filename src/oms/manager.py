"""OrderManager — orquestra ciclo de vida das ordens.

Responsabilidades:
1. Receber `TradeIntent`, validar via `RiskEngine.check_pre_trade`.
2. Submeter à exchange (Binance REST).
3. Manter store em memória das ordens ativas (`OrderStore`).
4. Reconciliar com a exchange periodicamente (detectar fills perdidos).
5. `cancel_all` de emergência (kill switch).

NÃO persiste no DB no hot path (Fase 4+ — usa fila out-of-band).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from core.types import Order, OrderStatus, OrderType, Side
from metrics import ORDER_SUBMIT_LATENCY_MS
from oms.binance_rest import BinanceRESTError
from risk.engine import TradeIntent

if TYPE_CHECKING:
    from oms.binance_rest import BinanceRESTClient
    from risk.engine import RiskEngine

logger = structlog.get_logger(__name__)


class OrderRejectedError(RuntimeError):
    """Ordem rejeitada pelo Risk Engine (não chegou à exchange)."""


class OrderStore:
    """Store em memória de ordens ativas/recentes (TTL implícito por reconciliação)."""

    def __init__(self, max_history: int = 1000) -> None:
        self._orders: dict[str, Order] = {}
        self._max_history = max_history

    def add(self, order: Order) -> None:
        self._orders[order.client_order_id] = order
        # Trim simples — remove os mais antigos quando ultrapassa o limite.
        if len(self._orders) > self._max_history:
            to_drop = len(self._orders) - self._max_history
            for k in list(self._orders.keys())[:to_drop]:
                del self._orders[k]

    def get(self, client_order_id: str) -> Order | None:
        return self._orders.get(client_order_id)

    def update_status(
        self,
        client_order_id: str,
        status: OrderStatus,
        *,
        exchange_order_id: str | None = None,
        filled_qty: Decimal | None = None,
    ) -> Order | None:
        order = self._orders.get(client_order_id)
        if order is None:
            return None
        order.status = status
        if exchange_order_id is not None:
            order.exchange_order_id = exchange_order_id
        if filled_qty is not None:
            order.filled_qty = filled_qty
        return order

    def open_orders(self, symbol: str | None = None) -> list[Order]:
        return [
            o
            for o in self._orders.values()
            if o.status in {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED}
            and (symbol is None or o.symbol == symbol)
        ]

    def __len__(self) -> int:
        return len(self._orders)


class OrderManager:
    """OMS principal — gate de risco + REST + store em memória."""

    def __init__(
        self,
        rest: BinanceRESTClient,
        risk: RiskEngine,
        *,
        client_order_id_prefix: str = "mdd",
    ) -> None:
        self._rest = rest
        self._risk = risk
        self._store = OrderStore()
        self._prefix = client_order_id_prefix

    @property
    def store(self) -> OrderStore:
        return self._store

    def make_client_order_id(self) -> str:
        return f"{self._prefix}-{uuid.uuid4().hex[:16]}"

    async def submit(
        self, intent: TradeIntent, *, order_type: OrderType = OrderType.LIMIT
    ) -> Order:
        """Valida via Risk Engine, submete à exchange, registra no store.

        Raises:
            OrderRejectedError: se o Risk Engine bloqueou (não há chamada REST).
            BinanceRESTError: se a exchange rejeitou.
        """
        evt = self._risk.check_pre_trade(intent)
        if evt is not None:
            raise OrderRejectedError(evt.message)

        client_id = self.make_client_order_id()
        order = Order(
            client_order_id=client_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=order_type,
            quantity=intent.quantity,
            price=intent.price,
            status=OrderStatus.PENDING,
        )
        self._store.add(order)

        with ORDER_SUBMIT_LATENCY_MS.time():
            try:
                resp = await self._rest.place_order(
                    symbol=intent.symbol,
                    side=intent.side.value,
                    order_type=order_type.value,
                    quantity=str(intent.quantity),
                    price=str(intent.price) if order_type != OrderType.MARKET else None,
                    client_order_id=client_id,
                )
            except BinanceRESTError:
                self._store.update_status(client_id, OrderStatus.REJECTED)
                raise

        exchange_id = str(resp.get("orderId", ""))
        status = self._map_status(str(resp.get("status", "NEW")))
        filled_str = str(resp.get("executedQty", "0"))
        filled = Decimal(filled_str) if filled_str else Decimal(0)
        self._store.update_status(
            client_id,
            status,
            exchange_order_id=exchange_id or None,
            filled_qty=filled,
        )
        if status in {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED}:
            self._risk.register_open_order(intent.symbol)

        logger.info(
            "order_submitted",
            client_id=client_id,
            symbol=intent.symbol,
            side=intent.side.value,
            qty=str(intent.quantity),
            price=str(intent.price),
            status=status.value,
        )
        return order

    async def cancel(self, client_order_id: str) -> None:
        order = self._store.get(client_order_id)
        if order is None:
            logger.warning("cancel_unknown_order", client_id=client_order_id)
            return
        try:
            await self._rest.cancel_order(symbol=order.symbol, client_order_id=client_order_id)
        except BinanceRESTError as exc:
            # -2011 = order não existe (já cancelada/expirada) — não-fatal
            if exc.code != -2011:
                raise
        self._store.update_status(client_order_id, OrderStatus.CANCELED)
        self._risk.register_closed_order(order.symbol)

    async def cancel_all(self, symbol: str | None = None) -> int:
        """Cancela todas as ordens abertas. Retorna a contagem cancelada com sucesso."""
        canceled = 0
        symbols: set[str] = {symbol} if symbol else {o.symbol for o in self._store.open_orders()}
        for sym in symbols:
            try:
                results = await self._rest.cancel_all(sym)
                canceled += len(results)
            except BinanceRESTError as exc:
                logger.error("cancel_all_failed", symbol=sym, exc=str(exc))
                continue
            # Marca todas as ordens locais como canceladas
            for o in self._store.open_orders(sym):
                self._store.update_status(o.client_order_id, OrderStatus.CANCELED)
                self._risk.register_closed_order(o.symbol)
        return canceled

    async def reconcile(self, symbol: str) -> None:
        """Compara ordens locais com `openOrders` da exchange. Marca discrepâncias."""
        try:
            remote = await self._rest.open_orders(symbol)
        except BinanceRESTError as exc:
            logger.error("reconcile_failed", symbol=symbol, exc=str(exc))
            return
        remote_ids = {str(r.get("clientOrderId", "")) for r in remote}
        for o in self._store.open_orders(symbol):
            if o.client_order_id not in remote_ids:
                # Local diz OPEN, exchange não conhece → assume FILLED/CANCELED.
                logger.warning(
                    "reconcile_missing_remote", client_id=o.client_order_id, symbol=symbol
                )
                self._store.update_status(o.client_order_id, OrderStatus.CANCELED)
                self._risk.register_closed_order(symbol)

    # ─────────── Internals ───────────

    @staticmethod
    def _map_status(binance_status: str) -> OrderStatus:
        mapping = {
            "NEW": OrderStatus.OPEN,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELED,
            "PENDING_CANCEL": OrderStatus.OPEN,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
        }
        return mapping.get(binance_status, OrderStatus.PENDING)


__all__ = ["OrderManager", "OrderRejectedError", "OrderStore"]


# Marca como usados (acessados via from-import / runtime apenas).
_ = Side
