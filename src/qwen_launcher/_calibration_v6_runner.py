"""Orchestrate one calibration/v6-lite mode group over injectable trial providers (spec 1.2).

Trial execution is injected so the orchestration is tested fake-first; the real provider lives in
``_calibration_v6_trial``. Text modes (coding+studio) share one hardware search and set of samples
and differ only by their per-mode gate and recorded policy; vstudio runs its own group.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from statistics import median

from qwen_launcher._calibration_outcomes import ClassifiedOutcome
from qwen_launcher._calibration_v6_confirm import RoundResult, needs_third_round, resolve
from qwen_launcher._calibration_v6_search import search_step
from qwen_launcher._calibration_v6_selection import near_tied_rival, select_envelopes
from qwen_launcher._calibration_v6_types import (
    EnvelopeResult,
    GateResult,
    Preference,
    V6Sample,
    V6SearchError,
)
from qwen_launcher.profiles import Mode

ProbeAt = Callable[[int, int], ClassifiedOutcome]
SampleAt = Callable[[int, int], V6Sample]
GateAt = Callable[[int, int], GateResult]


@dataclass(frozen=True, slots=True)
class SearchProvider:
    """Group the shared feasibility probe and quick-bench sample callables for one group."""

    probe_at: ProbeAt
    sample_at: SampleAt


@dataclass(frozen=True, slots=True)
class GateTarget:
    """Bind one mode to its per-mode final gate callable within a shared search group."""

    mode: Mode
    gate_at: GateAt


@dataclass(frozen=True, slots=True)
class GroupPlan:
    """Hold the context scale and shared probe budget for one mode group."""

    contexts: tuple[int, ...]
    budget: int


@dataclass(frozen=True, slots=True)
class ModeResult:
    """Hold one mode's confirmed, gated envelopes and the shared samples behind them."""

    mode: Mode
    envelopes: dict[Preference, EnvelopeResult]
    samples: tuple[V6Sample, ...]
    selection_inputs: dict[Preference, tuple[tuple[float, float], ...]]


def _sample_points(boundary: int, prudent: int) -> tuple[int, ...]:
    """Return boundary, boundary+2, and the prudent anchor, clamped and de-duplicated."""
    return tuple(sorted({boundary, min(boundary + 2, prudent), prudent}))


def search_samples(provider: SearchProvider, plan: GroupPlan) -> tuple[V6Sample, ...]:
    """Search every context step and measure each feasible step's boundary-region samples."""
    samples: list[V6Sample] = []
    remaining = plan.budget
    for ctx in plan.contexts:
        step = search_step(lambda value, fixed=ctx: provider.probe_at(fixed, value), remaining)
        remaining -= len(step.probed)
        if step.is_feasible and step.boundary is not None and step.prudent is not None:
            samples.extend(
                provider.sample_at(ctx, n) for n in _sample_points(step.boundary, step.prudent)
            )
        if remaining <= 0:
            break
    if not samples:
        raise V6SearchError("no feasible context step produced a usable sample")
    return tuple(samples)


def _dispersion(sample: V6Sample) -> float:
    """Return the intra-sample short end-to-end spread the third-round rule inspects."""
    values = [metric.e2e_ms for metric in sample.quick.short]
    center = median(values)
    return (max(values) - min(values)) / center if center else 0.0


def _abba_round(finalists: tuple[V6Sample, V6Sample], sample_at: SampleAt) -> RoundResult:
    """Re-measure both finalists once and report their medians and dispersions for one round."""
    first = sample_at(finalists[0].ctx, finalists[0].n_cpu_moe)
    second = sample_at(finalists[1].ctx, finalists[1].n_cpu_moe)
    return RoundResult((first.e2e_ms, second.e2e_ms), (_dispersion(first), _dispersion(second)))


def _confirm(
    samples: tuple[V6Sample, ...], preference: Preference, winner: V6Sample, sample_at: SampleAt
) -> tuple[V6Sample, tuple[RoundResult, ...]]:
    """Disambiguate a near-tied fast or balanced winner with ABBA and the third-round rule."""
    rival = None if preference == "max_context" else near_tied_rival(samples, winner, preference)
    if rival is None:
        return winner, ()
    finalists = (winner, rival)
    rounds = [_abba_round(finalists, sample_at), _abba_round(finalists, sample_at)]
    if needs_third_round((rounds[0], rounds[1])):
        rounds.append(_abba_round(finalists, sample_at))
    return finalists[resolve(tuple(rounds), finalists)], tuple(rounds)


def _gate_envelope(
    target: GateTarget, preference: Preference, sample: V6Sample, samples: tuple[V6Sample, ...]
) -> EnvelopeResult:
    """Gate the confirmed envelope, retrying the next candidate once before failing the mode."""
    result = target.gate_at(sample.ctx, sample.n_cpu_moe)
    if result.passed:
        return EnvelopeResult(preference, sample, result)
    rival = near_tied_rival(samples, sample, preference)
    if rival is not None and (retry := target.gate_at(rival.ctx, rival.n_cpu_moe)).passed:
        return EnvelopeResult(preference, rival, retry)
    raise V6SearchError(f"{preference} envelope failed the final gate for mode {target.mode.id}")


def run_group(
    provider: SearchProvider, targets: tuple[GateTarget, ...], plan: GroupPlan
) -> tuple[ModeResult, ...]:
    """Run one shared search, then confirm and gate each mode's envelopes from those samples."""
    samples = search_samples(provider, plan)
    winners = select_envelopes(samples)
    confirmed: dict[Preference, V6Sample] = {}
    inputs: dict[Preference, tuple[tuple[float, float], ...]] = {}
    for preference, winner in winners.items():
        sample, rounds = _confirm(samples, preference, winner, provider.sample_at)
        confirmed[preference] = sample
        inputs[preference] = tuple(round_result.medians for round_result in rounds)
    results = []
    for target in targets:
        envelopes = {
            preference: _gate_envelope(target, preference, sample, samples)
            for preference, sample in confirmed.items()
        }
        results.append(ModeResult(target.mode, envelopes, samples, inputs))
    return tuple(results)
