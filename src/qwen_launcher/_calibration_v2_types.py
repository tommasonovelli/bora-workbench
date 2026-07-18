"""Define calibration/v2 design constants and immutable per-mode evidence.

Every constant here is a universal design value with declared provenance (D-039): the maintainer's
approved local-first redesign of 17 July 2026, to be validated or corrected at the Calibration
Gate. None of them is a per-machine threshold; their effect always passes through local measures.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.profiles import Mode

CALIBRATION_V2_PROTOCOL = "calibration/v2"
VRAM_RESERVE_GIB = 0.5
RELEASE_TOLERANCE_GIB = 0.125
STABLE_START_RUNS = 2
MODE_PROBE_CAP = 12
CONTEXT_SCALE = (131072, 65536, 32768, 16384, 8192)
# The CPU baseline context is the envelope verified by Spike 0 (specification section 5.5); the CPU
# backend has no verified tuning axis, so v2 only confirms this baseline (design section 3, step 8).
CPU_BASELINE_CTX = 8192

SELECTION_DOMINANCE = "dominance-median-over-maximum"
SELECTION_FREE_VRAM = "equivalent-prefer-minimum-free-vram"
SELECTION_PRUDENT = "equivalent-prefer-prudent"
SELECTION_SINGLE = "single-finalist"
SELECTION_CPU_BASELINE = "cpu-baseline-confirmation"


@dataclass(frozen=True, slots=True)
class ProbeRecord:
    """Record one screening probe with its measured feasibility outcome."""

    ctx: int
    n_cpu_moe: int
    is_feasible: bool
    reason: str | None
    peak_used_gib: float | None


@dataclass(frozen=True, slots=True)
class FinalistEvidence:
    """Record one finalist's confirmation outcome with all measured evidence."""

    ctx: int
    n_cpu_moe: int | None
    outcome: str
    discard_reason: str | None
    benchmark: BenchmarkResult | None
    vram: VramSummary | None
    ram: RamSummary | None


@dataclass(frozen=True, slots=True)
class ModeCalibration:
    """Hold one mode's complete search evidence and its reconstructed selection."""

    mode: Mode
    ctx: int
    probes: tuple[ProbeRecord, ...]
    did_degrade: bool
    finalists: tuple[FinalistEvidence, ...]
    selected: FinalistEvidence
    selection_rule: str


@dataclass(frozen=True, slots=True)
class V2Outcome:
    """Identify every mode calibration and the local record path it produced."""

    calibrations: tuple[ModeCalibration, ...]
    record_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class SelectionCandidate:
    """Project one valid finalist onto the exact fields the selection rule reads."""

    median_tok_s: float
    maximum_tok_s: float
    minimum_free_vram_gib: float | None
    n_cpu_moe: int | None
