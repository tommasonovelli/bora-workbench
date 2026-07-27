"""Decide one requested envelope for each mode in a calibration group (spec section 5.6).

One decision runs in three stages over the samples a group measured: selection picks the requested
preference, ABBA confirmation re-measures only a pair selection could not separate, and the final
gate accepts the envelope or falls back once to its near-tied rival. The stages share the same
near-tie definition, so a material rival is exactly the one confirmation re-measures and the gate
retries.

Every selection and confirmation rule is a pure function of the measured samples, so the recorded
choice can be reconstructed from the record. Trial execution is injected, which keeps this
orchestration fake-tested; the real provider lives in ``_calibration_trial`` and the feasible-region
search in ``_calibration_search``. Text modes (coding+studio) share one hardware search and set of
samples and differ only by their per-mode gate and recorded policy; vstudio runs its own group.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from statistics import median

from bora_workbench._calibration_search import (
    ConfirmAt,
    GroupPlan,
    SearchProvider,
    search_samples,
)
from bora_workbench._calibration_types import (
    BALANCED_CEILING,
    DEADBAND_PCT,
    MIN_CTX_FAST,
    EnvelopeResult,
    GateResult,
    Preference,
    Sample,
    SearchError,
    TrialInfeasibleError,
)
from bora_workbench.benchmark_quick import ShortBench
from bora_workbench.profiles import Mode

GateAt = Callable[[int, int | None], GateResult]

# max_context is decided by the largest feasible context, which re-measurement cannot change, so it
# never pairs. Both phase totals are caps, not schedules: the requested paired preference runs two
# or three ABBA rounds of two trials, and its gate may additionally try one rival.
_PAIRED_PREFERENCES = frozenset({"fast", "balanced"})
_MAX_ABBA_ROUNDS = 3
_TRIALS_PER_ROUND = 2
MAX_PAIRING_TRIALS = _MAX_ABBA_ROUNDS * _TRIALS_PER_ROUND
MAX_GATE_TRIALS = 2

_DISPERSION_LIMIT = 0.10
_THIRD_ROUND_FACTOR = 1.5


@dataclass(frozen=True, slots=True)
class GateTarget:
    """Bind one mode to its per-mode final gate callable within a shared search group."""

    mode: Mode
    gate_at: GateAt


@dataclass(frozen=True, slots=True)
class ModeResult:
    """Hold one mode's requested gated envelope and the shared samples behind it."""

    mode: Mode
    envelope: EnvelopeResult
    samples: tuple[Sample, ...]
    selection_inputs: tuple[tuple[float, float], ...]


def _free_vram(sample: Sample) -> float:
    """Return comparable minimum free VRAM, treating an absent value as the least margin."""
    return -1.0 if sample.vram_min_free_gib is None else sample.vram_min_free_gib


def _prudence(sample: Sample) -> int:
    """Return the offload prudence tie-break, which is constant on a backend without that axis."""
    return 0 if sample.n_cpu_moe is None else sample.n_cpu_moe


def _within_deadband(value: float, best: float) -> bool:
    """Return whether one smaller-is-better value stays inside the material-improvement band."""
    return value <= best * (1 + DEADBAND_PCT / 100)


def _throughput_key(sample: Sample) -> tuple[float, float, int]:
    """Order samples by throughput, then VRAM margin, then prudence."""
    return (sample.decode_tps, _free_vram(sample), _prudence(sample))


def _fast_key(sample: Sample) -> tuple[float, float, int]:
    """Break a fast deadband tie by prefill, then VRAM margin, then prudence."""
    return (sample.prefill_tps, _free_vram(sample), _prudence(sample))


def _select_fast(samples: tuple[Sample, ...]) -> Sample:
    """Return the minimum median short end-to-end sample at or above the fast context floor."""
    eligible = tuple(sample for sample in samples if sample.ctx >= MIN_CTX_FAST) or samples
    best_e2e = min(sample.e2e_ms for sample in eligible)
    contenders = tuple(sample for sample in eligible if _within_deadband(sample.e2e_ms, best_e2e))
    return max(contenders, key=_fast_key)


def _select_balanced(samples: tuple[Sample, ...], fast: Sample) -> Sample:
    """Return the largest context whose short end-to-end stays within the balanced ceiling."""
    ceiling = fast.e2e_ms * BALANCED_CEILING
    eligible = tuple(sample for sample in samples if sample.e2e_ms <= ceiling) or (fast,)
    max_ctx = max(sample.ctx for sample in eligible)
    return max((s for s in eligible if s.ctx == max_ctx), key=_throughput_key)


def _select_max_context(samples: tuple[Sample, ...]) -> Sample:
    """Return the maximum feasible context, ordered by those throughput semantics within it."""
    max_ctx = max(sample.ctx for sample in samples)
    return max((s for s in samples if s.ctx == max_ctx), key=_throughput_key)


