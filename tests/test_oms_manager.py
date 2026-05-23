"""Testes do OrderManager — usa FakeRESTClient para evitar rede."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from core.types import Order, OrderStatus, OrderType, Side
from oms.binance_rest import BinanceRESTError
from oms.manager import OrderManager, OrderRejectedError, OrderStore
from risk.engine import RiskEngine, TradeIntent
from risk.limits import RiskLimits

pytestmark = pytest.mark.unit


class FakeRESTClient:
    """Mock determinístico — registra chamadas e devolve respostas configuráveis."""

    def __init__(self) -> None:
        self.placed: list[dict[str, Any]] = []
        self.canceled: list[dict[str, Any]] = []
        self.cancel_all_calls: list[str] = []
        self.open_orders_calls: list[str | None] = []
        self.next_response: dict[str, Any] = {
            "orderId": 1,
            "status": "NEW",
            "executedQty": "0",
        }
        self.next_error: BinanceRESTError | None = None
        self.next_open_orders: list[dict[str, Any]] = []

    async def place_order(self, **params: Any) -> dict[str, Any]:
        if self.next_error is not None:
            err = self.next_error
            self.next_error = None
            raise err
        self.placed.append(params)
        return self.next_response

    async def cancel_order(self, **params: Any) -> dict[str, Any]:
        self.canceled.append(params)
        return {"status": "CANCELED"}

    async def cancel_all(self, symbol: str) -> list[dict[str, Any]]:
        self.cancel_all_calls.append(symbol)
        return [{"orderId": 1}, {"orderId": 2}]

    async def open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        self.open_orders_calls.append(symbol)
        return self.next_open_orders


def _limits() -> RiskLimits:
    return RiskLimits(
        capital_usd=Decimal("10000"),
        max_daily_drawdown_pct=Decimal("0.03"),
        max_position_per_side_pct=Decimal("0.30"),
        max_open_orders_per_symbol=10,
    )


def _intent(symbol: str = "BTCUSDT", side: Side = Side.BUY) -> TradeIntent:
    return TradeIntent(symbol, side, Decimal("0.01"), Decimal("50000"))


@pytest.fixture
def fake_rest() -> FakeRESTClient:
    return FakeRESTClient()


@pytest.fixture
def risk() -> RiskEngine:
    return RiskEngine(_limits())


@pytest.fixture
def oms(fake_rest: FakeRESTClient, risk: RiskEngine) -> OrderManager:
    return OrderManager(fake_rest, risk)  # type: ignore[arg-type]


# ─────────── OrderStore ───────────


class TestOrderStore:
    def test_add_and_get(self) -> None:
        store = OrderStore()
        order = Order(
            client_order_id="x",
            symbol="BTC",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
            price=Decimal("100"),
        )
        store.add(order)
        assert store.get("x") is order
        assert len(store) == 1

    def test_trim_max_history(self) -> None:
        store = OrderStore(max_history=2)
        for i in range(5):
            store.add(
                Order(
                    client_order_id=f"o{i}",
                    symbol="BTC",
                    side=Side.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=Decimal("1"),
                    price=Decimal("100"),
                )
            )
        assert len(store) == 2


# ─────────── submit ───────────


class TestSubmit:
    async def test_happy_path(self, oms: OrderManager, fake_rest: FakeRESTClient) -> None:
        order = await oms.submit(_intent())
        assert order.status == OrderStatus.OPEN
        assert order.exchange_order_id == "1"
        assert len(fake_rest.placed) == 1
        assert fake_rest.placed[0]["symbol"] == "BTCUSDT"

    async def test_risk_reject_blocks_submit(
        self, oms: OrderManager, risk: RiskEngine, fake_rest: FakeRESTClient
    ) -> None:
        risk.trigger_halt("test")
        with pytest.raises(OrderRejectedError):
            await oms.submit(_intent())
        assert fake_rest.placed == []  # não tocou na exchange

    async def test_exchange_error_marks_rejected(
        self, oms: OrderManager, fake_rest: FakeRESTClient
    ) -> None:
        fake_rest.next_error = BinanceRESTError(-1013, "filter failure", 400)
        with pytest.raises(BinanceRESTError):
            await oms.submit(_intent())
        # A ordem registrada deve estar como REJECTED
        rejected = [o for o in oms.store._orders.values() if o.status == OrderStatus.REJECTED]
        assert len(rejected) == 1

    async def test_filled_response_sets_filled_qty(
        self, oms: OrderManager, fake_rest: FakeRESTClient
    ) -> None:
        fake_rest.next_response = {
            "orderId": 42,
            "status": "FILLED",
            "executedQty": "0.01",
        }
        order = await oms.submit(_intent())
        assert order.status == OrderStatus.FILLED
        assert order.filled_qty == Decimal("0.01")


# ─────────── cancel ───────────


class TestCancel:
    async def test_cancel_known_order(self, oms: OrderManager, fake_rest: FakeRESTClient) -> None:
        order = await oms.submit(_intent())
        await oms.cancel(order.client_order_id)
        assert order.status == OrderStatus.CANCELED
        assert len(fake_rest.canceled) == 1

    async def test_cancel_unknown_is_noop(
        self, oms: OrderManager, fake_rest: FakeRESTClient
    ) -> None:
        await oms.cancel("does-not-exist")
        assert fake_rest.canceled == []

    async def test_cancel_2011_is_tolerated(
        self, oms: OrderManager, fake_rest: FakeRESTClient
    ) -> None:
        order = await oms.submit(_intent())

        async def raise_2011(**_: Any) -> dict[str, Any]:
            raise BinanceRESTError(-2011, "unknown order", 400)

        fake_rest.cancel_order = raise_2011  # type: ignore[method-assign]
        # Não levanta — código -2011 é tolerado
        await oms.cancel(order.client_order_id)
        assert order.status == OrderStatus.CANCELED


# ─────────── cancel_all ───────────


class TestCancelAll:
    async def test_cancel_all_for_symbol(
        self, oms: OrderManager, fake_rest: FakeRESTClient
    ) -> None:
        await oms.submit(_intent())
        await oms.submit(_intent())
        count = await oms.cancel_all("BTCUSDT")
        assert count == 2
        assert fake_rest.cancel_all_calls == ["BTCUSDT"]


# ─────────── reconcile ───────────


class TestReconcile:
    async def test_reconcile_marks_missing_as_canceled(
        self, oms: OrderManager, fake_rest: FakeRESTClient
    ) -> None:
        order = await oms.submit(_intent())
        fake_rest.next_open_orders = []  # exchange não tem essa ordem
        await oms.reconcile("BTCUSDT")
        assert order.status == OrderStatus.CANCELED

    async def test_reconcile_keeps_matching_orders_open(
        self, oms: OrderManager, fake_rest: FakeRESTClient
    ) -> None:
        order = await oms.submit(_intent())
        fake_rest.next_open_orders = [{"clientOrderId": order.client_order_id}]
        await oms.reconcile("BTCUSDT")
        assert order.status == OrderStatus.OPEN


# ─────────── make_client_order_id ───────────


class TestClientOrderID:
    def test_format_and_uniqueness(self, oms: OrderManager) -> None:
        a = oms.make_client_order_id()
        b = oms.make_client_order_id()
        assert a.startswith("mdd-")
        assert a != b
