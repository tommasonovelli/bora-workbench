"""Define one calibration/v3 trial request, result, and candidate failure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psutil

from qwen_launcher._calibration_gpu_contexts import GpuContextBaseline
from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_v3_types import TrialEvidence, TrialOrder
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher._gpu_process_identity import GpuProcessIdentity
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.process import RunningService
from qwen_launcher.profiles import LaunchPlan


@dataclass(slots=True)
class SpawnRecord:
    """Capture child identity before health readiness can fail."""

    pid: int | None = None
    create_time: float | None = None

    def __call__(self, pid: int) -> None:
        """Record the spawned pid/create-time pair without failing process cleanup."""
        self.pid = pid
        try:
            self.create_time = psutil.Process(pid).create_time()
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            self.create_time = None


def managed_gpu_identity(
    running: RunningService | None, spawned: SpawnRecord
) -> GpuProcessIdentity | None:
    """Return the exact managed process instance even after normal cleanup."""
    if running is not None:
        service = running.state
        return GpuProcessIdentity(service.pid, service.create_time, None)
    if spawned.pid is None:
        return None
    return GpuProcessIdentity(spawned.pid, spawned.create_time, None)


class TrialFailure(RuntimeError):
    """Retain measured evidence when one candidate trial is infeasible."""

    def __init__(self, error: Exception, evidence: TrialEvidence):
        """Keep the original expected failure and every completed evidence stream."""
        super().__init__(str(error))
        self.error = error
        self.evidence = evidence


@dataclass(frozen=True, slots=True)
class TrialSpec:
    """Group one launch plan, isolated root, benchmark demand, and deterministic order."""

    plan: LaunchPlan
    root: Path
    with_benchmark: bool
    evidence_root: Path
    order: TrialOrder
    gpu_context_baseline: GpuContextBaseline | None = None


@dataclass(frozen=True, slots=True)
class TrialMeasurement:
    """Hold one completed trial's benchmark, monitors, and detailed evidence."""

    benchmark: BenchmarkResult | None
    vram: VramSummary | None
    ram: RamSummary
    evidence: TrialEvidence
