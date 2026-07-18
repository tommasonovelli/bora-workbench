"""Pure calibration/v2 screening search and noise-robust finalist selection.

The search finds the ``n_cpu_moe`` feasibility boundary by bisection because measured VRAM grows
monotonically as the axis descends (design document section 2.3). Every probe verifies that model
with a measure: a measured non-monotonic outcome degrades honestly to a linear scan from the most
prudent value, and a shared seed may only reorder the probes of the same complete search (D-038).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from qwen_launcher._calibration_v2_types import (
    RELEASE_TOLERANCE_GIB,
    SELECTION_DOMINANCE,
    SELECTION_FREE_VRAM,
    SELECTION_PRUDENT,
    SELECTION_SINGLE,
    SelectionCandidate,
)


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
    seed: int | None
    probe_budget: int


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    """Hold the measured boundary and the exact probe sequence that produced it."""

    boundary: int
    probed: tuple[tuple[int, ProbeMeasurement], ...]
    did_degrade: bool
    is_budget_exhausted: bool


@dataclass(slots=True)
class _Screening:
    """Track probe outcomes, ordering, and the remaining budget for one screening."""

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
        """Detect an aggressive probe measuring less VRAM than a more prudent one.

        Descending ``n_cpu_moe`` moves experts onto the GPU, so peak VRAM must not measurably
        shrink (design section 2.3). The comparison uses the declared drift tolerance instead of
        an invented equality threshold (D-039).
        """
        peaks = [
            (value, measured.peak_used_gib)
            for value, measured in self.outcomes.items()
            if measured.peak_used_gib is not None
        ]
        return any(
            aggressive < prudent and aggressive_peak + RELEASE_TOLERANCE_GIB < prudent_peak
            for aggressive, aggressive_peak in peaks
            for prudent, prudent_peak in peaks
            if aggressive < prudent
        )


def _bisect(state: _Screening) -> int | None:
    """Bisect to the least feasible value, or return ``None`` on a measured violation."""
    low, high = 0, state.plan.domain_maximum
    is_first = True
    while low < high:
        split = (low + high) // 2
        seed = state.plan.seed
        if is_first and seed is not None and low <= seed < high:
            split = seed
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
    value = boundary - 1
    while value >= 0:
        measured = state.run(value)
        if measured is None or not measured.is_feasible:
            break
        boundary = value
        value -= 1
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


def select_candidate_index(candidates: tuple[SelectionCandidate, ...]) -> tuple[int, str]:
    """Choose between finalists with the noise-robust rule of design section 3, step 4.

    A candidate dominates only when its median exceeds the other's maximum measure; otherwise the
    two are equivalent and the rule prefers the larger observed VRAM margin, then prudence.
    """
    if len(candidates) == 1:
        return 0, SELECTION_SINGLE
    if len(candidates) != 2:
        raise ValueError("calibration/v2 confirms at most two finalists per mode")
    first, second = candidates
    if first.median_tok_s > second.maximum_tok_s:
        return 0, SELECTION_DOMINANCE
    if second.median_tok_s > first.maximum_tok_s:
        return 1, SELECTION_DOMINANCE
    first_free = first.minimum_free_vram_gib or 0.0
    second_free = second.minimum_free_vram_gib or 0.0
    if first_free != second_free:
        return (0 if first_free > second_free else 1), SELECTION_FREE_VRAM
    first_prudence = first.n_cpu_moe or 0
    second_prudence = second.n_cpu_moe or 0
    return (0 if first_prudence >= second_prudence else 1), SELECTION_PRUDENT
