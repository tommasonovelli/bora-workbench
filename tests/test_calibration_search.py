"""Offline tests for the bounded feasibility search."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from qwen_launcher._calibration_outcomes import ClassifiedOutcome, TrialOutcome
from qwen_launcher._calibration_search import search_step
from qwen_launcher._calibration_types import SearchError

_VRAM = ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram")
_RAM = ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "ram")
_SUCCESS = ClassifiedOutcome(TrialOutcome.SUCCESS)


def region_probe(
    vram_boundary: int, ram_max: int, seen: list[int] | None = None
) -> Callable[[int], ClassifiedOutcome]:
    """Model a contiguous feasible window: low n_cpu_moe lacks VRAM, high n_cpu_moe lacks RAM."""

    def probe(value: int) -> ClassifiedOutcome:
        if seen is not None:
            seen.append(value)
        if value < vram_boundary:
            return _VRAM
        if value > ram_max:
            return _RAM
        return _SUCCESS

    return probe


def test_success_at_prudent_bisects_vram_boundary() -> None:
    """Find the VRAM boundary below a feasible prudent maximum without a RAM descent."""
    result = search_step(region_probe(37, 41), budget=24)
    assert result.is_feasible
    assert result.boundary == 37
    assert result.prudent == 41
    assert not result.is_budget_exhausted


def test_ram_failure_descends_then_bisects_only_the_vram_side() -> None:
    """Descend to one feasible anchor and bisect only the VRAM side, never the RAM ceiling."""
    seen: list[int] = []
    result = search_step(region_probe(15, 30, seen), budget=24)
    assert result.is_feasible
    assert result.boundary == 15
    assert result.prudent == 20
    assert max(value for value in seen if value != 41) <= 20


def test_vram_failure_at_prudent_marks_the_step_infeasible() -> None:
    """Report an infeasible step when maximum offload still violates the VRAM reserve."""
    result = search_step(region_probe(42, 45), budget=24)
    assert not result.is_feasible
    assert result.boundary is None
    assert result.prudent is None


def test_single_retry_is_tolerated_before_classifying() -> None:
    """Accept one transient retry at the prudent probe and still find the boundary."""
    seen: list[int] = []
    base = region_probe(37, 41, seen)

    def flaky(value: int) -> ClassifiedOutcome:
        if value == 41 and seen.count(41) == 0:
            seen.append(41)
            return ClassifiedOutcome(TrialOutcome.RETRYABLE)
        return base(value)

    result = search_step(flaky, budget=24)
    assert result.boundary == 37
    assert seen.count(41) == 2


def test_persistent_retryable_and_protocol_invalid_stop_the_mode() -> None:
    """Raise after one useless retry and immediately on protocol-invalid evidence."""
    with pytest.raises(SearchError, match="retryable"):
        search_step(lambda value: ClassifiedOutcome(TrialOutcome.RETRYABLE), budget=24)
    with pytest.raises(SearchError, match="protocol-invalid"):
        search_step(lambda value: ClassifiedOutcome(TrialOutcome.PROTOCOL_INVALID), budget=24)


def test_exhausted_budget_is_reported_with_partial_boundary() -> None:
    """Stop probing when the step budget runs out and flag the partial evidence."""
    result = search_step(region_probe(15, 30), budget=2)
    assert result.is_feasible
    assert result.is_budget_exhausted
