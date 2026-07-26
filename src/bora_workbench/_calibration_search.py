"""Search the feasible region of one calibration mode group (spec 1.2, 3.3, 5.6).

Two nested searches live here because they answer the same question at two scales: which
configurations this machine can actually serve.

Within one context step the search never maps the full feasible region. It probes the prudent
maximum offload, descends to one feasible anchor if RAM refused that maximum, and then bisects only
the aggressive VRAM side below the anchor. Feasibility here is a class, not a number: a probe either
started and served or it did not, so the bisection needs no peak model and stays exact under a
shared probe budget.

Across the context scale, the group walks the steps under that one shared budget and quick-benches
the boundary region of every feasible step. Trial execution is injected so the orchestration stays
fake-tested; the real provider lives in ``_calibration_trial``. CUDA searches the offload axis at
every context step, while CPU only confirms the baseline because that backend has no offload axis
to search (spec 5.6).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from bora_workbench._calibration_trial_control import TrialProgress
from bora_workbench._calibration_types import (
    MAX_RETRY_PER_TRIAL,
    PRUDENT_N_CPU_MOE,
    ClassifiedOutcome,
    Sample,
    SearchError,
    TrialInfeasibleError,
    TrialOutcome,
)

Probe = Callable[[int], ClassifiedOutcome]
ProbeAt = Callable[[int, int | None], ClassifiedOutcome]
SampleAt = Callable[[int, int | None], Sample]

# A feasible step measures at most the boundary, boundary+2, and the prudent anchor; on CPU it
# measures the single confirmed baseline. The budget bounds probes only, so the trial cap has to
# add these measurements explicitly or the reported position would exceed its own total.
MAX_SAMPLES_PER_STEP = 3


@dataclass(frozen=True, slots=True)
class SearchProvider:
    """Group the shared feasibility probe and quick-bench sample callables for one group."""

    probe_at: ProbeAt
    sample_at: SampleAt


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


@dataclass(frozen=True, slots=True)
class StepFeasibility:
    """Hold one context step's feasibility boundary, prudent anchor, and probe accounting.

    ``boundary`` and ``prudent`` are set together and only when the step is feasible, so a reader
    of either one already knows the step succeeded.
    """

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


def _probe(probe: Probe, value: int) -> ClassifiedOutcome:
    """Probe one value with a single retry; stop the mode on protocol-invalid evidence."""
    for _ in range(MAX_RETRY_PER_TRIAL + 1):
        outcome = probe(value)
        if outcome.outcome is TrialOutcome.PROTOCOL_INVALID:
            raise SearchError(f"n_cpu_moe={value} produced protocol-invalid evidence")
        if outcome.outcome is not TrialOutcome.RETRYABLE:
            return outcome
    raise SearchError(f"n_cpu_moe={value} remained retryable after one retry")


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


def _bisect_vram_side(probe: Probe, prudent: int, state: _StepBudget) -> int:
    """Bisect to the least feasible offload below one verified feasible anchor.

    ``prudent`` is already measured feasible, so it bounds the search from above and is never
    reprobed; an exhausted budget stops at the tightest bound proven so far.
    """
    low, high = 0, prudent
    while low < high:
        split = (low + high) // 2
        if not state.spend(split):
            return high
        if _probe(probe, split).outcome is TrialOutcome.SUCCESS:
            high = split
        else:
            low = split + 1
    return high


def search_step(probe: Probe, budget: int) -> StepFeasibility:
    """Search one context step: prudent probe, optional RAM descent, then VRAM bisection."""
    state = _StepBudget(budget)
    prudent = _find_prudent_anchor(probe, state)
    if prudent is None:
        return StepFeasibility(False, None, None, tuple(state.probed), state.is_exhausted)
    boundary = _bisect_vram_side(probe, prudent, state)
    return StepFeasibility(True, boundary, prudent, tuple(state.probed), state.is_exhausted)


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
    step = search_step(lambda value: provider.probe_at(ctx, value), budget)
    if step.boundary is None or step.prudent is None:
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
