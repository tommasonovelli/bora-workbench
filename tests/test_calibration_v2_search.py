"""Offline tests for calibration/v2 screening, degradation, budget, and selection."""

from __future__ import annotations

from qwen_launcher._calibration_v2_search import (
    ProbeMeasurement,
    ScreeningPlan,
    screen,
    select_candidate_index,
)
from qwen_launcher._calibration_v2_types import (
    SELECTION_DOMINANCE,
    SELECTION_FREE_VRAM,
    SELECTION_PRUDENT,
    SELECTION_SINGLE,
    SelectionCandidate,
)


def monotonic_probe(minimum_feasible: int, order: list[int]):
    """Build a probe whose feasibility and VRAM peaks follow the physical monotone model."""

    def probe(value: int) -> ProbeMeasurement:
        """Report feasibility above the boundary with peaks growing as the axis descends."""
        order.append(value)
        return ProbeMeasurement(value >= minimum_feasible, 7.5 - 0.05 * value)

    return probe


def test_bisection_finds_the_exact_measured_boundary() -> None:
    """Converge on the least feasible value with far fewer probes than the domain size."""
    order: list[int] = []
    plan = ScreeningPlan(41, 7.5 - 0.05 * 41, None, 12)

    result = screen(monotonic_probe(38, order), plan)

    assert result.boundary == 38
    assert not result.did_degrade
    assert not result.is_budget_exhausted
    assert len(order) <= 7
    assert order == [value for value, _measured in result.probed]


def test_fully_feasible_domain_reaches_zero() -> None:
    """Descend to the most aggressive value when every probe is feasible."""
    order: list[int] = []
    result = screen(monotonic_probe(0, order), ScreeningPlan(41, 5.45, None, 12))

    assert result.boundary == 0
    assert len(order) <= 7


def test_zero_domain_needs_no_probes() -> None:
    """Treat a degenerate single-value domain as already screened."""
    result = screen(monotonic_probe(0, []), ScreeningPlan(0, 4.0, None, 12))

    assert result.boundary == 0
    assert result.probed == ()


def test_seed_only_reorders_the_first_probe() -> None:
    """Probe the shared seed first without changing the measured boundary (D-035)."""
    seeded_order: list[int] = []
    plan = ScreeningPlan(41, 7.5 - 0.05 * 41, 38, 12)

    result = screen(monotonic_probe(38, seeded_order), plan)

    assert seeded_order[0] == 38
    assert result.boundary == 38


def test_seed_outside_the_open_interval_is_ignored() -> None:
    """Never let an alias of the maximum steer or narrow the search."""
    order: list[int] = []
    plan = ScreeningPlan(41, 7.5 - 0.05 * 41, 41, 12)

    result = screen(monotonic_probe(38, order), plan)

    assert order[0] == 20
    assert result.boundary == 38


def test_budget_exhaustion_returns_the_verified_feasible_value() -> None:
    """Stop honestly at the smallest value verified feasible when probes run out."""
    order: list[int] = []
    result = screen(monotonic_probe(38, order), ScreeningPlan(41, 5.45, None, 2))

    assert result.is_budget_exhausted
    assert result.boundary == 41
    assert len(order) == 2


def test_measured_non_monotonic_peak_degrades_to_linear_scan() -> None:
    """Fall back to a linear scan from the most prudent value on contradictory measures."""
    order: list[int] = []
    feasible = {41, 40, 39}

    def probe(value: int) -> ProbeMeasurement:
        """Measure a mid-domain peak far below the prudent maximum, breaking the model."""
        order.append(value)
        return ProbeMeasurement(value in feasible, 3.0)

    result = screen(probe, ScreeningPlan(41, 4.0, None, 12))

    assert result.did_degrade
    assert result.boundary == 39
    assert order == [20, 40, 39, 38]


def candidate(median: float, maximum: float, free: float, n_cpu_moe: int) -> SelectionCandidate:
    """Build one selection candidate with explicit rule-relevant fields."""
    return SelectionCandidate(median, maximum, free, n_cpu_moe)


def test_dominance_requires_median_above_the_other_maximum() -> None:
    """Let a candidate win only when noise cannot explain its advantage."""
    aggressive = candidate(62.0, 62.5, 0.6, 38)
    prudent = candidate(61.0, 61.5, 0.8, 39)

    assert select_candidate_index((aggressive, prudent)) == (0, SELECTION_DOMINANCE)
    assert select_candidate_index((prudent, aggressive)) == (1, SELECTION_DOMINANCE)


def test_equivalent_candidates_prefer_memory_margin_then_prudence() -> None:
    """Fall back safely on a noisy host instead of trusting overlapping measures."""
    aggressive = candidate(62.0, 64.0, 0.6, 38)
    prudent = candidate(61.5, 63.0, 0.8, 39)
    same_margin = candidate(61.5, 63.0, 0.6, 39)

    assert select_candidate_index((aggressive, prudent)) == (1, SELECTION_FREE_VRAM)
    assert select_candidate_index((aggressive, same_margin)) == (1, SELECTION_PRUDENT)


def test_single_finalist_is_selected_as_such() -> None:
    """Report the boundary-equals-maximum case with its own explicit rule."""
    assert select_candidate_index((candidate(50.0, 51.0, 1.0, 41),)) == (0, SELECTION_SINGLE)
