"""Bounded class-based feasibility search for one calibration/v6-lite context step (spec 3.3).

The search never maps the full feasible region. It finds one prudent feasible anchor and then reuses
``_calibration_v5_search.screen`` to bisect only the aggressive VRAM side below it, exactly as the
plan requires after a RAM failure at maximum offload.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from qwen_launcher._calibration_outcomes import ClassifiedOutcome, TrialOutcome
from qwen_launcher._calibration_v5_search import ProbeMeasurement, ScreeningPlan, screen
from qwen_launcher._calibration_v6_types import (
    MAX_RETRY_PER_TRIAL,
    PRUDENT_N_CPU_MOE,
    V6SearchError,
)

Probe = Callable[[int], ClassifiedOutcome]


@dataclass(frozen=True, slots=True)
class StepFeasibility:
    """Hold one context step's feasibility boundary, prudent anchor, and probe accounting."""

    is_feasible: bool
    boundary: int | None
    prudent: int | None
    probed: tuple[int, ...]
    is_budget_exhausted: bool


@dataclass(slots=True)
class _StepBudget:
    """Track the shared per-step probe budget and record every probed value."""

    limit: int
    probed: list[int] = field(default_factory=list)
    is_exhausted: bool = False

    def spend(self, value: int) -> bool:
        """Reserve one probe for ``value`` or mark the step budget exhausted."""
        if len(self.probed) >= self.limit:
            self.is_exhausted = True
            return False
        self.probed.append(value)
        return True

    @property
    def remaining(self) -> int:
        """Return the probes still available for the VRAM screening phase."""
        return max(0, self.limit - len(self.probed))


def _probe(probe: Probe, value: int) -> ClassifiedOutcome:
    """Probe one value with a single retry; stop the mode on protocol-invalid evidence."""
    for _ in range(MAX_RETRY_PER_TRIAL + 1):
        outcome = probe(value)
        if outcome.outcome is TrialOutcome.PROTOCOL_INVALID:
            raise V6SearchError(f"n_cpu_moe={value} produced protocol-invalid evidence")
        if outcome.outcome is not TrialOutcome.RETRYABLE:
            return outcome
    raise V6SearchError(f"n_cpu_moe={value} remained retryable after one retry")


def _descend_to_feasible(probe: Probe, state: _StepBudget) -> int | None:
    """Find one feasible anchor below the prudent maximum after a RAM failure (spec 3.3)."""
    low, high = 0, PRUDENT_N_CPU_MOE - 1
    while low <= high:
        mid = (low + high) // 2
        if not state.spend(mid):
            return None
        outcome = _probe(probe, mid)
        if outcome.outcome is TrialOutcome.SUCCESS:
            return mid
        if outcome.resource == "ram":
            high = mid - 1
        else:
            low = mid + 1
    return None


def _find_prudent_anchor(probe: Probe, state: _StepBudget) -> int | None:
    """Probe the prudent maximum; a VRAM failure there makes the whole step infeasible."""
    if not state.spend(PRUDENT_N_CPU_MOE):
        return None
    outcome = _probe(probe, PRUDENT_N_CPU_MOE)
    if outcome.outcome is TrialOutcome.SUCCESS:
        return PRUDENT_N_CPU_MOE
    if outcome.resource == "vram":
        return None
    return _descend_to_feasible(probe, state)


def _bisect_vram_side(probe: Probe, prudent: int, state: _StepBudget) -> tuple[int, bool]:
    """Bisect the VRAM side below one feasible anchor by reusing v5 screening (spec 3.3)."""

    def screen_probe(value: int) -> ProbeMeasurement:
        """Report only VRAM feasibility; RAM never fails below the feasible anchor."""
        return ProbeMeasurement(_probe(probe, value).outcome is TrialOutcome.SUCCESS, None)

    plan = ScreeningPlan(prudent, None, 0.0, None, state.remaining)
    result = screen(screen_probe, plan)
    state.probed.extend(value for value, _ in result.probed)
    return result.boundary, result.is_budget_exhausted


def search_step(probe: Probe, budget: int) -> StepFeasibility:
    """Search one context step: prudent probe, optional RAM descent, then VRAM bisection."""
    state = _StepBudget(budget)
    prudent = _find_prudent_anchor(probe, state)
    if prudent is None:
        return StepFeasibility(False, None, None, tuple(state.probed), state.is_exhausted)
    boundary, screen_exhausted = _bisect_vram_side(probe, prudent, state)
    exhausted = state.is_exhausted or screen_exhausted
    return StepFeasibility(True, boundary, prudent, tuple(state.probed), exhausted)
