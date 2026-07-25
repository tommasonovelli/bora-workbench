"""Constants and immutable models of the calibration engine (spec 1.2, 3.3-3.6).

Every constant here is universal, not machine-specific: its effect always passes through the local
measurements of one run. The reserves (0.5/2.0/0.125 GiB) are written into each record so a record
can be re-evaluated later against exactly the margins it was measured with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bora_workbench.benchmark_quick import QuickBenchResult

CALIBRATION_PROTOCOL = "calibration"
CONTEXT_SCALE = (131072, 98304, 65536, 49152, 32768, 16384, 8192)
DEADBAND_PCT = 3.0
BALANCED_CEILING = 1.10
MIN_CTX_FAST = 16384
# An infeasible step costs a single prudent probe, so the full scale only widens the budget by the
# number of added steps; a feasible step still pays for its own VRAM bisection.
TEXT_SEARCH_BUDGET = 28
VSTUDIO_SEARCH_BUDGET = 20
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
class Sample:
    """Hold one measured feasible configuration and its quick-bench evidence (spec 1.2)."""

    ctx: int
    n_cpu_moe: int | None
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
        """Return the median short decode throughput used for throughput ordering."""
        return self.quick.decode_tps_median


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
    sample: Sample
    gate: GateResult


class SearchError(RuntimeError):
    """Report exhausted search budget or protocol-invalid evidence for one mode."""


class TrialInfeasibleError(SearchError):
    """Report a measured point that turned infeasible after a probe had accepted it.

    The memory boundary can move between a light probe and the heavier quick-bench, so the search
    drops that single point instead of failing the mode; paired confirmation lets it propagate,
    because dropping one finalist would silently change the comparison (spec 3.3-3.4).
    """
