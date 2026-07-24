"""Constants and immutable models for the calibration/v6-lite engine (spec 1.2, 3.3-3.6).

calibration/v6-lite is opt-in (``--protocol v6``); calibration/v5 stays the default and keeps its
own constants. These reserves (0.5/2.0/0.125 GiB) apply only to v6 trials and are written into the
record. The engine is authorized by the D-063 human override while the cross-context spike GO stays
pending, so v6 must never be promoted to default without a committed measured verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from qwen_launcher.benchmark_quick import QuickBenchResult

CONTEXT_SCALE_V6 = (131072, 65536, 32768)
CONTEXT_REFINEMENT = (98304, 49152)
DEADBAND_PCT = 3.0
BALANCED_CEILING = 1.10
MIN_CTX_FAST = 16384
TEXT_SEARCH_BUDGET = 24
VSTUDIO_SEARCH_BUDGET = 16
MAX_RETRY_PER_TRIAL = 1
PRUDENT_N_CPU_MOE = 41
VRAM_RESERVE_GIB = 0.5
RAM_RESERVE_GIB = 2.0
RELEASE_TOLERANCE_GIB = 0.125
BASELINE_CTX = 8192
BASELINE_N_CPU_MOE = 48

Preference = Literal["fast", "balanced", "max_context"]
PREFERENCES: tuple[Preference, ...] = ("fast", "balanced", "max_context")
DEFAULT_PREFERENCE: Preference = "balanced"


@dataclass(frozen=True, slots=True)
class V6Sample:
    """Hold one measured feasible configuration and its quick-bench evidence (spec 1.2)."""

    ctx: int
    n_cpu_moe: int
    speculative: Literal["mtp2", "disabled"]
    quick: QuickBenchResult
    ram_needed_gib: float
    vram_needed_gib: float | None
    ram_min_available_gib: float
    vram_min_free_gib: float | None

    @property
    def e2e_ms(self) -> float:
        """Return the median short end-to-end latency used by fast and balanced selection."""
        return self.quick.short_e2e_median_ms

    @property
    def prefill_tps(self) -> float:
        """Return the ~8K prefill throughput used as the deadband prefill tie-break."""
        return self.quick.prefill_8k_tps

    @property
    def decode_tps(self) -> float:
        """Return the median short decode throughput used for the v5-style ordering."""
        return self.quick.decode_tps_median


@dataclass(frozen=True, slots=True)
class StepResult:
    """Hold one context step's feasibility and the samples measured at that context."""

    ctx: int
    is_feasible: bool
    samples: tuple[V6Sample, ...]


@dataclass(frozen=True, slots=True)
class GateResult:
    """Hold final-gate pass/fail evidence for one selected envelope (spec 3.5)."""

    smoke: bool
    multi_turn: bool
    vision: bool | None

    @property
    def passed(self) -> bool:
        """Return whether every required gate stage passed for this envelope."""
        return self.smoke and self.multi_turn and (self.vision is not False)


@dataclass(frozen=True, slots=True)
class EnvelopeResult:
    """Hold one selected preference envelope, its measured needs, and its gate outcome."""

    preference: Preference
    sample: V6Sample
    gate: GateResult


@dataclass(frozen=True, slots=True)
class SelectionInput:
    """Retain the per-round medians and thresholds that reconstruct one confirmation."""

    preference: Preference
    round_medians: tuple[tuple[float, float], ...]
    deadband_pct: float


class V6SearchError(RuntimeError):
    """Report exhausted search budget or protocol-invalid evidence for one v6 mode."""
