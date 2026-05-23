"""Testes do Risk Engine: limits, state, engine (gate + halt + drawdown)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.types import Fill, Side
from risk.engine import RiskEngine, TradeIntent
from risk.limits import RiskLimits
from risk.state import RiskState

pytestmark = pytest.mark.unit


def _limits(
    capital: str = "1000",
    dd_pct: str = "0.03",
    pos_pct: str = "0.30",
    max_orders: int = 10,
) -> RiskLimits:
    return RiskLimits(
        capital_usd=Decimal(capital),
        max_daily_drawdown_pct=Decimal(dd_pct),
        max_position_per_side_pct=Decimal(pos_pct),
        max_open_orders_per_symbol=max_orders,
    )


def _fill(price: str, qty: str, fee: str = "0") -> Fill:
    return Fill(
        order_client_id="oid-1",
        trade_id="tid-1",
        price=Decimal(price),
        quantity=Decimal(qty),
        fee=Decimal(fee),
        fee_currency="USDT",
        is_maker=True,
        executed_at_ns=0,
    )


# ─────────── RiskState ───────────


class TestRiskState:
    def test_open_long_sets_avg_entry(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        assert s.position("BTCUSDT").quantity == Decimal("1")
        assert s.position("BTCUSDT").avg_entry_price == Decimal("100")

    def test_increase_long_recomputes_avg(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        s.apply_fill(_fill("110", "1"), "BTCUSDT", Side.BUY)
        assert s.position("BTCUSDT").quantity == Decimal("2")
        assert s.position("BTCUSDT").avg_entry_price == Decimal("105")

    def test_reduce_long_realizes_pnl(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "2"), "BTCUSDT", Side.BUY)
        s.apply_fill(_fill("120", "1"), "BTCUSDT", Side.SELL)
        # vendeu 1 unidade comprada a 100 por 120 → +20 realizado
        assert s.realized_pnl == Decimal("20")
        assert s.position("BTCUSDT").quantity == Decimal("1")

    def test_full_close_resets_avg(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        s.apply_fill(_fill("90", "1"), "BTCUSDT", Side.SELL)
        assert s.position("BTCUSDT").quantity == Decimal("0")
        assert s.position("BTCUSDT").avg_entry_price == Decimal("0")
        assert s.realized_pnl == Decimal("-10")

    def test_reversal_sets_new_avg(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        s.apply_fill(_fill("120", "3"), "BTCUSDT", Side.SELL)
        # Fechou 1 long (+20 realized) e abriu 2 short a 120
        assert s.position("BTCUSDT").quantity == Decimal("-2")
        assert s.position("BTCUSDT").avg_entry_price == Decimal("120")
        assert s.realized_pnl == Decimal("20")

    def test_fee_reduces_realized_pnl(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        s.apply_fill(_fill("120", "1", fee="0.5"), "BTCUSDT", Side.SELL)
        assert s.realized_pnl == Decimal("19.5")

    def test_unrealized_pnl_uses_mark(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "2"), "BTCUSDT", Side.BUY)
        s.update_mark("BTCUSDT", Decimal("110"))
        assert s.unrealized_pnl == Decimal("20")
        assert s.equity == Decimal("1020")

    def test_equity_peak_tracks_high_water_mark(self) -> None:
        s = RiskState(Decimal("1000"))
        s.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        s.update_mark("BTCUSDT", Decimal("150"))
        assert s.equity_peak == Decimal("1050")
        s.update_mark("BTCUSDT", Decimal("90"))
        assert s.equity_peak == Decimal("1050")  # não baixa
        assert s.drawdown_pct == Decimal("60") / Decimal("1050")

    def test_open_orders_counter(self) -> None:
        s = RiskState(Decimal("1000"))
        s.inc_open_orders("BTCUSDT")
        s.inc_open_orders("BTCUSDT")
        assert s.open_orders("BTCUSDT") == 2
        s.dec_open_orders("BTCUSDT")
        assert s.open_orders("BTCUSDT") == 1
        # dec abaixo de zero é no-op
        s.dec_open_orders("BTCUSDT")
        s.dec_open_orders("BTCUSDT")
        assert s.open_orders("BTCUSDT") == 0


# ─────────── RiskLimits ───────────


class TestRiskLimits:
    def test_derived_usd_limits(self) -> None:
        lim = _limits(capital="1000", dd_pct="0.03", pos_pct="0.30")
        assert lim.max_daily_drawdown_usd == Decimal("30.00")
        assert lim.max_position_per_side_usd == Decimal("300.00")


# ─────────── RiskEngine — pre-trade gate ───────────


class TestPreTradeGate:
    def test_happy_path_allows(self) -> None:
        eng = RiskEngine(_limits())
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("1"), Decimal("100"))
        assert eng.check_pre_trade(intent) is None

    def test_zero_quantity_denied(self) -> None:
        eng = RiskEngine(_limits())
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("0"), Decimal("100"))
        assert eng.check_pre_trade(intent) is not None

    def test_zero_price_denied(self) -> None:
        eng = RiskEngine(_limits())
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("1"), Decimal("0"))
        assert eng.check_pre_trade(intent) is not None

    def test_position_at_limit_allowed(self) -> None:
        # capital 1000, pos limit 30% = 300 USD
        eng = RiskEngine(_limits())
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("3"), Decimal("100"))
        assert eng.check_pre_trade(intent) is None  # 300 == 300 (≤)

    def test_position_above_limit_denied(self) -> None:
        eng = RiskEngine(_limits())
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("4"), Decimal("100"))
        evt = eng.check_pre_trade(intent)
        assert evt is not None
        assert evt.event_type.value == "MAX_POSITION_BREACH"

    def test_position_considers_existing_inventory(self) -> None:
        eng = RiskEngine(_limits())
        # já comprou 2 a 100 = posição 200 USD
        eng.apply_fill(_fill("100", "2"), "BTCUSDT", Side.BUY)
        eng.update_mark("BTCUSDT", Decimal("100"))
        # tentar comprar mais 1.5 a 100 → projetado 350 > 300
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("1.5"), Decimal("100"))
        assert eng.check_pre_trade(intent) is not None

    def test_max_open_orders_limit(self) -> None:
        eng = RiskEngine(_limits(max_orders=2))
        eng.register_open_order("BTCUSDT")
        eng.register_open_order("BTCUSDT")
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("1"), Decimal("100"))
        assert eng.check_pre_trade(intent) is not None

    def test_halted_engine_denies_everything(self) -> None:
        eng = RiskEngine(_limits())
        eng.trigger_halt("manual test")
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("1"), Decimal("100"))
        evt = eng.check_pre_trade(intent)
        assert evt is not None
        assert evt.event_type.value == "MANUAL_KILL_SWITCH"


# ─────────── RiskEngine — drawdown halt ───────────


class TestDrawdownHalt:
    def test_drawdown_within_limit_does_not_halt(self) -> None:
        eng = RiskEngine(_limits(dd_pct="0.03"))
        eng.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        eng.update_mark("BTCUSDT", Decimal("99"))  # -1 = -0.1% DD
        assert not eng.is_halted()

    def test_drawdown_above_limit_halts(self) -> None:
        eng = RiskEngine(_limits(dd_pct="0.03", capital="1000"))
        eng.apply_fill(_fill("100", "1"), "BTCUSDT", Side.BUY)
        eng.update_mark("BTCUSDT", Decimal("50"))  # -50 = -5% DD > 3%
        assert eng.is_halted()
        assert "drawdown" in (eng.halt_reason() or "")

    def test_halt_is_idempotent(self) -> None:
        eng = RiskEngine(_limits())
        eng.trigger_halt("reason A")
        eng.trigger_halt("reason B")
        assert eng.halt_reason() == "reason A"

    def test_reset_halt_clears_state(self) -> None:
        eng = RiskEngine(_limits())
        eng.trigger_halt("test")
        eng.reset_halt()
        assert not eng.is_halted()
        assert eng.halt_reason() is None


# ─────────── RiskEngine — fail-closed ───────────


class TestFailClosed:
    def test_internal_error_results_in_deny(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = RiskEngine(_limits())

        def boom(_symbol: str) -> int:
            msg = "simulated"
            raise RuntimeError(msg)

        monkeypatch.setattr(eng._state, "open_orders", boom)
        intent = TradeIntent("BTCUSDT", Side.BUY, Decimal("1"), Decimal("100"))
        evt = eng.check_pre_trade(intent)
        assert evt is not None
        assert evt.severity.value == "CRITICAL"
