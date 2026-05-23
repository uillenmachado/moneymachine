"""Risk Engine — circuit breaker isolado.

Roda em processo separado (multiprocessing) e tem autoridade suprema sobre
o OMS. Pode cancelar todas as ordens e fechar posições a mercado.

Implementação completa na Fase 4. Aqui apenas tipos de eventos.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

import msgspec


class RiskSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskEventType(StrEnum):
    MAX_DAILY_DRAWDOWN = "MAX_DAILY_DRAWDOWN"
    MAX_POSITION_BREACH = "MAX_POSITION_BREACH"
    LATENCY_BREACH = "LATENCY_BREACH"
    INVENTORY_SKEW = "INVENTORY_SKEW"
    HEARTBEAT_LOST = "HEARTBEAT_LOST"
    EXCHANGE_DISCONNECTED = "EXCHANGE_DISCONNECTED"
    MANUAL_KILL_SWITCH = "MANUAL_KILL_SWITCH"


class RiskEvent(msgspec.Struct, frozen=True):
    event_type: RiskEventType
    severity: RiskSeverity
    message: str
    metadata: dict[str, str | float | int] | None = None


class RiskGate(Protocol):
    """Contrato do portão de risco — toda ordem passa por aqui antes do OMS."""

    def check_pre_trade(self, intent_qty_usd: float, side: str) -> RiskEvent | None:
        """Retorna None se permitido, ou RiskEvent CRITICAL para bloquear."""
        ...

    def is_halted(self) -> bool: ...

    def trigger_halt(self, reason: str) -> None: ...
