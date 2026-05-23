"""Tipos compartilhados pelo sistema (domain types).

Usa msgspec.Struct para alta performance (zero-copy, ~10x mais rápido que dataclass)
no hot path. Decimal para representar preços e quantidades — evita erros de float
em cálculos financeiros.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

import msgspec


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    LIMIT_MAKER = "LIMIT_MAKER"  # Post-only — rejeita se cruzar o book


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class BookLevel(msgspec.Struct, frozen=True, gc=False):
    """Um nível do order book (preço + quantidade agregada)."""

    price: Decimal
    quantity: Decimal


class OrderBookSnapshot(msgspec.Struct, frozen=True, gc=False):
    """Snapshot top-N do livro de ofertas."""

    symbol: str
    timestamp_ns: int  # nanosegundos UTC
    bids: tuple[BookLevel, ...]  # ordenados DESC por preço
    asks: tuple[BookLevel, ...]  # ordenados ASC por preço
    sequence: int | None = None

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / Decimal(2)

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid


class Trade(msgspec.Struct, frozen=True, gc=False):
    """Negócio executado no tape público."""

    symbol: str
    timestamp_ns: int
    price: Decimal
    quantity: Decimal
    side: Side
    trade_id: str


class Order(msgspec.Struct):
    """Ordem submetida ao OMS."""

    client_order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None  # None para MARKET
    exchange_order_id: str | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: Decimal = Decimal(0)
    created_at_ns: int = 0
    updated_at_ns: int = 0


class Fill(msgspec.Struct, frozen=True, gc=False):
    """Execução parcial ou total de uma ordem."""

    order_client_id: str
    trade_id: str
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_currency: str
    is_maker: bool
    executed_at_ns: int
