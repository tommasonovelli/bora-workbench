"""Shared vocabulary of the calibration engine: constants, models, failures and outcomes.

Every constant here is universal, not machine-specific: its effect always passes through the local
measurements of one run. The reserves (0.5/2.0/0.125 GiB) are written into each record so a record
can be re-evaluated later against exactly the margins it was measured with (spec 1.2, 3.3-3.6).

The trial outcome taxonomy of D-059 lives here too, because its classes are part of the same
vocabulary: the search, the confirmation and the trial provider all speak in them, and the rule
that decides which failure means "infeasible" belongs next to the failure classes it reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

import httpx

from bora_workbench._calibration_memory import (
    RamError,
    RamReserveError,
    VramEnvironmentError,
    VramReleaseError,
    VramReserveError,
    oom_resource,
    read_logs,
)
from bora_workbench.benchmark import BenchmarkError, BenchmarkRetryableError
from bora_workbench.benchmark_quick import QuickBenchResult
from bora_workbench.process import ServerStartupError

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

Preference = Literal["fast", "balanced", "max_context"]
PREFERENCES: tuple[Preference, ...] = ("fast", "balanced", "max_context")
DEFAULT_PREFERENCE: Preference = "balanced"


def launcher_version() -> str:
    """Read installed package metadata with the source-checkout development fallback.

    The value is the provenance of every generated record, so it is read here rather than hardcoded
    at the writer (spec 3.6).
    """
    try:
        return version("bora-workbench")
    except PackageNotFoundError:
        return "0.2.0"


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


class CalibrationError(RuntimeError):
    """Report invalid calibration input or a failed preflight."""


class CalibrationRunError(CalibrationError):
    """Report an operational calibration failure after valid input was accepted."""


class SearchError(RuntimeError):
    """Report exhausted search budget or protocol-invalid evidence for one mode."""


class TrialInfeasibleError(SearchError):
    """Report a measured point that turned infeasible after a probe had accepted it.

    The memory boundary can move between a light probe and the heavier quick-bench, so the search
    drops that single point instead of failing the mode; paired confirmation lets it propagate,
    because dropping one finalist would silently change the comparison (spec 3.3-3.4).
    """


class UnclassifiableTrialError(ValueError):
    """Report an error that invalidates the run rather than one candidate."""


class TrialOutcome(Enum):
    """Name the four trial outcome classes from D-059."""

    SUCCESS = "success"
    MEMORY_INFEASIBLE = "memory_infeasible"
    RETRYABLE = "retryable"
    PROTOCOL_INVALID = "protocol_invalid"


@dataclass(frozen=True, slots=True)
class ClassifiedOutcome:
    """Attach the constrained memory resource only to infeasible outcomes."""

    outcome: TrialOutcome
    resource: Literal["ram", "vram"] | None = None


def _startup_outcome(error: ServerStartupError) -> ClassifiedOutcome:
    """Classify a server that died before READY using the engine's own log diagnosis.

    Only explicit out-of-memory evidence proves an infeasible candidate. Any other early exit is
    treated as retryable, so a transient start never fabricates a memory boundary (spec 5.6).
    """
    paths = () if error.log_path is None else (error.log_path,)
    resource = oom_resource(read_logs(paths))
    if resource is None:
        return ClassifiedOutcome(TrialOutcome.RETRYABLE)
    return ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, resource)


def classify(error: BaseException | None) -> ClassifiedOutcome:
    """Map class-defined failures to D-059 outcomes and reject run-invalidating evidence."""
    if error is None:
        return ClassifiedOutcome(TrialOutcome.SUCCESS)
    if isinstance(error, (VramEnvironmentError, RamError)):
        raise UnclassifiableTrialError(f"run-invalidating error: {error}") from error
    if isinstance(error, ServerStartupError):
        return _startup_outcome(error)
    if isinstance(error, VramReserveError):
        return ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram")
    if isinstance(error, RamReserveError):
        return ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "ram")
    retryable = (VramReleaseError, BenchmarkRetryableError, httpx.TransportError)
    if isinstance(error, retryable):
        return ClassifiedOutcome(TrialOutcome.RETRYABLE)
    if isinstance(error, BenchmarkError):
        return ClassifiedOutcome(TrialOutcome.PROTOCOL_INVALID)
    raise UnclassifiableTrialError(
        f"unsupported trial error: {type(error).__name__}: {error}"
    ) from error
