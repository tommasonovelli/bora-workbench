"""Define calibration/v3 constants and immutable per-mode evidence.

The universal values have declared provenance in D-039/D-041-D-045 and remain subject to the
Calibration Gate. Their effect always passes through local measurements; none is machine-specific.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.profiles import Mode

CALIBRATION_V3_PROTOCOL = "calibration/v3"
VRAM_RESERVE_GIB = 0.5
RAM_RESERVE_GIB = 2.0
RELEASE_TOLERANCE_GIB = 0.125
CONFIRM_ROUNDS = 2
MODE_PROBE_CAP = 12
CONTEXT_SCALE = (131072, 65536, 32768, 16384, 8192)
EXPERT_CONTEXT_TARGETS = (131072, 98304, 65536, 32768, 16384, 8192)
CPU_BASELINE_CTX = 8192
OBJECTIVE = "maximum-context-then-paired-throughput-then-memory-margin-then-prudence"

SELECTION_DOMINANCE = "dominance-unanimous-rounds"
SELECTION_FREE_VRAM = "equivalent-prefer-minimum-free-vram"
SELECTION_PRUDENT = "equivalent-prefer-prudent"
SELECTION_DRIFT = "equivalent-after-baseline-drift"
SELECTION_SINGLE = "single-finalist"
SELECTION_CPU_BASELINE = "cpu-baseline-confirmation"


@dataclass(frozen=True, slots=True)
class TrialOrder:
    """Identify one trial's phase and deterministic position within that phase."""

    phase: str
    sequence: int
    round_index: int | None = None
    global_position: int | None = None


@dataclass(frozen=True, slots=True)
class TrialEvidence:
    """Retain one fresh process's timing, benchmark, resources, and relative log."""

    order: TrialOrder
    started_at: str
    finished_at: str
    benchmark: BenchmarkResult | None
    vram: VramSummary | None
    ram: RamSummary | None
    log_path: str | None


@dataclass(frozen=True, slots=True)
class ProbeRecord:
    """Record one screening probe with its measured feasibility and reduced evidence."""

    ctx: int
    n_cpu_moe: int
    is_feasible: bool
    reason: str | None
    trial: TrialEvidence


@dataclass(frozen=True, slots=True)
class FinalistEvidence:
    """Record one finalist's paired-round outcome and conservative resource aggregates."""

    ctx: int
    n_cpu_moe: int | None
    outcome: str
    discard_reason: str | None
    sessions: tuple[TrialEvidence, ...]
    vram: VramSummary | None
    ram: RamSummary | None


@dataclass(frozen=True, slots=True)
class ModeCalibration:
    """Hold one mode's complete search, paired confirmation, and reconstructed selection."""

    mode: Mode
    ctx: int
    target_ctx: int | None
    probes: tuple[ProbeRecord, ...]
    did_degrade: bool
    finalists: tuple[FinalistEvidence, ...]
    selected: FinalistEvidence
    selection_rule: str
    round_winners: tuple[int | None, ...]
    baseline_drift_gib: float | None


@dataclass(frozen=True, slots=True)
class V3Outcome:
    """Identify calibrations, record lifecycle paths, and retained evidence for one run."""

    calibrations: tuple[ModeCalibration, ...]
    candidate_paths: tuple[Path, ...]
    active_paths: tuple[Path, ...]
    evidence_path: Path


@dataclass(frozen=True, slots=True)
class SelectionCandidate:
    """Project one valid finalist onto the fields read by paired selection."""

    round_medians: tuple[float, ...]
    minimum_free_vram_gib: float | None
    n_cpu_moe: int | None


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Describe one completed phase item and a best-effort learned duration estimate."""

    mode_id: str
    phase: str
    completed: int
    total: int
    estimated_remaining_seconds: float | None


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(frozen=True, slots=True)
class V3RunOptions:
    """Group optional expert controls without burdening the zero-input default path."""

    target_ctx: int | None = None
    is_activate: bool = True
    progress: ProgressCallback | None = None
