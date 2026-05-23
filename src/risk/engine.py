"""RiskEngine — gate de pré-trade + estado + kill switch.

Princípios (`.github/instructions/risk-engine.instructions.md`):
- Falha fechado: qualquer erro interno vira `deny`.
- Idempotente: `trigger_halt()` chamado N vezes é equivalente a 1.
- Decisões determinísticas dado o estado.
- Sem float em decisão financeira.

Esta classe é stateful e NÃO thread-safe — uso esperado é a partir de uma
única corrotina (event loop principal) OU protegida por `asyncio.Lock`.
Isolamento via `multiprocessing` é deployment-concern (Fase 6).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec
import structlog

from metrics import HALTED, RISK_EVENTS
from risk.state import RiskState

if TYPE_CHECKING:
    from core.types import Fill, Side
    from risk.limits import RiskLimits

logger = structlog.get_logger(__name__)


# Reuso dos tipos públicos definidos em src/risk/__init__.py
from risk import RiskEvent, RiskEventType, RiskSeverity  # noqa: E402


class TradeIntent(msgspec.Struct, frozen=True):
    """Intenção de ordem antes de submeter ao OMS."""

    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal  # preço esperado (para cálculo de notional)

    @property
    def notional_usd(self) -> Decimal:
        return self.quantity * self.price


class RiskEngine:
    """Gate de risco + estado + kill switch.

    Implementa o protocolo `RiskGate` definido em `src/risk/__init__.py`,
    mas com assinatura `check_pre_trade(intent)` mais rica (intent inclui
    símbolo + preço, necessário para checagem por-símbolo).
    """

    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits
        self._state = RiskState(limits.capital_usd)
        self._halted: bool = False
        self._halt_reason: str | None = None

    # ─────────── Snapshot público ───────────

    @property
    def state(self) -> RiskState:
        return self._state

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def is_halted(self) -> bool:
        return self._halted

    def halt_reason(self) -> str | None:
        return self._halt_reason

    # ─────────── Atualização de estado ───────────

    def update_mark(self, symbol: str, price: Decimal) -> None:
        self._state.update_mark(symbol, price)
        self._auto_check_drawdown()

    def apply_fill(self, fill: Fill, symbol: str, side: Side) -> None:
        self._state.apply_fill(fill, symbol, side)
        self._auto_check_drawdown()

    def register_open_order(self, symbol: str) -> None:
        self._state.inc_open_orders(symbol)

    def register_closed_order(self, symbol: str) -> None:
        self._state.dec_open_orders(symbol)

    # ─────────── Pre-trade gate ───────────

    def check_pre_trade(self, intent: TradeIntent) -> RiskEvent | None:  # noqa: PLR0911
        """Retorna None se permitido. Retorna `RiskEvent` para bloquear."""
        try:
            if self._halted:
                return self._reject(
                    RiskEventType.MANUAL_KILL_SWITCH,
                    RiskSeverity.CRITICAL,
                    f"system halted: {self._halt_reason}",
                )

            if intent.quantity <= 0 or intent.price <= 0:
                return self._reject(
                    RiskEventType.MAX_POSITION_BREACH,
                    RiskSeverity.WARNING,
                    "intent inválido: quantidade/preço não-positivo",
                )

            # Limite de ordens abertas por símbolo
            if self._state.open_orders(intent.symbol) >= self._limits.max_open_orders_per_symbol:
                return self._reject(
                    RiskEventType.MAX_POSITION_BREACH,
                    RiskSeverity.WARNING,
                    f"max_open_orders ({self._limits.max_open_orders_per_symbol}) "
                    f"atingido para {intent.symbol}",
                )

            # Limite de posição por lado
            pos = self._state.position(intent.symbol)
            signed_delta = intent.quantity if intent.side.value == "BUY" else -intent.quantity
            projected_qty = pos.quantity + signed_delta
            projected_notional = abs(projected_qty) * intent.price
            if projected_notional > self._limits.max_position_per_side_usd:
                return self._reject(
                    RiskEventType.MAX_POSITION_BREACH,
                    RiskSeverity.WARNING,
                    f"posição projetada {projected_notional:.2f} USD excede limite "
                    f"{self._limits.max_position_per_side_usd:.2f} USD",
                )

            # Drawdown — bloqueia novas ordens se já estourou
            if self._state.drawdown_pct > self._limits.max_daily_drawdown_pct:
                return self._reject(
                    RiskEventType.MAX_DAILY_DRAWDOWN,
                    RiskSeverity.CRITICAL,
                    f"drawdown {self._state.drawdown_pct:.4f} excede limite "
                    f"{self._limits.max_daily_drawdown_pct:.4f}",
                )
            return None
        except Exception as exc:  # falha fechado
            logger.error("risk_engine_internal_error", exc_info=exc)
            return self._reject(
                RiskEventType.MANUAL_KILL_SWITCH,
                RiskSeverity.CRITICAL,
                f"erro interno do Risk Engine: {type(exc).__name__}",
            )

    # ─────────── Kill switch ───────────

    def trigger_halt(self, reason: str) -> None:
        """Idempotente — chamadas subsequentes mantêm o motivo original."""
        if self._halted:
            return
        self._halted = True
        self._halt_reason = reason
        HALTED.set(1)
        RISK_EVENTS.labels(
            event_type=RiskEventType.MANUAL_KILL_SWITCH.value,
            severity=RiskSeverity.CRITICAL.value,
        ).inc()
        logger.critical("risk_halt_triggered", reason=reason)

    def reset_halt(self) -> None:
        """Apenas para uso manual (intervenção). NÃO chamar automaticamente."""
        self._halted = False
        self._halt_reason = None
        HALTED.set(0)
        logger.warning("risk_halt_reset")

    # ─────────── Internals ───────────

    def _auto_check_drawdown(self) -> None:
        if self._halted:
            return
        if self._state.drawdown_pct > self._limits.max_daily_drawdown_pct:
            self.trigger_halt(
                f"drawdown {self._state.drawdown_pct:.4f} > "
                f"{self._limits.max_daily_drawdown_pct:.4f}"
            )

    def _reject(self, event_type: RiskEventType, severity: RiskSeverity, message: str) -> RiskEvent:
        RISK_EVENTS.labels(event_type=event_type.value, severity=severity.value).inc()
        logger.warning("risk_reject", event_type=event_type.value, message=message)
        return RiskEvent(event_type=event_type, severity=severity, message=message)


__all__ = ["RiskEngine", "TradeIntent"]
