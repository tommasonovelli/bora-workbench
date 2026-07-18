"""Deterministic RAM monitoring tests for every calibration/v2 backend."""

from __future__ import annotations

import threading

import pytest

from qwen_launcher._calibration_ram import RamError, RamMonitor


def query_sequence(polled_gib: float):
    """Return a thread-aware query serving the baseline on the owner thread."""
    observed = threading.Event()

    def query() -> float:
        """Serve the workload minimum on the poller and the baseline elsewhere."""
        if threading.current_thread().name == "qwen-calibration-ram":
            observed.set()
            return polled_gib
        return 24.0

    return query, observed


def test_monitor_records_baseline_and_minimum_available() -> None:
    """Track the measured RAM minimum that the record headroom check will reuse."""
    query, observed = query_sequence(18.5)
    monitor = RamMonitor(query)

    monitor.start()
    assert observed.wait(timeout=1)
    summary = monitor.finish()

    assert summary.baseline_available_gib == 24.0
    assert summary.minimum_available_gib == 18.5
    assert summary.needed_gib == pytest.approx(5.5)


def test_query_failure_invalidates_the_run() -> None:
    """Surface an unreliable monitor instead of recording partial RAM evidence."""
    observed = threading.Event()

    def failing() -> float:
        """Fail only on the polling thread to exercise error propagation."""
        if threading.current_thread().name == "qwen-calibration-ram":
            observed.set()
            raise OSError("psutil failed")
        return 24.0

    monitor = RamMonitor(failing)
    monitor.start()
    assert observed.wait(timeout=1)

    with pytest.raises(RamError, match="RAM monitoring failed"):
        monitor.finish()


def test_unstarted_monitor_is_rejected() -> None:
    """Refuse to fabricate a summary for a monitor that never sampled."""
    with pytest.raises(RamError, match="not started"):
        RamMonitor(lambda: 24.0).finish()
