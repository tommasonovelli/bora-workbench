"""Apply calibration/v5's immutable run-scoped WDDM executable baseline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from qwen_launcher._calibration_vram_types import VramEnvironmentError
from qwen_launcher._gpu_process_identity import GpuProcessIdentity
from qwen_launcher._hardware_monitoring import GpuSnapshot, query_gpu_snapshot


@dataclass(frozen=True, slots=True)
class GpuContextBaseline:
    """Hold the complete compute-process population captured once for a v5 run."""

    is_wddm: bool
    contexts: tuple[GpuProcessIdentity, ...]


def legacy_foreign_pids(
    snapshots: list[GpuSnapshot],
    baseline: GpuSnapshot,
    managed: GpuProcessIdentity | int | None,
) -> set[int]:
    """Preserve calibration/v1's historical per-trial exact-PID WDDM contract."""
    baseline_pids = set(baseline.compute_pids) if baseline.is_wddm else set()
    managed_pid = managed.pid if isinstance(managed, GpuProcessIdentity) else managed
    managed_pids = set() if managed_pid is None else {managed_pid}
    observed = set().union(*(set(snapshot.compute_pids) for snapshot in snapshots))
    return observed - baseline_pids - managed_pids


def _aligned_contexts(snapshot: GpuSnapshot) -> tuple[GpuProcessIdentity, ...]:
    """Return process identities aligned exactly with one NVIDIA PID snapshot."""
    contexts = snapshot.compute_contexts
    if contexts is None or len(contexts) != len(snapshot.compute_pids):
        raise VramEnvironmentError("GPU compute-process identity monitoring is unavailable")
    return contexts


def _require_complete(
    contexts: tuple[GpuProcessIdentity, ...],
) -> tuple[GpuProcessIdentity, ...]:
    """Reject every non-managed context whose executable identity is unavailable."""
    unknown = [item.pid for item in contexts if not item.is_complete]
    if unknown:
        pids = ", ".join(str(pid) for pid in unknown)
        raise VramEnvironmentError(f"cannot identify GPU compute context PIDs {pids}")
    return contexts


def capture_gpu_context_baseline(index: int) -> GpuContextBaseline:
    """Capture one immutable pre-run context baseline and reject unreadable identities early."""
    snapshot = query_gpu_snapshot(index)
    contexts = _require_complete(_aligned_contexts(snapshot))
    if contexts and not snapshot.is_wddm:
        pids = ", ".join(str(item.pid) for item in contexts)
        raise VramEnvironmentError(
            f"concurrent GPU compute workload detected before calibration (PIDs {pids}); stop it"
        )
    return GpuContextBaseline(snapshot.is_wddm, contexts)


def _visible_contexts(
    snapshot: GpuSnapshot, managed: GpuProcessIdentity | None
) -> tuple[GpuProcessIdentity, ...]:
    """Remove the exact managed instance before requiring complete foreign identities."""
    contexts = _aligned_contexts(snapshot)
    if managed is not None and managed.create_time is not None:
        contexts = tuple(item for item in contexts if item.instance != managed.instance)
    return _require_complete(contexts)


def _identity_counts(contexts: tuple[GpuProcessIdentity, ...]) -> Counter[str]:
    """Count complete executable identities without serializing their opaque values."""
    return Counter(item.executable_id for item in contexts if item.executable_id is not None)


def _reject_excess(current: tuple[GpuProcessIdentity, ...], baseline: GpuContextBaseline) -> None:
    """Reject new executable files or multiplicity above the immutable run baseline."""
    allowed = _identity_counts(baseline.contexts)
    observed = _identity_counts(current)
    excess = observed - allowed
    if not excess:
        return
    pids = [item.pid for item in current if item.executable_id in excess]
    values = ", ".join(str(pid) for pid in sorted(pids))
    raise VramEnvironmentError(
        f"concurrent GPU compute workload contaminated calibration (PIDs {values}); stop it"
    )


def validate_gpu_contexts(
    snapshot: GpuSnapshot,
    baseline: GpuContextBaseline,
    managed: GpuProcessIdentity | None,
) -> set[tuple[int, float | None]]:
    """Validate one sample and return admitted baseline-executable replacement instances."""
    if snapshot.is_wddm != baseline.is_wddm:
        raise VramEnvironmentError("GPU driver model changed during calibration")
    current = _visible_contexts(snapshot, managed)
    if current and not baseline.is_wddm:
        pids = ", ".join(str(item.pid) for item in current)
        raise VramEnvironmentError(
            f"concurrent GPU compute workload contaminated calibration (PIDs {pids}); stop it"
        )
    _reject_excess(current, baseline)
    original = {item.instance for item in baseline.contexts}
    return {item.instance for item in current if item.instance not in original}


def count_context_replacements(
    snapshots: list[GpuSnapshot],
    baseline: GpuContextBaseline,
    managed: GpuProcessIdentity | None,
) -> int:
    """Validate every trial sample and count unique admitted process replacements."""
    replacements: set[tuple[int, float | None]] = set()
    for snapshot in snapshots:
        replacements |= validate_gpu_contexts(snapshot, baseline, managed)
    return len(replacements)
