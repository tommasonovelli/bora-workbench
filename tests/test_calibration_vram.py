"""Deterministic aggregate VRAM monitoring tests without a real NVIDIA GPU."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import qwen_launcher._hardware_monitoring as monitoring
from qwen_launcher._calibration_vram import VramError, VramMonitor
from qwen_launcher._hardware_monitoring import GpuSnapshot


def snapshot(free: float, pids: tuple[int, ...] = ()) -> GpuSnapshot:
    """Build one fixed 8 GiB aggregate GPU observation."""
    return GpuSnapshot(8, free, "610.47", pids)


def query_sequence(polled: GpuSnapshot, released: GpuSnapshot):
    """Return a thread-aware query and event that distinguish baseline/poll/release calls."""
    observed = threading.Event()
    main_calls = 0

    def query(index: int) -> GpuSnapshot:
        """Serve baseline/release on the owner thread and run samples on the poller thread."""
        nonlocal main_calls
        assert index == 0
        if threading.current_thread().name == "qwen-calibration-vram":
            observed.set()
            return polled
        main_calls += 1
        return snapshot(7) if main_calls == 1 else released

    return query, observed


def test_monitor_records_peak_reserve_and_clean_release() -> None:
    """Measure aggregate peak/minimum free VRAM and permit only the managed compute PID."""
    query, observed = query_sequence(snapshot(1.5, (42,)), snapshot(7))
    monitor = VramMonitor(0, 1, query)

    monitor.start()
    assert observed.wait(timeout=1)
    summary = monitor.finish(42)

    assert summary.baseline_used_gib == 1
    assert summary.peak_used_gib == 6.5
    assert summary.minimum_free_gib == 1.5
    assert summary.driver_version == "610.47"


def test_concurrent_compute_load_blocks_before_candidate_start() -> None:
    """Reject pre-existing compute PIDs instead of attributing their memory to calibration."""
    monitor = VramMonitor(0, 1, lambda index: snapshot(6, (999,)))

    with pytest.raises(VramError, match="concurrent"):
        monitor.start()


@pytest.mark.parametrize(
    ("polled", "released", "match"),
    [(snapshot(0.5, (42,)), snapshot(7), "reserve"), (snapshot(2, (42,)), snapshot(6), "baseline")],
)
def test_invalid_reserve_or_unreleased_memory_retains_measured_summary(
    polled: GpuSnapshot, released: GpuSnapshot, match: str
) -> None:
    """Discard invalid candidates while retaining real non-null CUDA memory evidence."""
    query, observed = query_sequence(polled, released)
    monitor = VramMonitor(0, 1, query)
    monitor.start()
    assert observed.wait(timeout=1)

    with pytest.raises(VramError, match=match) as captured:
        monitor.finish(42)

    assert captured.value.summary is not None


def test_hardware_snapshot_query_reads_memory_driver_and_compute_pids(monkeypatch) -> None:
    """Use bounded shell-free nvidia-smi queries for all calibration monitoring facts."""
    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="8192, 7000, 610.47\n"),
            SimpleNamespace(stdout="42\n7\n"),
        ]
    )
    monkeypatch.setattr(monitoring.subprocess, "run", run)

    result = monitoring.query_gpu_snapshot(0)

    assert result.vram_total_gib == 8
    assert result.vram_free_gib == 7000 / 1024
    assert result.compute_pids == (7, 42)
    for call in run.call_args_list:
        assert call.kwargs["timeout"] == 5
        assert "shell" not in call.kwargs
