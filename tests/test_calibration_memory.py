"""Deterministic calibration memory tests without a real NVIDIA GPU or host measurement.

The suite covers the three evidence streams of one trial: aggregate VRAM with the run-scoped WDDM
context population, available RAM, and the log-based out-of-memory diagnosis.
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import bora_workbench._calibration_memory as memory_module
import bora_workbench.hardware as hardware
from bora_workbench._calibration_memory import (
    GpuContextBaseline,
    RamError,
    RamMonitor,
    RamReserveError,
    VramEnvironmentError,
    VramError,
    VramMonitor,
    VramReleaseError,
    VramReserveError,
    VramThresholds,
    capture_gpu_context_baseline,
    count_context_replacements,
    oom_resource,
    read_logs,
    validate_gpu_contexts,
)
from bora_workbench.hardware import GpuProcessIdentity, GpuSnapshot


def snapshot(
    free: float, pids: tuple[int, ...] = (), driver: str = "610.47", *, is_wddm: bool = False
) -> GpuSnapshot:
    """Build one fixed 8 GiB aggregate GPU observation."""
    return GpuSnapshot(8, free, driver, pids, is_wddm)


def context(pid: int, created: float, executable: str) -> GpuProcessIdentity:
    """Build one complete opaque compute-process identity."""
    return GpuProcessIdentity(pid, created, executable)


def context_snapshot(free: float, *items: GpuProcessIdentity) -> GpuSnapshot:
    """Build one WDDM sample with aligned PID and opaque identity evidence."""
    pids = tuple(item.pid for item in items)
    return GpuSnapshot(8.0, free, "610.47", pids, True, None, items)


def query_sequence(polled, releases, baseline=None):
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
    monkeypatch.setattr(memory_module.time, "sleep", lambda seconds: None)
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
    monkeypatch.setattr(memory_module, "_RELEASE_STABILIZATION_SECONDS", 0)
    monitor = monitor_for(query, tolerance=0.125)
    monitor.start()
    assert observed.wait(timeout=1)

    with pytest.raises(VramReleaseError, match="stabilize") as captured:
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

    with pytest.raises(VramReserveError, match="reserve") as captured:
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
    monkeypatch.setattr(hardware.subprocess, "run", run)

    result = hardware.query_gpu_snapshot(0)

    assert result.vram_total_gib == 8
    assert result.vram_free_gib == 7000 / 1024
    assert result.compute_pids == (7, 42)
    assert result.is_wddm
    for call in run.call_args_list:
        assert call.kwargs["timeout"] == 5
        assert "shell" not in call.kwargs


def test_monitor_admits_and_records_same_file_process_replacement() -> None:
    """Keep a clean trial when a baseline executable respawns without extra multiplicity."""
    original = context(100, 1.0, "desktop")
    replacement = context(200, 2.0, "desktop")
    managed = context(42, 3.0, "server")
    query, observed = query_sequence(
        context_snapshot(2.0, replacement, managed),
        (context_snapshot(7.0, replacement),),
        context_snapshot(7.0, original),
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
    query, observed = query_sequence(
        context_snapshot(2.0, intruder),
        (context_snapshot(7.0, original),),
        context_snapshot(7.0, original),
    )
    monitor = VramMonitor(
        0, VramThresholds(0.5, 0.125), query, GpuContextBaseline(True, (original,))
    )

    monitor.start()
    assert observed.wait(timeout=1)
    with pytest.raises(VramEnvironmentError, match="contaminated"):
        monitor.finish(None)


def test_same_file_replacement_is_evidence_not_contamination() -> None:
    """Admit one baseline executable replacement and count its new process instance."""
    original = context(100, 1.0, "file-a")
    replacement = context(200, 2.0, "file-a")
    baseline = GpuContextBaseline(True, (original,))

    observed = validate_gpu_contexts(context_snapshot(7.0, replacement), baseline, None)

    assert observed == {(200, 2.0)}
    assert count_context_replacements([context_snapshot(7.0, replacement)], baseline, None) == 1


@pytest.mark.parametrize(
    "current",
    [
        (context(200, 2.0, "file-b"),),
        (context(100, 1.0, "file-a"), context(200, 2.0, "file-a")),
        (GpuProcessIdentity(200, None, None),),
    ],
)
def test_new_file_extra_multiplicity_and_unknown_identity_fail_closed(current) -> None:
    """Reject every population that is not a complete sub-multiset of the run baseline."""
    baseline = GpuContextBaseline(True, (context(100, 1.0, "file-a"),))

    with pytest.raises(VramEnvironmentError):
        validate_gpu_contexts(context_snapshot(7.0, *current), baseline, None)


def test_pid_reuse_cannot_impersonate_baseline_or_managed_server() -> None:
    """Require executable identity for baseline and pid/create-time for the managed process."""
    baseline_process = context(100, 1.0, "file-a")
    baseline = GpuContextBaseline(True, (baseline_process,))
    recycled_baseline_pid = context(100, 2.0, "file-b")
    managed = GpuProcessIdentity(42, 3.0, None)
    recycled_managed_pid = context(42, 4.0, "file-b")

    admitted = validate_gpu_contexts(
        context_snapshot(7.0, baseline_process, managed), baseline, managed
    )

    assert admitted == set()
    with pytest.raises(VramEnvironmentError):
        validate_gpu_contexts(context_snapshot(7.0, recycled_baseline_pid), baseline, None)
    with pytest.raises(VramEnvironmentError):
        validate_gpu_contexts(
            context_snapshot(7.0, baseline_process, recycled_managed_pid), baseline, managed
        )


def test_baseline_capture_is_complete_and_immutable_across_trials(monkeypatch) -> None:
    """Capture once, admit later same-file turnover, and reject a persistent new file."""
    original = context(100, 1.0, "file-a")
    monkeypatch.setattr(
        memory_module, "query_gpu_snapshot", lambda index: context_snapshot(7.0, original)
    )
    baseline = capture_gpu_context_baseline(0)

    assert validate_gpu_contexts(context_snapshot(7.0, context(200, 2.0, "file-a")), baseline, None)
    with pytest.raises(VramEnvironmentError):
        validate_gpu_contexts(context_snapshot(7.0, context(300, 3.0, "file-b")), baseline, None)


def test_unreadable_initial_context_fails_before_process_work(monkeypatch) -> None:
    """Reject an incomplete run baseline instead of burning model probes predictably."""
    unknown = GpuProcessIdentity(100, None, None)
    monkeypatch.setattr(
        memory_module, "query_gpu_snapshot", lambda index: context_snapshot(7.0, unknown)
    )

    with pytest.raises(VramEnvironmentError, match="cannot identify"):
        capture_gpu_context_baseline(0)


def ram_query_sequence(polled_gib: float):
    """Return a thread-aware query serving the baseline on the owner thread."""
    observed = threading.Event()

    def query() -> float:
        """Serve the workload minimum on the poller and the baseline elsewhere."""
        if threading.current_thread().name == "qwen-calibration-ram":
            observed.set()
            return polled_gib
        return 24.0

    return query, observed


def test_ram_monitor_records_baseline_and_minimum_available() -> None:
    """Track the measured RAM minimum that the record headroom check will reuse."""
    query, observed = ram_query_sequence(18.5)
    monitor = RamMonitor(query)

    monitor.start()
    assert observed.wait(timeout=1)
    summary = monitor.finish()

    assert summary.baseline_available_gib == 24.0
    assert summary.minimum_available_gib == 18.5
    assert summary.needed_gib == pytest.approx(5.5)


def test_universal_reserve_violation_retains_candidate_evidence() -> None:
    """Make one trial infeasible while preserving its measured RAM summary."""
    query, observed = ram_query_sequence(1.5)
    monitor = RamMonitor(query, minimum_free_gib=2.0)

    monitor.start()
    assert observed.wait(timeout=1)
    with pytest.raises(RamReserveError, match="reserve") as captured:
        monitor.finish()

    assert captured.value.summary.minimum_available_gib == 1.5


def test_ram_query_failure_invalidates_the_run() -> None:
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


def test_ram_baseline_query_failure_invalidates_the_run() -> None:
    """Classify a baseline monitor failure as unreliable environment evidence."""
    monitor = RamMonitor(lambda: (_ for _ in ()).throw(OSError("psutil failed")))

    with pytest.raises(RamError, match="RAM monitoring failed"):
        monitor.start()


def test_unstarted_ram_monitor_is_rejected() -> None:
    """Refuse to fabricate a summary for a monitor that never sampled."""
    with pytest.raises(RamError, match="not started"):
        RamMonitor(lambda: 24.0).finish()


_CUDA_FAILURE = (
    "ggml_backend_cuda_buffer_type_alloc_buffer: allocating 11807.70 MiB on device 0: "
    "cudaMalloc failed: out of memory\n"
    "llama_model_load: error loading model: unable to allocate CUDA0 buffer\n"
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (_CUDA_FAILURE, "vram"),
        ("ggml_backend_cpu_buffer_type_alloc_buffer: out of memory", "ram"),
        ("srv load_model: OOM while preparing the host buffer", "ram"),
        ("srv init: renderer zoom failure", None),
        ("srv init: model loaded", None),
        ("", None),
    ],
)
def test_oom_resource_names_only_the_failing_device(text: str, expected: str | None) -> None:
    """Name the exhausted resource from the failing line, never from unrelated log context."""
    assert oom_resource(text) == expected


def test_device_marker_is_read_per_line_not_per_log() -> None:
    """Keep a CUDA banner elsewhere from turning a host allocation failure into a GPU one."""
    log = "ggml_cuda_init: found 1 CUDA device\nfailed to allocate host buffer: out of memory\n"
    assert oom_resource(log) == "ram"


def test_read_logs_skips_unreadable_paths(tmp_path: Path) -> None:
    """Concatenate the logs this run can open and ignore the ones it cannot."""
    present = tmp_path / "server.log"
    present.write_text("out of memory on device 0\n", encoding="utf-8")
    text = read_logs((present, tmp_path / "missing.log"))
    assert oom_resource(text) == "vram"
