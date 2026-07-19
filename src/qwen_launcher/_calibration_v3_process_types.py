"""Define one calibration/v3 trial request, result, and candidate failure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_v3_types import TrialEvidence, TrialOrder
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.profiles import LaunchPlan


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


@dataclass(frozen=True, slots=True)
class TrialMeasurement:
    """Hold one completed trial's benchmark, monitors, and detailed evidence."""

    benchmark: BenchmarkResult | None
    vram: VramSummary | None
    ram: RamSummary
    evidence: TrialEvidence