def select_envelope(samples: tuple[Sample, ...], preference: Preference) -> Sample:
    """Select only the requested preference from shared feasible samples (spec section 5.6)."""
    if preference == "max_context":
        return _select_max_context(samples)
    fast = _select_fast(samples)
    if preference == "fast":
        return fast
    return _select_balanced(samples, fast)


def _fast_rivals(samples: tuple[Sample, ...], winner: Sample) -> tuple[Sample, ...]:
    """Return fast contenders whose short end-to-end stays within the winner's deadband."""
    pool = tuple(sample for sample in samples if sample.ctx >= MIN_CTX_FAST) or samples
    return tuple(sample for sample in pool if _within_deadband(sample.e2e_ms, winner.e2e_ms))


def _throughput_rivals(samples: tuple[Sample, ...], winner: Sample) -> tuple[Sample, ...]:
    """Return same-context contenders whose decode throughput ties the winner within deadband."""
    floor = winner.decode_tps * (1 - DEADBAND_PCT / 100)
    return tuple(s for s in samples if s.ctx == winner.ctx and s.decode_tps >= floor)


def near_tied_rival(
    samples: tuple[Sample, ...], winner: Sample, preference: Preference
) -> Sample | None:
    """Return the strongest distinct contender ABBA must disambiguate, or None when clear."""
    rivals = (
        _fast_rivals(samples, winner)
        if preference == "fast"
        else _throughput_rivals(samples, winner)
    )
    key = _fast_key if preference == "fast" else _throughput_key
    others = tuple(
        sample
        for sample in rivals
        if (sample.ctx, sample.n_cpu_moe) != (winner.ctx, winner.n_cpu_moe)
    )
    return max(others, key=key) if others else None


@dataclass(frozen=True, slots=True)
class RoundResult:
    """Hold one ABBA round's per-finalist median metric and intra-round dispersion fraction."""

    medians: tuple[float, float]
    dispersions: tuple[float, float]


def _round_winner(medians: tuple[float, float]) -> int | None:
    """Return the better finalist, or None when the round stays inside the deadband."""
    first, second = medians
    if abs(first - second) <= DEADBAND_PCT / 100 * min(first, second):
        return None
    return 0 if first < second else 1


def _aggregate(rounds: tuple[RoundResult, ...]) -> tuple[float, float]:
    """Return each finalist's median metric across the completed rounds."""
    return (
        median(round_result.medians[0] for round_result in rounds),
        median(round_result.medians[1] for round_result in rounds),
    )


def needs_third_round(rounds: tuple[RoundResult, RoundResult]) -> bool:
    """Trigger a third round on discordant winners, a sub-1.5x gap, or noise (spec section 5.6)."""
    winners = {value for value in (_round_winner(r.medians) for r in rounds) if value is not None}
    if len(winners) > 1:
        return True
    first, second = _aggregate(rounds)
    if abs(first - second) < _THIRD_ROUND_FACTOR * DEADBAND_PCT / 100 * min(first, second):
        return True
    return any(value > _DISPERSION_LIMIT for r in rounds for value in r.dispersions)


def _equivalence_index(finalists: tuple[Sample, Sample]) -> int:
    """Break an equivalent confirmation by VRAM margin, then prudence.

    A backend without an offload axis records no ``n_cpu_moe``; both finalists then compare equal
    and the first one wins, keeping the rule total instead of comparing two absent values. That
    absent axis sorts below every real offload here, which is why this tie-break does not reuse
    ``_prudence``: the two rules only ever agree on the samples one group can actually produce.
    """
    first, second = finalists
    first_free, second_free = _free_vram(first), _free_vram(second)
    if first_free != second_free:
        return 0 if first_free > second_free else 1
    first_offload = -1 if first.n_cpu_moe is None else first.n_cpu_moe
    second_offload = -1 if second.n_cpu_moe is None else second.n_cpu_moe
    return 0 if first_offload >= second_offload else 1


def resolve(rounds: tuple[RoundResult, ...], finalists: tuple[Sample, Sample]) -> int:
    """Resolve the confirmed winner by decisive-round majority, then material equivalence."""
    winners = [value for value in (_round_winner(r.medians) for r in rounds) if value is not None]
    zeros, ones = winners.count(0), winners.count(1)
    if zeros != ones:
        return 0 if zeros > ones else 1
    return _equivalence_index(finalists)


class _FinalistLost(Exception):
    """Carry which finalist stopped being feasible while confirmation was re-measuring it."""

    def __init__(self, index: int) -> None:
        """Retain the finalist position so the caller can keep the other one."""
        super().__init__(f"finalist {index} is no longer feasible")
        self.index = index


