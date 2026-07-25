"""Integration tests for run-scoped context identities in the VRAM monitor."""

from __future__ import annotations

import threading

import pytest

from bora_workbench._calibration_gpu_contexts import GpuContextBaseline
from bora_workbench._calibration_vram import (
    VramEnvironmentError,
    VramMonitor,
    VramThresholds,
)
from bora_workbench._gpu_process_identity import GpuProcessIdentity
from bora_workbench._hardware_monitoring import GpuSnapshot


def context(pid: int, created: float, executable: str) -> GpuProcessIdentity:
    """Build one complete process instance for context matching."""
    return GpuProcessIdentity(pid, created, executable)


def snapshot(free: float, *items: GpuProcessIdentity) -> GpuSnapshot:
    """Build one WDDM sample with aligned PID and opaque identity evidence."""
    pids = tuple(item.pid for item in items)
    return GpuSnapshot(8.0, free, "610.47", pids, True, None, items)


def sequence(baseline: GpuSnapshot, workload: GpuSnapshot, release: GpuSnapshot):
    """Serve owner-thread baseline/release samples and poller workload samples."""
    observed = threading.Event()
    owner_calls = 0

    def query(index: int) -> GpuSnapshot:
        """Return one deterministic sample for the monitor's calling thread."""
        nonlocal owner_calls
        assert index == 0
        if threading.current_thread().name == "qwen-calibration-vram":
            observed.set()
            return workload
        owner_calls += 1
        return baseline if owner_calls == 1 else release

    return query, observed


def test_monitor_admits_and_records_same_file_process_replacement() -> None:
    """Keep a clean trial when a baseline executable respawns without extra multiplicity."""
    original = context(100, 1.0, "desktop")
    replacement = context(200, 2.0, "desktop")
    managed = context(42, 3.0, "server")
    query, observed = sequence(
        snapshot(7.0, original),
        snapshot(2.0, replacement, managed),
        snapshot(7.0, replacement),
    )
    monitor = VramMonitor(
        0, VramThresholds(0.5, 0.125), query, GpuContextBaseline(True, (original,))
    )

    monitor.start()
    assert observed.wait(timeout=1)
    summary = monitor.finish(managed)

    assert summary.context_replacement_count == 1


def test_monitor_still_invalidates_a_new_executable_file() -> None:
    """Reject a genuinely new WDDM executable while preserving the strict run boundary."""
    original = context(100, 1.0, "desktop")
    intruder = context(200, 2.0, "other")
    query, observed = sequence(
        snapshot(7.0, original), snapshot(2.0, intruder), snapshot(7.0, original)
    )
    monitor = VramMonitor(
        0, VramThresholds(0.5, 0.125), query, GpuContextBaseline(True, (original,))
    )

    monitor.start()
    assert observed.wait(timeout=1)
    with pytest.raises(VramEnvironmentError, match="contaminated"):
        monitor.finish(None)
