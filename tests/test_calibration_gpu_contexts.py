"""Offline tests for calibration/v3's immutable run-scoped WDDM context population."""

from __future__ import annotations

import pytest

import qwen_launcher._calibration_gpu_contexts as contexts_module
from qwen_launcher._calibration_gpu_contexts import (
    GpuContextBaseline,
    capture_gpu_context_baseline,
    count_context_replacements,
    validate_gpu_contexts,
)
from qwen_launcher._calibration_vram import VramEnvironmentError
from qwen_launcher._gpu_process_identity import GpuProcessIdentity
from qwen_launcher._hardware_monitoring import GpuSnapshot


def context(pid: int, created: float, executable: str) -> GpuProcessIdentity:
    """Build one complete opaque compute-process identity."""
    return GpuProcessIdentity(pid, created, executable)


def snapshot(*items: GpuProcessIdentity, is_wddm: bool = True) -> GpuSnapshot:
    """Build one fixed-memory GPU sample with aligned process identities."""
    pids = tuple(item.pid for item in items)
    return GpuSnapshot(8.0, 7.0, "610.47", pids, is_wddm, None, items)


def test_same_file_replacement_is_evidence_not_contamination() -> None:
    """Admit one baseline executable replacement and count its new process instance."""
    original = context(100, 1.0, "file-a")
    replacement = context(200, 2.0, "file-a")
    baseline = GpuContextBaseline(True, (original,))

    observed = validate_gpu_contexts(snapshot(replacement), baseline, None)

    assert observed == {(200, 2.0)}
    assert count_context_replacements([snapshot(replacement)], baseline, None) == 1


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
        validate_gpu_contexts(snapshot(*current), baseline, None)


def test_pid_reuse_cannot_impersonate_baseline_or_managed_server() -> None:
    """Require executable identity for baseline and pid/create-time for the managed process."""
    baseline_process = context(100, 1.0, "file-a")
    baseline = GpuContextBaseline(True, (baseline_process,))
    recycled_baseline_pid = context(100, 2.0, "file-b")
    managed = GpuProcessIdentity(42, 3.0, None)
    recycled_managed_pid = context(42, 4.0, "file-b")

    assert validate_gpu_contexts(snapshot(baseline_process, managed), baseline, managed) == set()
    with pytest.raises(VramEnvironmentError):
        validate_gpu_contexts(snapshot(recycled_baseline_pid), baseline, None)
    with pytest.raises(VramEnvironmentError):
        validate_gpu_contexts(snapshot(baseline_process, recycled_managed_pid), baseline, managed)


def test_baseline_capture_is_complete_and_immutable_across_trials(monkeypatch) -> None:
    """Capture once, admit later same-file turnover, and reject a persistent new file."""
    original = context(100, 1.0, "file-a")
    monkeypatch.setattr(contexts_module, "query_gpu_snapshot", lambda index: snapshot(original))
    baseline = capture_gpu_context_baseline(0)

    assert validate_gpu_contexts(snapshot(context(200, 2.0, "file-a")), baseline, None)
    with pytest.raises(VramEnvironmentError):
        validate_gpu_contexts(snapshot(context(300, 3.0, "file-b")), baseline, None)


def test_unreadable_initial_context_fails_before_process_work(monkeypatch) -> None:
    """Reject an incomplete run baseline instead of burning model probes predictably."""
    unknown = GpuProcessIdentity(100, None, None)
    monkeypatch.setattr(contexts_module, "query_gpu_snapshot", lambda index: snapshot(unknown))

    with pytest.raises(VramEnvironmentError, match="cannot identify"):
        capture_gpu_context_baseline(0)
