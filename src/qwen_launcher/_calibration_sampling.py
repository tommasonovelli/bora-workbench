"""Measure the feasible region of one calibration mode group (spec 1.2, 3.3).

Trial execution is injected so the orchestration stays fake-tested; the real provider lives in
``_calibration_trial``. CUDA searches the offload axis at every context step, while CPU only
confirms the baseline because that backend has no offload axis to search (spec 5.6).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from qwen_launcher._calibration_outcomes import ClassifiedOutcome, TrialOutcome
from qwen_launcher._calibration_progress import TrialProgress
from qwen_launcher._calibration_search import search_step
from qwen_launcher._calibration_types import Sample, SearchError, TrialInfeasibleError

ProbeAt = Callable[[int, int | None], ClassifiedOutcome]
SampleAt = Callable[[int, int | None], Sample]


@dataclass(frozen=True, slots=True)
class SearchProvider:
    """Group the shared feasibility probe and quick-bench sample callables for one group."""

    probe_at: ProbeAt
    sample_at: SampleAt


# A feasible step measures at most the boundary, boundary+2, and the prudent anchor; on CPU it
# measures the single confirmed baseline. The budget bounds probes only, so the trial cap has to
# add these measurements explicitly or the reported position would exceed its own total.
MAX_SAMPLES_PER_STEP = 3


@dataclass(frozen=True, slots=True)
class GroupPlan:
    """Hold the context scale, shared probe budget, offload axis, and progress of one group.

    Progress belongs to the group because the group is exactly the scope whose trials are shared.
    """

    contexts: tuple[int, ...]
    budget: int
    has_offload_axis: bool = True
    progress: TrialProgress = field(default_factory=TrialProgress)

    @property
    def trial_cap(self) -> int:
        """Return the highest number of fresh processes this search can start.

        The budget caps probes; every feasible step additionally quick-benches its sample points,
        and those trials are what the operator watches, so they belong in the reported cap.
        """
        if not self.has_offload_axis:
            return 2 * len(self.contexts)
        return self.budget + MAX_SAMPLES_PER_STEP * len(self.contexts)


def _sample_points(boundary: int, prudent: int) -> tuple[int, ...]:
    """Return boundary, boundary+2, and the prudent anchor, clamped and de-duplicated."""
    return tuple(sorted({boundary, min(boundary + 2, prudent), prudent}))


def _measure(provider: SearchProvider, ctx: int, points: tuple[int | None, ...]) -> list[Sample]:
    """Measure each point, dropping one whose boundary moved between probe and quick-bench."""
    samples: list[Sample] = []
    for n_cpu_moe in points:
        try:
            samples.append(provider.sample_at(ctx, n_cpu_moe))
        except TrialInfeasibleError:
            continue
    return samples


def _cuda_step(provider: SearchProvider, ctx: int, budget: int) -> tuple[list[Sample], int]:
    """Search one context's offload boundary and measure its boundary region."""
    step = search_step(lambda value, fixed=ctx: provider.probe_at(fixed, value), budget)
    if not step.is_feasible or step.boundary is None or step.prudent is None:
        return [], len(step.probed)
    points = _sample_points(step.boundary, step.prudent)
    return _measure(provider, ctx, points), len(step.probed)


def _cpu_step(provider: SearchProvider, ctx: int) -> tuple[list[Sample], int]:
    """Confirm one context on CPU without inventing an offload axis (spec 5.6)."""
    if provider.probe_at(ctx, None).outcome is not TrialOutcome.SUCCESS:
        return [], 1
    return _measure(provider, ctx, (None,)), 1


def search_samples(provider: SearchProvider, plan: GroupPlan) -> tuple[Sample, ...]:
    """Search every context step and measure each feasible step's usable samples."""
    samples: list[Sample] = []
    remaining = plan.budget
    for ctx in plan.contexts:
        if plan.has_offload_axis:
            measured, spent = _cuda_step(provider, ctx, remaining)
        else:
            measured, spent = _cpu_step(provider, ctx)
        samples.extend(measured)
        remaining -= spent
        if remaining <= 0:
            break
    if not samples:
        raise SearchError("no feasible context step produced a usable sample")
    return tuple(samples)
