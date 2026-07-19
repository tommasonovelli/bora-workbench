"""Select paired calibration/v3 finalists by unanimity and deterministic safety tie-breaks."""

from __future__ import annotations

from qwen_launcher._calibration_v3_types import (
    SELECTION_DOMINANCE,
    SELECTION_DRIFT,
    SELECTION_FREE_VRAM,
    SELECTION_PRUDENT,
    SELECTION_SINGLE,
    SelectionCandidate,
)


def _round_winners(candidates: tuple[SelectionCandidate, ...]) -> tuple[int | None, ...]:
    """Compare paired session medians and return each round's winner or tie marker."""
    first, second = candidates
    if len(first.round_medians) != len(second.round_medians):
        raise ValueError("paired finalists must contain the same number of rounds")
    winners: list[int | None] = []
    for first_rate, second_rate in zip(first.round_medians, second.round_medians, strict=True):
        winner = 0 if first_rate > second_rate else 1 if second_rate > first_rate else None
        winners.append(winner)
    return tuple(winners)


def _fallback_index(candidates: tuple[SelectionCandidate, ...]) -> tuple[int, str]:
    """Prefer the larger VRAM margin, then the more prudent axis value."""
    first, second = candidates
    first_free = first.minimum_free_vram_gib
    second_free = second.minimum_free_vram_gib
    if first_free != second_free:
        first_value = -1.0 if first_free is None else first_free
        second_value = -1.0 if second_free is None else second_free
        return (0 if first_value > second_value else 1), SELECTION_FREE_VRAM
    first_prudence = -1 if first.n_cpu_moe is None else first.n_cpu_moe
    second_prudence = -1 if second.n_cpu_moe is None else second.n_cpu_moe
    return (0 if first_prudence >= second_prudence else 1), SELECTION_PRUDENT


def select_candidate_index(
    candidates: tuple[SelectionCandidate, ...], *, has_baseline_drift: bool = False
) -> tuple[int, str, tuple[int | None, ...]]:
    """Select by round unanimity, degrading honestly to memory margin and prudence."""
    if len(candidates) == 1:
        rounds = len(candidates[0].round_medians)
        return 0, SELECTION_SINGLE, (None,) * rounds
    if len(candidates) != 2:
        raise ValueError("calibration/v3 confirms at most two finalists per mode")
    winners = _round_winners(candidates)
    fallback_index, fallback_rule = _fallback_index(candidates)
    if has_baseline_drift:
        return fallback_index, SELECTION_DRIFT, winners
    if winners and winners[0] is not None and all(winner == winners[0] for winner in winners):
        return int(winners[0]), SELECTION_DOMINANCE, winners
    return fallback_index, fallback_rule, winners
