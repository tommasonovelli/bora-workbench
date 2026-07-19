"""Implement pure calibration/v3 screening and paired-round finalist selection.

Screening preserves measured bisection and may use safe interpolation only to choose the next probe;
it never excludes a value. Peak monotonicity is checked only on completed feasible loads because an
OOM peak is truncated evidence (D-045).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from qwen_launcher._calibration_v3_selection import select_candidate_index
from qwen_launcher._calibration_v3_types import RELEASE_TOLERANCE_GIB

__all__ = [
    "ProbeMeasurement",
    "ScreeningPlan",
    "ScreeningResult",
    "screen",
    "select_candidate_index",
]


@dataclass(frozen=True, slots=True)
class ProbeMeasurement:
    """Hold the two measured facts screening needs from one probe."""

    is_feasible: bool
    peak_used_gib: float | None


@dataclass(frozen=True, slots=True)
class ScreeningPlan:
    """Describe one fixed-context screening over the metadata-predicted domain."""

    domain_maximum: int
    maximum_peak_gib: float | None
    peak_limit_gib: float
    seed: int | None
    probe_budget: int


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    """Hold the measured boundary and exact probe sequence that produced it."""

    boundary: int
    probed: tuple[tuple[int, ProbeMeasurement], ...]
    did_degrade: bool
    is_budget_exhausted: bool


@dataclass(slots=True)
class _Screening:
    """Track probe outcomes, ordering, and remaining budget for one screening."""

    probe: Callable[[int], ProbeMeasurement]
    plan: ScreeningPlan
    outcomes: dict[int, ProbeMeasurement]
    order: list[tuple[int, ProbeMeasurement]] = field(default_factory=list)
    used: int = 0
    is_exhausted: bool = False

    def run(self, value: int) -> ProbeMeasurement | None:
        """Run or reuse one probe, or report budget exhaustion with ``None``."""
        cached = self.outcomes.get(value)
        if cached is not None:
            return cached
        if self.used >= self.plan.probe_budget:
            self.is_exhausted = True
            return None
        self.used += 1
        measured = self.probe(value)
        self.outcomes[value] = measured
        self.order.append((value, measured))
        return measured

    def has_monotonic_violation(self) -> bool:
        """Detect contradictory peaks using only completed feasible probes (D-045)."""
        peaks = _feasible_peaks(self.outcomes)
        return any(
            aggressive < prudent and aggressive_peak + RELEASE_TOLERANCE_GIB < prudent_peak
            for aggressive, aggressive_peak in peaks
            for prudent, prudent_peak in peaks
            if aggressive < prudent
        )


def _feasible_peaks(outcomes: dict[int, ProbeMeasurement]) -> list[tuple[int, float]]:
    """Return sorted complete-load peaks suitable for monotonicity and interpolation."""
    return sorted(
        (value, measured.peak_used_gib)
        for value, measured in outcomes.items()
        if measured.is_feasible and measured.peak_used_gib is not None
    )


def _interpolated_split(state: _Screening, low: int, high: int) -> int | None:
    """Predict a bracket-internal boundary from two feasible peaks without excluding values."""
    peaks = _feasible_peaks(state.outcomes)
    if len(peaks) < 2:
        return None
    left, right = peaks[0], peaks[-1]
    if left[0] == right[0] or left[1] == right[1]:
        return None
    slope = (right[1] - left[1]) / (right[0] - left[0])
    if slope >= 0:
        return None
    intercept = left[1] - slope * left[0]
    predicted = math.ceil((state.plan.peak_limit_gib - intercept) / slope)
    return predicted if low <= predicted < high else None


def _next_split(state: _Screening, bracket: tuple[int, int], is_first: bool) -> int:
    """Choose seed, safe interpolation, or midpoint in deterministic priority order."""
    low, high = bracket
    seed = state.plan.seed
    if is_first and seed is not None and low <= seed < high:
        return seed
    predicted = _interpolated_split(state, low, high)
    return predicted if predicted is not None else (low + high) // 2


def _bisect(state: _Screening) -> int | None:
    """Bisect to the least feasible value, or return ``None`` on a measured violation."""
    low, high = 0, state.plan.domain_maximum
    is_first = True
    while low < high:
        split = _next_split(state, (low, high), is_first)
        is_first = False
        measured = state.run(split)
        if measured is None:
            return high
        if measured.is_feasible:
            high = split
        else:
            low = split + 1
        if state.has_monotonic_violation():
            return None
    return high


def _linear_descent(state: _Screening) -> int:
    """Scan downward from the most prudent value after the monotonic model failed."""
    boundary = state.plan.domain_maximum
    for value in range(boundary - 1, -1, -1):
        measured = state.run(value)
        if measured is None or not measured.is_feasible:
            break
        boundary = value
    return boundary


def screen(probe: Callable[[int], ProbeMeasurement], plan: ScreeningPlan) -> ScreeningResult:
    """Find the feasibility boundary below the already verified most prudent value."""
    initial = {plan.domain_maximum: ProbeMeasurement(True, plan.maximum_peak_gib)}
    state = _Screening(probe, plan, initial)
    if plan.domain_maximum == 0:
        return ScreeningResult(0, (), False, False)
    boundary = _bisect(state)
    did_degrade = boundary is None
    if boundary is None:
        boundary = _linear_descent(state)
    return ScreeningResult(boundary, tuple(state.order), did_degrade, state.is_exhausted)
