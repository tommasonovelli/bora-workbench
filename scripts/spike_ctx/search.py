"""Run the spike's bounded class-based n_cpu_moe feasibility search."""

from __future__ import annotations

from collections.abc import Callable

from qwen_launcher._calibration_outcomes import TrialOutcome, classify
from scripts.spike_ctx.models import SearchResult, SearchStep

Probe = Callable[[int], BaseException | None]


class SpikeSearchError(RuntimeError):
    """Report retry exhaustion or protocol-invalid evidence during the spike."""


def _classify_probe(probe: Probe, value: int) -> tuple[SearchStep, TrialOutcome]:
    """Classify one probe, allowing exactly one retry for transient failures."""
    classified = classify(probe(value))
    if classified.outcome is TrialOutcome.RETRYABLE:
        classified = classify(probe(value))
        if classified.outcome is TrialOutcome.RETRYABLE:
            raise SpikeSearchError(f"n_cpu_moe={value} remained retryable after one retry")
    step = SearchStep(value, classified.outcome.value, classified.resource)
    if classified.outcome is TrialOutcome.PROTOCOL_INVALID:
        raise SpikeSearchError(f"n_cpu_moe={value} produced protocol-invalid evidence")
    return step, classified.outcome


def find_boundary(probe: Probe, budget: int = 6, maximum: int = 41) -> SearchResult:
    """Probe the prudent point, then use at most six binary boundary decisions."""
    prudent_step, prudent_outcome = _classify_probe(probe, maximum)
    steps = [prudent_step]
    if prudent_step.resource == "vram":
        return SearchResult(None, maximum, tuple(steps))
    low = 0
    high = maximum
    successful = [maximum] if prudent_outcome is TrialOutcome.SUCCESS else []
    decisions = 0
    while low < high and decisions < budget:
        value = (low + high) // 2
        step, outcome = _classify_probe(probe, value)
        steps.append(step)
        decisions += 1
        if outcome is TrialOutcome.SUCCESS:
            successful.append(value)
            high = value
        elif step.resource == "vram":
            low = value + 1
        elif step.resource == "ram":
            high = value
        else:
            raise SpikeSearchError(f"n_cpu_moe={value} has no usable memory classification")
    boundary = low if low in successful else None
    prudent = max(successful, default=maximum)
    return SearchResult(boundary, prudent, tuple(steps))