def _remeasure(finalist: Sample, index: int, confirm_at: ConfirmAt) -> ShortBench:
    """Re-measure one finalist, reporting which one the memory boundary moved under."""
    try:
        return confirm_at(finalist.ctx, finalist.n_cpu_moe)
    except TrialInfeasibleError as error:
        raise _FinalistLost(index) from error


def _abba_round(
    finalists: tuple[Sample, Sample], confirm_at: ConfirmAt, is_reversed: bool = False
) -> RoundResult:
    """Measure one A-B or B-A round while returning metrics in canonical finalist order."""
    order = (1, 0) if is_reversed else (0, 1)
    measured = {index: _remeasure(finalists[index], index, confirm_at) for index in order}
    first, second = measured[0], measured[1]
    return RoundResult(
        (first.e2e_median_ms, second.e2e_median_ms), (first.dispersion, second.dispersion)
    )


def _finalists(
    samples: tuple[Sample, ...], winner: Sample, preference: Preference
) -> tuple[Sample, Sample] | None:
    """Pair the winner with the rival ABBA has to separate, or None when the choice is clear."""
    if preference not in _PAIRED_PREFERENCES:
        return None
    rival = near_tied_rival(samples, winner, preference)
    return None if rival is None else (winner, rival)


def _confirm(
    finalists: tuple[Sample, Sample], confirm_at: ConfirmAt
) -> tuple[Sample, tuple[RoundResult, ...]]:
    """Disambiguate near-tied finalists with ABBA and the third-round rule (spec section 5.6).

    The confirmed winner is the finalist the search already measured, not a round's re-measurement,
    so the recorded cell keeps the full quick-bench evidence a confirmation round never produces.

    A finalist that stops fitting the reserves between the search and confirmation cannot become a
    launch envelope, so the surviving finalist is confirmed with no recorded rounds instead of
    failing the mode: the comparison is abandoned, never silently continued with one side missing.
    """
    try:
        rounds = [
            _abba_round(finalists, confirm_at),
            _abba_round(finalists, confirm_at, is_reversed=True),
        ]
        if needs_third_round((rounds[0], rounds[1])):
            rounds.append(_abba_round(finalists, confirm_at))
    except _FinalistLost as lost:
        return finalists[1 - lost.index], ()
    return finalists[resolve(tuple(rounds), finalists)], tuple(rounds)


def _confirm_selected(
    samples: tuple[Sample, ...], confirm_at: ConfirmAt, preference: Preference
) -> tuple[Sample, tuple[tuple[float, float], ...]]:
    """Confirm only the requested preference and retain its canonical finalist medians."""
    winner = select_envelope(samples, preference)
    pair = _finalists(samples, winner, preference)
    sample, rounds = (winner, ()) if pair is None else _confirm(pair, confirm_at)
    return sample, tuple(round_result.medians for round_result in rounds)


def _gate_candidates(
    samples: tuple[Sample, ...], winner: Sample, preference: Preference
) -> Iterator[Sample]:
    """Yield the confirmed envelope, then the one rival that earns a second gate.

    The rival is looked up lazily, so a winner that passes its gate never runs the search for one.
    """
    yield winner
    rival = near_tied_rival(samples, winner, preference)
    if rival is not None:
        yield rival


def _gate_envelope(
    target: GateTarget, preference: Preference, candidates: Iterator[Sample]
) -> EnvelopeResult:
    """Return the first candidate that passes the mode's final gate (spec section 5.6).

    A point that turned infeasible since it was confirmed cannot become a launch envelope, so it
    counts as a gate it did not pass rather than as a failure of the whole run.
    """
    for candidate in candidates:
        try:
            result = target.gate_at(candidate.ctx, candidate.n_cpu_moe)
        except TrialInfeasibleError:
            continue
        if result.passed:
            return EnvelopeResult(preference, candidate, result)
    raise SearchError(f"{preference} envelope failed the final gate for mode {target.mode.id}")


def run_group(
    provider: SearchProvider, targets: tuple[GateTarget, ...], plan: GroupPlan
) -> tuple[ModeResult, ...]:
    """Run one shared search, then confirm and gate the requested cell for each mode."""
    # The label names every mode of the group, because one search serves all of their trials.
    label = "+".join(target.mode.id for target in targets)
    plan.progress.enter(label, "search", plan.trial_cap)
    samples = search_samples(provider, plan)
    if plan.preference in _PAIRED_PREFERENCES:
        plan.progress.enter(label, "pairing", MAX_PAIRING_TRIALS)
    confirmed, inputs = _confirm_selected(samples, provider.confirm_at, plan.preference)
    results = []
    for target in targets:
        plan.progress.enter(target.mode.id, "gate", MAX_GATE_TRIALS)
        candidates = _gate_candidates(samples, confirmed, plan.preference)
        envelope = _gate_envelope(target, plan.preference, candidates)
        results.append(ModeResult(target.mode, envelope, samples, inputs))
    return tuple(results)
