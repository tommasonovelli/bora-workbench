"""Offline tests for calibration/v3 screening, interpolation, and paired selection."""

from __future__ import annotations

from qwen_launcher._calibration_v3_search import (
    ProbeMeasurement,
    ScreeningPlan,
    screen,
    select_candidate_index,
)
from qwen_launcher._calibration_v3_types import (
    SELECTION_DOMINANCE,
    SELECTION_DRIFT,
    SELECTION_FREE_VRAM,
    SELECTION_PRUDENT,
    SELECTION_SINGLE,
    SelectionCandidate,
)


def monotonic_probe(minimum_feasible: int, order: list[int]):
    """Build a probe whose feasibility and peaks follow the physical monotone model."""

    def probe(value: int) -> ProbeMeasurement:
        """Report feasibility above the boundary with use growing as the axis descends."""
        order.append(value)
        return ProbeMeasurement(value >= minimum_feasible, 7.5 - 0.05 * value)

    return probe


def plan(seed: int | None = None, budget: int = 12) -> ScreeningPlan:
    """Build one 41-block screening plan with an explicit aggregate peak limit."""
    return ScreeningPlan(41, 7.5 - 0.05 * 41, 5.6, seed, budget)


def test_bisection_finds_the_exact_measured_boundary() -> None:
    """Converge on the least feasible value with far fewer probes than a linear scan."""
    order: list[int] = []
    result = screen(monotonic_probe(38, order), plan())

    assert result.boundary == 38
    assert not result.did_degrade
    assert not result.is_budget_exhausted
    assert len(order) <= 7


def test_fully_feasible_and_zero_domains_reach_zero() -> None:
    """Reach the aggressive endpoint, including a degenerate single-value domain."""
    order: list[int] = []
    result = screen(monotonic_probe(0, order), plan())
    zero = screen(monotonic_probe(0, []), ScreeningPlan(0, 4.0, 7.0, None, 12))

    assert result.boundary == 0
    assert zero.boundary == 0 and zero.probed == ()


def test_seed_and_interpolation_only_reorder_the_complete_search() -> None:
    """Use a feasible shared seed and fitted boundary without changing the measured result."""
    order: list[int] = []
    result = screen(monotonic_probe(38, order), plan(seed=39))

    assert order[0] == 39
    assert result.boundary == 38
    assert len(order) < 7


def test_interpolation_falls_back_when_prediction_cannot_shrink_the_bracket() -> None:
    """Use a midpoint when feasible peaks cannot predict an internal next probe."""
    order: list[int] = []
    flat = ScreeningPlan(41, 5.0, 7.0, 41, 12)
    result = screen(monotonic_probe(38, order), flat)

    assert order[0] == 20
    assert result.boundary == 38


def test_budget_exhaustion_returns_a_verified_feasible_value() -> None:
    """Stop honestly at a feasible value when the screening budget runs out."""
    order: list[int] = []
    result = screen(monotonic_probe(38, order), plan(budget=2))

    assert result.is_budget_exhausted
    assert result.boundary >= 38
    assert len(order) == 2


def test_non_monotonic_feasible_peaks_degrade_to_linear_scan() -> None:
    """Fall back only when completed feasible loads contradict measured monotonicity."""
    feasible = {41, 40, 39}

    def probe(value: int) -> ProbeMeasurement:
        """Make feasible aggressive loads report a contradictory lower peak."""
        peak = 3.0 if value in feasible else 7.8
        return ProbeMeasurement(value in feasible, peak)

    result = screen(probe, ScreeningPlan(41, 4.0, 7.0, None, 12))

    assert result.did_degrade
    assert result.boundary == 39


def test_truncated_oom_peak_does_not_trigger_spurious_degradation() -> None:
    """Ignore a failed load's truncated peak when validating the physical peak model."""

    def probe(value: int) -> ProbeMeasurement:
        """Return low truncated peaks for failures and monotone peaks for complete loads."""
        is_feasible = value >= 38
        peak = 2.0 if not is_feasible else 7.5 - 0.05 * value
        return ProbeMeasurement(is_feasible, peak)

    result = screen(probe, plan())

    assert result.boundary == 38
    assert not result.did_degrade


def candidate(rounds: tuple[float, float], free: float, moe: int) -> SelectionCandidate:
    """Build one paired selection candidate."""
    return SelectionCandidate(rounds, free, moe)


def test_unanimous_round_wins_use_session_medians() -> None:
    """Select throughput only when the same finalist wins both paired rounds."""
    aggressive = candidate((62.0, 63.0), 0.6, 38)
    prudent = candidate((61.0, 61.5), 0.8, 39)

    assert select_candidate_index((aggressive, prudent)) == (
        0,
        SELECTION_DOMINANCE,
        (0, 0),
    )


def test_discordant_or_tied_rounds_prefer_margin_then_prudence() -> None:
    """Treat discordance and exact ties as equivalence without a fixed noise threshold."""
    aggressive = candidate((62.0, 60.0), 0.6, 38)
    prudent = candidate((61.0, 61.0), 0.8, 39)
    tied_margin = candidate((61.0, 60.0), 0.6, 39)

    assert select_candidate_index((aggressive, prudent))[1] == SELECTION_FREE_VRAM
    assert select_candidate_index((aggressive, tied_margin))[1] == SELECTION_PRUDENT


def test_baseline_drift_suppresses_dominance_without_discarding() -> None:
    """Degrade an otherwise unanimous comparison to the explicit drift label."""
    aggressive = candidate((62.0, 63.0), 0.6, 38)
    prudent = candidate((61.0, 61.5), 0.8, 39)

    selected = select_candidate_index((aggressive, prudent), has_baseline_drift=True)

    assert selected == (1, SELECTION_DRIFT, (0, 0))


def test_single_finalist_and_real_run_shape_are_deterministic() -> None:
    """Handle one finalist and select 37 when it wins both reconstructed real-run rounds."""
    single = candidate((50.0, 51.0), 1.0, 41)
    candidate_37 = candidate((22.85, 23.18), 0.649, 37)
    candidate_38 = candidate((20.52, 20.52), 0.930, 38)

    assert select_candidate_index((single,)) == (0, SELECTION_SINGLE, (None, None))
    assert select_candidate_index((candidate_37, candidate_38))[0] == 0
