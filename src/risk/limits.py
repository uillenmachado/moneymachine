"""Limites de risco — typed, baseados em Decimal.

Imutáveis (msgspec.Struct frozen). Carregam-se de `core.config.RiskSettings`
via `RiskLimits.from_settings()`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from core.config import RiskSettings


class RiskLimits(msgspec.Struct, frozen=True):
    """Configuração imutável de limites de risco.

    Todos os percentuais são frações sobre `capital_usd` (ex.: 0.30 = 30%).
    """

    capital_usd: Decimal
    max_daily_drawdown_pct: Decimal  # ex.: Decimal("0.03")
    max_position_per_side_pct: Decimal  # ex.: Decimal("0.30")
    max_open_orders_per_symbol: int = 20
    latency_p99_ms_limit: int = 500
    inventory_skew_limit: Decimal = Decimal("0.5")

    @classmethod
    def from_settings(cls, settings: RiskSettings, capital_usd: float) -> RiskLimits:
        return cls(
            capital_usd=Decimal(str(capital_usd)),
            max_daily_drawdown_pct=Decimal(str(settings.max_daily_drawdown_pct)) / Decimal(100),
            max_position_per_side_pct=Decimal(str(settings.max_position_per_side_pct))
            / Decimal(100),
            latency_p99_ms_limit=settings.latency_p99_ms_limit,
            inventory_skew_limit=Decimal(str(settings.inventory_skew_limit)),
        )

    @property
    def max_daily_drawdown_usd(self) -> Decimal:
        return self.capital_usd * self.max_daily_drawdown_pct

    @property
    def max_position_per_side_usd(self) -> Decimal:
        return self.capital_usd * self.max_position_per_side_pct


__all__ = ["RiskLimits"]
