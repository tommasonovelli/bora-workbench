"""Orchestrate one calibration mode group over injectable trial providers (spec 1.2).

Trial execution is injected so the orchestration is tested fake-first; the real provider lives in
``_calibration_trial`` and the feasible-region search in ``_calibration_sampling``. Text modes
(coding+studio) share one hardware search and set of samples and differ only by their per-mode gate
and recorded policy; vstudio runs its own group.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from statistics import median

from bora_workbench._calibration_confirm import RoundResult, needs_third_round, resolve
from bora_workbench._calibration_sampling import (
    GroupPlan,
    SampleAt,
    SearchProvider,
    search_samples,
)
from bora_workbench._calibration_selection import near_tied_rival, select_envelopes
from bora_workbench._calibration_types import (
    PREFERENCES,
    EnvelopeResult,
    GateResult,
    Preference,
    Sample,
    SearchError,
    TrialInfeasibleError,
)
from bora_workbench.profiles import Mode

GateAt = Callable[[int, int | None], GateResult]

# Both phase totals are caps, not schedules. Confirmation pairs every preference that can have a
# near-tied rival, and each of those runs two or three ABBA rounds of two trials; max_context never
# pairs, so it contributes nothing. Each envelope's gate may additionally gate one rival.
_PAIRED_PREFERENCES = tuple(name for name in PREFERENCES if name != "max_context")
_MAX_ABBA_ROUNDS = 3
_TRIALS_PER_ROUND = 2
MAX_PAIRING_TRIALS = len(_PAIRED_PREFERENCES) * _MAX_ABBA_ROUNDS * _TRIALS_PER_ROUND
MAX_GATE_TRIALS = len(PREFERENCES) * 2


@dataclass(frozen=True, slots=True)
class GateTarget:
    """Bind one mode to its per-mode final gate callable within a shared search group."""

    mode: Mode
    gate_at: GateAt


@dataclass(frozen=True, slots=True)
class ModeResult:
    """Hold one mode's confirmed, gated envelopes and the shared samples behind them."""

    mode: Mode
    envelopes: dict[Preference, EnvelopeResult]
    samples: tuple[Sample, ...]
    selection_inputs: dict[Preference, tuple[tuple[float, float], ...]]


def _dispersion(sample: Sample) -> float:
    """Return the intra-sample short end-to-end spread the third-round rule inspects."""
    values = [metric.e2e_ms for metric in sample.quick.short]
    center = median(values)
    return (max(values) - min(values)) / center if center else 0.0


class _FinalistLost(Exception):
    """Carry which finalist stopped being feasible while confirmation was re-measuring it."""

    def __init__(self, index: int) -> None:
        """Retain the finalist position so the caller can keep the other one."""
        super().__init__(f"finalist {index} is no longer feasible")
        self.index = index


def _remeasure(finalist: Sample, index: int, sample_at: SampleAt) -> Sample:
    """Re-measure one finalist, reporting which one the memory boundary moved under."""
    try:
        return sample_at(finalist.ctx, finalist.n_cpu_moe)
    except TrialInfeasibleError as error:
        raise _FinalistLost(index) from error


def _abba_round(finalists: tuple[Sample, Sample], sample_at: SampleAt) -> RoundResult:
    """Re-measure both finalists once and report their medians and dispersions for one round."""
    first = _remeasure(finalists[0], 0, sample_at)
    second = _remeasure(finalists[1], 1, sample_at)
    return RoundResult((first.e2e_ms, second.e2e_ms), (_dispersion(first), _dispersion(second)))


def _confirm(
    samples: tuple[Sample, ...], preference: Preference, winner: Sample, sample_at: SampleAt
) -> tuple[Sample, tuple[RoundResult, ...]]:
    """Disambiguate a near-tied fast or balanced winner with ABBA and the third-round rule.

    A finalist that stops fitting the reserves between the search and confirmation cannot become a
    launch envelope, so the surviving finalist is confirmed with no recorded rounds instead of
    failing the mode: the comparison is abandoned, never silently continued with one side missing.
    """
    rival = None if preference == "max_context" else near_tied_rival(samples, winner, preference)
    if rival is None:
        return winner, ()
    finalists = (winner, rival)
    try:
        rounds = [_abba_round(finalists, sample_at), _abba_round(finalists, sample_at)]
        if needs_third_round((rounds[0], rounds[1])):
            rounds.append(_abba_round(finalists, sample_at))
    except _FinalistLost as lost:
        return finalists[1 - lost.index], ()
    return finalists[resolve(tuple(rounds), finalists)], tuple(rounds)


def _gate(target: GateTarget, sample: Sample) -> GateResult | None:
    """Gate one envelope, reading a point that turned infeasible as a gate it cannot pass."""
    try:
        return target.gate_at(sample.ctx, sample.n_cpu_moe)
    except TrialInfeasibleError:
        return None


def _gate_envelope(
    target: GateTarget, preference: Preference, sample: Sample, samples: tuple[Sample, ...]
) -> EnvelopeResult:
    """Gate the confirmed envelope, retrying the next candidate once before failing the mode."""
    result = _gate(target, sample)
    if result is not None and result.passed:
        return EnvelopeResult(preference, sample, result)
    rival = near_tied_rival(samples, sample, preference)
    if rival is not None and (retry := _gate(target, rival)) is not None and retry.passed:
        return EnvelopeResult(preference, rival, retry)
    raise SearchError(f"{preference} envelope failed the final gate for mode {target.mode.id}")


def _group_label(targets: tuple[GateTarget, ...]) -> str:
    """Name the modes that share one hardware search, because their trials are shared too."""
    return "+".join(target.mode.id for target in targets)


def _confirm_all(
    provider: SearchProvider, samples: tuple[Sample, ...]
) -> tuple[dict[Preference, Sample], dict[Preference, tuple[tuple[float, float], ...]]]:
    """Confirm every preference envelope from the shared samples of one group."""
    winners = select_envelopes(samples)
    confirmed: dict[Preference, Sample] = {}
    inputs: dict[Preference, tuple[tuple[float, float], ...]] = {}
    for preference, winner in winners.items():
        sample, rounds = _confirm(samples, preference, winner, provider.sample_at)
        confirmed[preference] = sample
        inputs[preference] = tuple(round_result.medians for round_result in rounds)
    return confirmed, inputs


def run_group(
    provider: SearchProvider, targets: tuple[GateTarget, ...], plan: GroupPlan
) -> tuple[ModeResult, ...]:
    """Run one shared search, then confirm and gate each mode's envelopes from those samples."""
    label = _group_label(targets)
    plan.progress.enter(label, "search", plan.trial_cap)
    samples = search_samples(provider, plan)
    plan.progress.enter(label, "pairing", MAX_PAIRING_TRIALS)
    confirmed, inputs = _confirm_all(provider, samples)
    results = []
    for target in targets:
        plan.progress.enter(target.mode.id, "gate", MAX_GATE_TRIALS)
        envelopes = {
            preference: _gate_envelope(target, preference, sample, samples)
            for preference, sample in confirmed.items()
        }
        results.append(ModeResult(target.mode, envelopes, samples, inputs))
    return tuple(results)
