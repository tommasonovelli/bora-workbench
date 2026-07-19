"""Deterministic aggregate VRAM monitoring tests without a real NVIDIA GPU."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import qwen_launcher._calibration_vram as vram_module
import qwen_launcher._hardware_monitoring as monitoring
from qwen_launcher._calibration_vram import (
    VramEnvironmentError,
    VramError,
    VramMonitor,
    VramThresholds,
)
from qwen_launcher._hardware_monitoring import GpuSnapshot


def snapshot(
    free: float, pids: tuple[int, ...] = (), driver: str = "610.47", *, is_wddm: bool = False
) -> GpuSnapshot:
    """Build one fixed 8 GiB aggregate GPU observation."""
    return GpuSnapshot(8, free, driver, pids, is_wddm)


def query_sequence(
    polled: GpuSnapshot,
    releases: tuple[GpuSnapshot, ...],
    baseline: GpuSnapshot | None = None,
):
    """Return a thread-aware query and event for baseline, workload, and release calls."""
    observed = threading.Event()
    main_calls = 0

    def query(index: int) -> GpuSnapshot:
        """Serve baseline/release on the owner thread and workload on the poller."""
        nonlocal main_calls
        assert index == 0
        if threading.current_thread().name == "qwen-calibration-vram":
            observed.set()
            return polled
        main_calls += 1
        if main_calls == 1:
            return baseline or snapshot(7)
        release_index = min(main_calls - 2, len(releases) - 1)
        return releases[release_index]

    return query, observed


def monitor_for(query, tolerance: float = 0) -> VramMonitor:
    """Build one monitor with an explicit reserve and release tolerance."""
    return VramMonitor(0, VramThresholds(1, tolerance), query)


def test_monitor_records_peak_reserve_and_clean_release() -> None:
    """Measure aggregate peak, reserve, and the final clean release sample."""
    query, observed = query_sequence(snapshot(1.5, (42,)), (snapshot(7),))
    monitor = monitor_for(query)

    monitor.start()
    assert observed.wait(timeout=1)
    summary = monitor.finish(42)

    assert summary.baseline_used_gib == 1
    assert summary.peak_used_gib == 6.5
    assert summary.minimum_free_gib == 1.5
    assert summary.release_used_gib == 1
    assert summary.driver_version == "610.47"


def test_release_stabilizes_within_window(monkeypatch) -> None:
    """Accept delayed CUDA release once a later 250 ms sample reaches tolerance."""
    releases = (snapshot(6.7), snapshot(6.95))
    query, observed = query_sequence(snapshot(2, (42,)), releases)
    monkeypatch.setattr(vram_module.time, "sleep", lambda seconds: None)
    monitor = monitor_for(query, tolerance=0.1)

    monitor.start()
    assert observed.wait(timeout=1)
    summary = monitor.finish(42)

    assert summary.release_used_gib == pytest.approx(1.05)


def test_release_within_explicit_tolerance_is_valid() -> None:
    """Accept environmental VRAM noise no larger than the operator-supplied tolerance."""
    query, observed = query_sequence(snapshot(2, (42,)), (snapshot(6.9),))
    monitor = monitor_for(query, tolerance=0.125)

    monitor.start()
    assert observed.wait(timeout=1)

    assert monitor.finish(42).release_used_gib == pytest.approx(1.1)


def test_release_beyond_window_retains_summary(monkeypatch) -> None:
    """Discard persistent retained memory while preserving its final release sample."""
    query, observed = query_sequence(snapshot(2, (42,)), (snapshot(6),))
    monkeypatch.setattr(vram_module, "_RELEASE_STABILIZATION_SECONDS", 0)
    monitor = monitor_for(query, tolerance=0.125)
    monitor.start()
    assert observed.wait(timeout=1)

    with pytest.raises(VramError, match="stabilize") as captured:
        monitor.finish(42)

    assert captured.value.summary is not None
    assert captured.value.summary.release_used_gib == 2


def test_concurrent_compute_load_blocks_before_candidate_start() -> None:
    """Reject pre-existing compute PIDs instead of attributing their memory to calibration."""
    monitor = monitor_for(lambda index: snapshot(6, (999,)))

    with pytest.raises(VramError, match="concurrent"):
        monitor.start()


def test_stable_wddm_desktop_contexts_are_part_of_the_aggregate_baseline() -> None:
    """Allow WDDM's persistent desktop contexts while accounting for their aggregate VRAM."""
    baseline = snapshot(7, (100,), is_wddm=True)
    workload = snapshot(2, (42, 100), is_wddm=True)
    release = snapshot(7, (100,), is_wddm=True)
    query, observed = query_sequence(workload, (release,), baseline)
    monitor = monitor_for(query)

    monitor.start()
    assert observed.wait(timeout=1)
    assert monitor.finish(42).release_used_gib == 1


def test_new_wddm_context_invalidates_the_run() -> None:
    """Reject a WDDM context that appears after the measured desktop baseline."""
    baseline = snapshot(7, (100,), is_wddm=True)
    workload = snapshot(2, (42, 100, 999), is_wddm=True)
    release = snapshot(7, (100,), is_wddm=True)
    query, observed = query_sequence(workload, (release,), baseline)
    monitor = monitor_for(query)

    monitor.start()
    assert observed.wait(timeout=1)
    with pytest.raises(VramEnvironmentError, match="concurrent"):
        monitor.finish(42)


def test_monitor_query_failure_invalidates_the_run() -> None:
    """Classify a failed baseline query as unreliable environmental evidence."""
    monitor = monitor_for(lambda index: (_ for _ in ()).throw(OSError("query failed")))

    with pytest.raises(VramEnvironmentError, match="GPU monitoring failed"):
        monitor.start()


def test_driver_change_during_trial_invalidates_the_run() -> None:
    """Reject a driver identity that changes between baseline and workload samples."""
    query, observed = query_sequence(snapshot(2, (42,), "620.00"), (snapshot(7),))
    monitor = monitor_for(query)
    monitor.start()
    assert observed.wait(timeout=1)

    with pytest.raises(VramEnvironmentError, match="driver version changed"):
        monitor.finish(42)


def test_reserve_violation_retains_measured_summary() -> None:
    """Discard a reserve violation while retaining real non-null CUDA evidence."""
    query, observed = query_sequence(snapshot(0.5, (42,)), (snapshot(7),))
    monitor = monitor_for(query)
    monitor.start()
    assert observed.wait(timeout=1)

    with pytest.raises(VramError, match="reserve") as captured:
        monitor.finish(42)

    assert captured.value.summary is not None


def test_hardware_snapshot_query_reads_memory_driver_and_compute_pids(monkeypatch) -> None:
    """Use bounded shell-free nvidia-smi queries for all calibration monitoring facts."""
    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="8192, 7000, 610.47, WDDM\n"),
            SimpleNamespace(stdout="42\n7\n"),
        ]
    )
    monkeypatch.setattr(monitoring.subprocess, "run", run)

    result = monitoring.query_gpu_snapshot(0)

    assert result.vram_total_gib == 8
    assert result.vram_free_gib == 7000 / 1024
    assert result.compute_pids == (7, 42)
    assert result.is_wddm
    for call in run.call_args_list:
        assert call.kwargs["timeout"] == 5
        assert "shell" not in call.kwargs
