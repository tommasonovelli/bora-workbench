"""Offline tests for calibration group orchestration over fake trial providers."""

from __future__ import annotations

import pytest

from bora_workbench._calibration_runner import (
    MAX_GATE_TRIALS,
    MAX_PAIRING_TRIALS,
    GateTarget,
    _confirm,
    run_group,
)
from bora_workbench._calibration_search import GroupPlan, SearchProvider
from bora_workbench._calibration_trial_control import TrialProgress
from bora_workbench._calibration_types import (
    ClassifiedOutcome,
    GateResult,
    SearchError,
    TrialInfeasibleError,
    TrialOutcome,
)
from bora_workbench.profiles import load_catalog
from tests.sample_fixtures import sample

_VRAM = ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram")
_SUCCESS = ClassifiedOutcome(TrialOutcome.SUCCESS)
_E2E = {131072: 200.0, 65536: 100.0, 32768: 105.0}
_BOUNDARY = {131072: 37, 65536: 30, 32768: 20}
_CONTEXTS = (131072, 65536, 32768)


def _mode(mode_id: str):
    """Return one packaged mode for a gate target."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    return mode


def _provider() -> SearchProvider:
    """Build a shared provider whose feasibility and latency depend only on the context."""

    def probe_at(ctx: int, n_cpu_moe: int) -> ClassifiedOutcome:
        """Classify points against the synthetic per-context boundary."""
        return _SUCCESS if n_cpu_moe >= _BOUNDARY[ctx] else _VRAM

    def sample_at(ctx: int, n_cpu_moe: int):
        """Measure one synthetic sample with context-dependent latency."""
        return sample(ctx, n_cpu_moe, _E2E[ctx])

    return SearchProvider(probe_at, sample_at)


def _pass_gate(ctx: int, n_cpu_moe: int) -> GateResult:
    """Pass every gate stage."""
    return GateResult(True, True, None)


def test_shared_search_yields_identical_hardware_for_coding_and_studio() -> None:
    """Run one search and give coding and studio the same selected cell with distinct gates."""
    targets = (GateTarget(_mode("coding"), _pass_gate), GateTarget(_mode("studio"), _pass_gate))
    coding, studio = run_group(_provider(), targets, GroupPlan(_CONTEXTS, 24))
    assert coding.mode.id == "coding"
    assert studio.mode.id == "studio"
    left = coding.envelope.sample
    right = studio.envelope.sample
    assert (left.ctx, left.n_cpu_moe) == (right.ctx, right.n_cpu_moe)
    assert coding.envelope.preference == "balanced"
    assert coding.envelope.sample.ctx == 65536


def test_group_persists_only_the_requested_preference() -> None:
    """Return one balanced cell instead of measuring and gating unused preferences."""
    gated: list[tuple[int, int | None]] = []

    def gate_at(ctx: int, n_cpu_moe: int | None) -> GateResult:
        """Record each final-gate process started for the selected cell."""
        gated.append((ctx, n_cpu_moe))
        return GateResult(True, True, None)

    (result,) = run_group(
        _provider(), (GateTarget(_mode("coding"), gate_at),), GroupPlan(_CONTEXTS, 24)
    )

    assert result.envelope.preference == "balanced"
    assert result.envelope.sample.ctx == 65536
    assert len(gated) == 1


def test_gate_failure_retries_next_candidate_then_errors() -> None:
    """Use the next candidate once when a gate fails, then fail the mode when both fail."""
    failing_context = 65536

    def gate_only_prudent(ctx: int, n_cpu_moe: int) -> GateResult:
        """Reject only the prudent finalist at the configured context."""
        passed = not (ctx == failing_context and n_cpu_moe == 41)
        return GateResult(passed, passed, None)

    (result,) = run_group(
        _provider(),
        (GateTarget(_mode("coding"), gate_only_prudent),),
        GroupPlan(_CONTEXTS, 24, preference="fast"),
    )
    assert result.envelope.sample.n_cpu_moe != 41

    def gate_never(ctx: int, n_cpu_moe: int) -> GateResult:
        """Reject every finalist at the final gate."""
        del ctx, n_cpu_moe
        return GateResult(False, False, None)

    with pytest.raises(SearchError, match="final gate"):
        run_group(
            _provider(),
            (GateTarget(_mode("coding"), gate_never),),
            GroupPlan(_CONTEXTS, 24, preference="fast"),
        )


def _moving_boundary_provider(lost: tuple[int, int]) -> SearchProvider:
    """Build a provider where one point is measurable once and then stops fitting the reserves.

    The first measurement is the search, which therefore accepts the point and lets selection pick
    it; every later measurement is confirmation, where the boundary has moved under it.
    """
    base = _provider()
    seen = False

    def sample_at(ctx: int, n_cpu_moe: int):
        """Allow the selected point once before making it infeasible."""
        nonlocal seen
        if (ctx, n_cpu_moe) == lost:
            if seen:
                raise TrialInfeasibleError(f"{lost} is no longer feasible: VRAM reserve violated")
            seen = True
        return base.sample_at(ctx, n_cpu_moe)

    return SearchProvider(base.probe_at, sample_at)


def test_a_finalist_that_stops_fitting_confirms_the_other_one() -> None:
    """Never fail a mode because the memory boundary moved under one ABBA finalist (D-067).

    The search accepted the point, so it appears among the samples; confirmation then re-measures
    it and finds it violates the reserve. It cannot become a launch envelope, but the run must
    continue with the finalist that still fits.
    """
    provider = _provider()
    (reference,) = run_group(
        provider,
        (GateTarget(_mode("coding"), _pass_gate),),
        GroupPlan(_CONTEXTS, 24, preference="fast"),
    )
    confirmed = reference.envelope.sample
    assert confirmed.n_cpu_moe is not None

    moving = _moving_boundary_provider((confirmed.ctx, confirmed.n_cpu_moe))
    (result,) = run_group(
        moving,
        (GateTarget(_mode("coding"), _pass_gate),),
        GroupPlan(_CONTEXTS, 24, preference="fast"),
    )

    survivor = result.envelope.sample
    assert (survivor.ctx, survivor.n_cpu_moe) != (confirmed.ctx, confirmed.n_cpu_moe)
    assert result.selection_inputs == ()


def test_confirmation_executes_abba_order_and_records_canonical_pairs() -> None:
    """Counter process drift with A-B then B-A while keeping every median pair ordered A-B."""
    first = sample(65536, 40, 100.0)
    second = sample(65536, 38, 120.0)
    order: list[int | None] = []

    def sample_at(ctx: int, n_cpu_moe: int | None):
        """Record execution order and return the matching finalist."""
        del ctx
        order.append(n_cpu_moe)
        return first if n_cpu_moe == first.n_cpu_moe else second

    winner, rounds = _confirm((first, second), sample_at)

    assert order == [40, 38, 38, 40]
    assert tuple(result.medians for result in rounds) == ((100.0, 120.0), (100.0, 120.0))
    assert winner is first


def test_an_envelope_that_stops_fitting_at_the_gate_falls_back_to_its_rival() -> None:
    """Read a point that turned infeasible at the gate as a gate it cannot pass, not as a crash."""
    gated: list[tuple[int, int | None]] = []

    def gate_at(ctx: int, n_cpu_moe: int | None) -> GateResult:
        """Make the prudent point infeasible only when it reaches the gate."""
        gated.append((ctx, n_cpu_moe))
        if n_cpu_moe == 41:
            raise TrialInfeasibleError(f"({ctx}, {n_cpu_moe}) is no longer feasible")
        return GateResult(True, True, None)

    (result,) = run_group(
        _provider(),
        (GateTarget(_mode("coding"), gate_at),),
        GroupPlan(_CONTEXTS, 24, preference="fast"),
    )

    assert any(n_cpu_moe == 41 for _ctx, n_cpu_moe in gated)
    assert result.envelope.sample.n_cpu_moe != 41


def test_reported_phase_caps_cover_every_trial_each_phase_can_start() -> None:
    """Never report a position above its own total: a cap that a real run exceeds is not a cap.

    The one requested preference can run three ABBA rounds, so the cap remains six fresh processes.
    """
    counts = {"search": 0, "pairing": 0, "gate": 0}

    class _Counter(TrialProgress):
        """Count the trials each phase actually starts, per phase name."""

        def started(self) -> None:
            """Record one more started trial for the phase currently entered."""
            counts[self.phase] = counts.get(self.phase, 0) + 1
            super().started()

    progress = _Counter()
    plan = GroupPlan(_CONTEXTS, 24, True, progress)
    run_group(_provider(), (GateTarget(_mode("coding"), _pass_gate),), plan)

    assert counts["search"] <= plan.trial_cap
    assert counts["pairing"] <= MAX_PAIRING_TRIALS
    assert counts["gate"] <= MAX_GATE_TRIALS
    assert MAX_PAIRING_TRIALS == 6
