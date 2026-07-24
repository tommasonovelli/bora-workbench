"""Select the fast, balanced, and max_context envelopes without Pareto search (spec 1.2, 3.4).

Every rule is a pure function of the measured samples so the choice can be reconstructed from the
record. Confirmation between two near-tied finalists lives in ``_calibration_v6_confirm``.
"""

from __future__ import annotations

from qwen_launcher._calibration_v6_types import (
    BALANCED_CEILING,
    DEADBAND_PCT,
    MIN_CTX_FAST,
    Preference,
    V6Sample,
)


def _free_vram(sample: V6Sample) -> float:
    """Return comparable minimum free VRAM, treating an absent value as the least margin."""
    return -1.0 if sample.vram_min_free_gib is None else sample.vram_min_free_gib


def _within_deadband(value: float, best: float) -> bool:
    """Return whether one smaller-is-better value stays inside the material-improvement band."""
    return value <= best * (1 + DEADBAND_PCT / 100)


def _throughput_key(sample: V6Sample) -> tuple[float, float, int]:
    """Order samples by the v5 semantics: throughput, then VRAM margin, then prudence."""
    return (sample.decode_tps, _free_vram(sample), sample.n_cpu_moe)


def _fast_key(sample: V6Sample) -> tuple[float, float, int]:
    """Break a fast deadband tie by prefill, then VRAM margin, then prudence."""
    return (sample.prefill_tps, _free_vram(sample), sample.n_cpu_moe)


def select_fast(samples: tuple[V6Sample, ...]) -> V6Sample:
    """Return the minimum median short end-to-end sample at or above the fast context floor."""
    eligible = tuple(sample for sample in samples if sample.ctx >= MIN_CTX_FAST) or samples
    best_e2e = min(sample.e2e_ms for sample in eligible)
    contenders = tuple(sample for sample in eligible if _within_deadband(sample.e2e_ms, best_e2e))
    return max(contenders, key=_fast_key)


def select_balanced(samples: tuple[V6Sample, ...], fast: V6Sample) -> V6Sample:
    """Return the largest context whose short end-to-end stays within the balanced ceiling."""
    ceiling = fast.e2e_ms * BALANCED_CEILING
    eligible = tuple(sample for sample in samples if sample.e2e_ms <= ceiling) or (fast,)
    max_ctx = max(sample.ctx for sample in eligible)
    return max((s for s in eligible if s.ctx == max_ctx), key=_throughput_key)


def select_max_context(samples: tuple[V6Sample, ...]) -> V6Sample:
    """Return the maximum feasible context, ordered by v5 throughput semantics within it."""
    max_ctx = max(sample.ctx for sample in samples)
    return max((s for s in samples if s.ctx == max_ctx), key=_throughput_key)


def select_envelopes(samples: tuple[V6Sample, ...]) -> dict[Preference, V6Sample]:
    """Select all three preference envelopes from one shared set of feasible samples."""
    if not samples:
        raise ValueError("cannot select envelopes without any feasible sample")
    fast = select_fast(samples)
    return {
        "fast": fast,
        "balanced": select_balanced(samples, fast),
        "max_context": select_max_context(samples),
    }


def _fast_rivals(samples: tuple[V6Sample, ...], winner: V6Sample) -> tuple[V6Sample, ...]:
    """Return fast contenders whose short end-to-end stays within the winner's deadband."""
    pool = tuple(sample for sample in samples if sample.ctx >= MIN_CTX_FAST) or samples
    return tuple(sample for sample in pool if _within_deadband(sample.e2e_ms, winner.e2e_ms))


def _throughput_rivals(samples: tuple[V6Sample, ...], winner: V6Sample) -> tuple[V6Sample, ...]:
    """Return same-context contenders whose decode throughput ties the winner within deadband."""
    floor = winner.decode_tps * (1 - DEADBAND_PCT / 100)
    return tuple(s for s in samples if s.ctx == winner.ctx and s.decode_tps >= floor)


def near_tied_rival(
    samples: tuple[V6Sample, ...], winner: V6Sample, preference: Preference
) -> V6Sample | None:
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
