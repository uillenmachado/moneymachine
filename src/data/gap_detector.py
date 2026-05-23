"""Validador de continuidade de streams WebSocket.

Detecta:
- Regressão / repetição de identificadores de sequência (`lastUpdateId`).
- Regressão de event time (clock fora de ordem).
- Stale stream (sem mensagens por > `stale_after_ms`).

Falhas levantam `GapDetected` para que o cliente WS reconecte e
re-sincronize. Métricas Prometheus registradas em `metrics.WS_GAPS_DETECTED`.
"""

from __future__ import annotations

import time

import msgspec

from metrics import WS_GAPS_DETECTED


class GapDetectedError(Exception):
    """Lançada quando uma descontinuidade no stream é detectada."""


class SequenceValidator(msgspec.Struct):
    """Valida monotonia estrita de `lastUpdateId` (ou similar)."""

    stream: str
    last_id: int = 0

    def check(self, new_id: int) -> None:
        if self.last_id and new_id <= self.last_id:
            WS_GAPS_DETECTED.labels(stream=self.stream).inc()
            msg = f"sequence regression on {self.stream}: last={self.last_id} new={new_id}"
            raise GapDetectedError(msg)
        self.last_id = new_id


class EventTimeValidator(msgspec.Struct):
    """Valida que event time não regride além de um drift tolerado."""

    stream: str
    max_backwards_ms: int = 1000
    last_event_ms: int = 0

    def check(self, event_ms: int) -> None:
        if self.last_event_ms and event_ms + self.max_backwards_ms < self.last_event_ms:
            WS_GAPS_DETECTED.labels(stream=self.stream).inc()
            msg = (
                f"event time regression on {self.stream}: last={self.last_event_ms} new={event_ms}"
            )
            raise GapDetectedError(msg)
        self.last_event_ms = max(self.last_event_ms, event_ms)


class StalenessMonitor:
    """Marca o tempo da última mensagem; permite checar staleness."""

    __slots__ = ("_last_seen_ms", "stale_after_ms", "stream")

    def __init__(self, stream: str, stale_after_ms: int = 5_000) -> None:
        self.stream = stream
        self.stale_after_ms = stale_after_ms
        self._last_seen_ms: int = 0

    def touch(self) -> None:
        self._last_seen_ms = int(time.time() * 1000)

    def is_stale(self, now_ms: int | None = None) -> bool:
        if self._last_seen_ms == 0:
            return False
        current = now_ms if now_ms is not None else int(time.time() * 1000)
        return (current - self._last_seen_ms) > self.stale_after_ms
