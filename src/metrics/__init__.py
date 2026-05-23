"""Exportação de métricas Prometheus.

Implementação completa na Fase 4.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ─────────── Latência ───────────
WS_EVENT_LATENCY_MS = Histogram(
    "mdd_ws_event_latency_ms",
    "Latência entre timestamp do exchange e processamento local (ms).",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000),
)

ORDER_SUBMIT_LATENCY_MS = Histogram(
    "mdd_order_submit_latency_ms",
    "Latência entre intenção e ACK da exchange (ms).",
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 5000),
)

# ─────────── Estratégia ───────────
QUOTE_UPDATES = Counter(
    "mdd_quote_updates_total",
    "Atualizações de cotação emitidas pela estratégia.",
    labelnames=("symbol", "side"),
)

FILLS = Counter(
    "mdd_fills_total",
    "Fills recebidos.",
    labelnames=("symbol", "side", "is_maker"),
)

INVENTORY = Gauge(
    "mdd_inventory",
    "Inventário atual por símbolo (quantidade base).",
    labelnames=("symbol",),
)

EQUITY_USD = Gauge(
    "mdd_equity_usd",
    "Equity total marcado a mercado (USD).",
)

PNL_REALIZED_USD = Gauge(
    "mdd_pnl_realized_usd",
    "PnL realizado acumulado (USD).",
)

PNL_UNREALIZED_USD = Gauge(
    "mdd_pnl_unrealized_usd",
    "PnL não realizado (USD).",
)

# ─────────── Risk ───────────
RISK_EVENTS = Counter(
    "mdd_risk_events_total",
    "Eventos disparados pelo Risk Engine.",
    labelnames=("event_type", "severity"),
)

HALTED = Gauge(
    "mdd_halted",
    "1 se sistema está em halt (kill switch ativado), 0 caso contrário.",
)
