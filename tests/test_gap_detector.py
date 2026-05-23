"""Testes do validador de continuidade de streams."""

from __future__ import annotations

import pytest

from data.gap_detector import (
    EventTimeValidator,
    GapDetectedError,
    SequenceValidator,
    StalenessMonitor,
)


class TestSequenceValidator:
    def test_accepts_monotonic_ids(self) -> None:
        v = SequenceValidator(stream="btcusdt@depth20@100ms")
        v.check(1)
        v.check(2)
        v.check(100)
        assert v.last_id == 100

    def test_rejects_regression(self) -> None:
        v = SequenceValidator(stream="s")
        v.check(10)
        with pytest.raises(GapDetectedError, match="regression"):
            v.check(5)

    def test_rejects_repeat(self) -> None:
        v = SequenceValidator(stream="s")
        v.check(10)
        with pytest.raises(GapDetectedError):
            v.check(10)


class TestEventTimeValidator:
    def test_accepts_forward_time(self) -> None:
        v = EventTimeValidator(stream="btcusdt@trade")
        v.check(1_000)
        v.check(1_500)
        assert v.last_event_ms == 1_500

    def test_tolerates_small_jitter(self) -> None:
        v = EventTimeValidator(stream="s", max_backwards_ms=1_000)
        v.check(10_000)
        v.check(9_500)  # 500ms back — dentro da tolerância
        assert v.last_event_ms == 10_000  # não regride

    def test_rejects_large_regression(self) -> None:
        v = EventTimeValidator(stream="s", max_backwards_ms=500)
        v.check(10_000)
        with pytest.raises(GapDetectedError, match="event time"):
            v.check(8_000)


class TestStalenessMonitor:
    def test_not_stale_before_touch(self) -> None:
        mon = StalenessMonitor("s", stale_after_ms=1_000)
        assert mon.is_stale(now_ms=999_999) is False

    def test_stale_after_threshold(self) -> None:
        mon = StalenessMonitor("s", stale_after_ms=500)
        mon.touch()
        last = mon._last_seen_ms
        assert mon.is_stale(now_ms=last + 501) is True
        assert mon.is_stale(now_ms=last + 100) is False
