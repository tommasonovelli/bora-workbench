"""Offline tests for feasible-region sampling over the context scale."""

from __future__ import annotations

import pytest

from qwen_launcher._calibration_outcomes import ClassifiedOutcome, TrialOutcome
from qwen_launcher._calibration_sampling import GroupPlan, SearchProvider, search_samples
from qwen_launcher._calibration_types import (
    CONTEXT_SCALE,
    Sample,
    SearchError,
    TrialInfeasibleError,
)
from tests.sample_fixtures import sample

_VRAM = ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram")
_SUCCESS = ClassifiedOutcome(TrialOutcome.SUCCESS)


def test_context_scale_keeps_the_full_seven_step_ladder() -> None:
    """Reach the small contexts, so modest hardware still produces a usable envelope."""
    assert CONTEXT_SCALE == (131072, 98304, 65536, 49152, 32768, 16384, 8192)


def _cuda_provider(feasible_from: int, boundary: int) -> tuple[SearchProvider, list[int]]:
    """Build a provider feasible only at or below one context, recording every probed context."""
    probed: list[int] = []

    def probe_at(ctx: int, n_cpu_moe: int | None) -> ClassifiedOutcome:
        probed.append(ctx)
        assert n_cpu_moe is not None
        return _SUCCESS if ctx <= feasible_from and n_cpu_moe >= boundary else _VRAM

    def sample_at(ctx: int, n_cpu_moe: int | None) -> Sample:
        assert n_cpu_moe is not None
        return sample(ctx, n_cpu_moe, float(ctx))

    return SearchProvider(probe_at, sample_at), probed


def test_infeasible_large_contexts_cost_one_probe_each_and_do_not_end_the_run() -> None:
    """Descend past unaffordable contexts cheaply and still measure the first feasible one."""
    provider, probed = _cuda_provider(feasible_from=32768, boundary=30)
    samples = search_samples(provider, GroupPlan(CONTEXT_SCALE, 28))
    assert probed[:4] == [131072, 98304, 65536, 49152]
    assert {item.ctx for item in samples} <= {32768, 16384, 8192}
    assert samples


def test_the_reported_cap_covers_every_trial_the_search_can_start() -> None:
    """Never report a position above its own total: the budget bounds probes, not measurements."""
    started = 0

    def probe_at(ctx: int, n_cpu_moe: int | None) -> ClassifiedOutcome:
        nonlocal started
        started += 1
        assert n_cpu_moe is not None
        return _SUCCESS if n_cpu_moe >= 30 else _VRAM

    def sample_at(ctx: int, n_cpu_moe: int | None) -> Sample:
        nonlocal started
        started += 1
        assert n_cpu_moe is not None
        return sample(ctx, n_cpu_moe, float(ctx))

    plan = GroupPlan(CONTEXT_SCALE, 28)
    search_samples(SearchProvider(probe_at, sample_at), plan)

    assert started > plan.budget
    assert started <= plan.trial_cap


def test_a_point_that_turns_infeasible_is_dropped_not_fatal() -> None:
    """Drop a single moved boundary point instead of failing the whole mode (spec 3.3)."""
    probe_calls: list[int] = []

    def probe_at(ctx: int, n_cpu_moe: int | None) -> ClassifiedOutcome:
        probe_calls.append(ctx)
        assert n_cpu_moe is not None
        return _SUCCESS if n_cpu_moe >= 30 else _VRAM

    def sample_at(ctx: int, n_cpu_moe: int | None) -> Sample:
        assert n_cpu_moe is not None
        if n_cpu_moe == 30:
            raise TrialInfeasibleError("boundary moved")
        return sample(ctx, n_cpu_moe, float(ctx))

    samples = search_samples(SearchProvider(probe_at, sample_at), GroupPlan((65536,), 28))
    assert samples
    assert all(item.n_cpu_moe != 30 for item in samples)


def test_every_point_turning_infeasible_reports_no_usable_sample() -> None:
    """Report an actionable search failure when nothing measurable survives."""

    def probe_at(ctx: int, n_cpu_moe: int | None) -> ClassifiedOutcome:
        return _SUCCESS

    def sample_at(ctx: int, n_cpu_moe: int | None) -> Sample:
        raise TrialInfeasibleError("boundary moved")

    with pytest.raises(SearchError, match="no feasible context step"):
        search_samples(SearchProvider(probe_at, sample_at), GroupPlan((65536,), 28))


def test_cpu_confirms_the_baseline_without_probing_an_offload_axis() -> None:
    """Never invent a CPU offload axis: probe and sample the baseline once (spec 5.6)."""
    offloads: list[int | None] = []

    def probe_at(ctx: int, n_cpu_moe: int | None) -> ClassifiedOutcome:
        offloads.append(n_cpu_moe)
        return _SUCCESS

    def sample_at(ctx: int, n_cpu_moe: int | None) -> Sample:
        offloads.append(n_cpu_moe)
        return Sample(ctx, n_cpu_moe, "mtp2", sample(ctx, 0, 10.0).quick, 4.0, None, 9.0, None)

    samples = search_samples(
        SearchProvider(probe_at, sample_at), GroupPlan((8192,), 28, has_offload_axis=False)
    )
    assert offloads == [None, None]
    assert [item.n_cpu_moe for item in samples] == [None]


def test_an_infeasible_cpu_baseline_reports_no_usable_sample() -> None:
    """Fail the CPU run explicitly rather than recording an unmeasured baseline."""

    def probe_at(ctx: int, n_cpu_moe: int | None) -> ClassifiedOutcome:
        return ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "ram")

    def sample_at(ctx: int, n_cpu_moe: int | None) -> Sample:
        raise AssertionError("an infeasible baseline must never be measured")

    with pytest.raises(SearchError, match="no feasible context step"):
        search_samples(
            SearchProvider(probe_at, sample_at), GroupPlan((8192,), 28, has_offload_axis=False)
        )
