"""ABBA confirmation and the conditional third-round rule for calibration/v6-lite (spec 3.4).

Confirmation compares two finalists on a lower-is-better metric (short end-to-end for fast and
balanced; the runner passes negated throughput for max_context). Every rule here is pure so the
record can reconstruct the confirmed choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from qwen_launcher._calibration_v6_types import DEADBAND_PCT, V6Sample

_DISPERSION_LIMIT = 0.10
_THIRD_ROUND_FACTOR = 1.5


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
    """Trigger a third round on discordant winners, a sub-1.5x gap, or a noisy round (spec 3.4)."""
    winners = {value for value in (_round_winner(r.medians) for r in rounds) if value is not None}
    if len(winners) > 1:
        return True
    first, second = _aggregate(rounds)
    if abs(first - second) < _THIRD_ROUND_FACTOR * DEADBAND_PCT / 100 * min(first, second):
        return True
    return any(value > _DISPERSION_LIMIT for r in rounds for value in r.dispersions)


def _equivalence_index(finalists: tuple[V6Sample, V6Sample]) -> int:
    """Break an equivalent confirmation by VRAM margin, then prudence (v5 semantics)."""
    first, second = finalists
    first_free = -1.0 if first.vram_min_free_gib is None else first.vram_min_free_gib
    second_free = -1.0 if second.vram_min_free_gib is None else second.vram_min_free_gib
    if first_free != second_free:
        return 0 if first_free > second_free else 1
    return 0 if first.n_cpu_moe >= second.n_cpu_moe else 1


def resolve(rounds: tuple[RoundResult, ...], finalists: tuple[V6Sample, V6Sample]) -> int:
    """Resolve the confirmed winner by decisive-round majority, then material equivalence."""
    winners = [value for value in (_round_winner(r.medians) for r in rounds) if value is not None]
    zeros, ones = winners.count(0), winners.count(1)
    if zeros != ones:
        return 0 if zeros > ones else 1
    return _equivalence_index(finalists)
