"""Offline tests for the requested calibration preference selection policy."""

from __future__ import annotations

from bora_workbench._calibration_runner import near_tied_rival, select_envelope
from tests.sample_fixtures import sample


def test_trade_off_keeps_balanced_below_max_context() -> None:
    """When a lower context wins beyond the ceiling, balanced drops but max_context stays high."""
    samples = (
        sample(131072, 37, e2e_ms=200.0, decode_tps=30.0),
        sample(65536, 40, e2e_ms=100.0, decode_tps=50.0),
    )
    assert select_envelope(samples, "fast").ctx == 65536
    assert select_envelope(samples, "balanced").ctx == 65536
    assert select_envelope(samples, "max_context").ctx == 131072


def test_balanced_takes_max_context_when_within_ceiling() -> None:
    """Balanced keeps the largest context whose end-to-end stays within 1.10x of fast."""
    samples = (sample(131072, 37, e2e_ms=105.0), sample(65536, 40, e2e_ms=100.0))
    assert select_envelope(samples, "fast").ctx == 65536
    assert select_envelope(samples, "balanced").ctx == 131072
    assert select_envelope(samples, "max_context").ctx == 131072


def test_fast_context_floor_and_balanced_ceiling_are_inclusive() -> None:
    """Include exactly 16K for fast and exactly 1.10x latency for balanced."""
    below_floor = sample(16383, 41, e2e_ms=50.0)
    floor = sample(16384, 40, e2e_ms=100.0)
    ceiling = sample(32768, 39, e2e_ms=110.0)

    samples = (below_floor, floor, ceiling)

    assert select_envelope(samples, "fast") is floor
    assert select_envelope(samples, "balanced") is ceiling


def test_fast_and_throughput_deadbands_include_exactly_three_percent() -> None:
    """Keep exact 3% rivals eligible for confirmation in both ordering directions."""
    fast = sample(65536, 40, e2e_ms=100.0)
    fast_boundary = sample(65536, 38, e2e_ms=103.0, vram_free=2.0)
    throughput = sample(65536, 40, e2e_ms=100.0, decode_tps=100.0)
    throughput_boundary = sample(65536, 38, e2e_ms=100.0, decode_tps=97.0)

    assert near_tied_rival((fast, fast_boundary), fast, "fast") is fast_boundary
    assert (
        near_tied_rival((throughput, throughput_boundary), throughput, "balanced")
        is throughput_boundary
    )


def test_near_tied_rival_detects_and_ignores_competitors() -> None:
    """Detect a distinct deadband competitor for fast and ignore a clearly slower sample."""
    winner = sample(65536, 40, e2e_ms=100.0)
    rival = sample(65536, 38, e2e_ms=102.0, vram_free=2.0)
    slow = sample(32768, 41, e2e_ms=200.0)
    found = near_tied_rival((winner, rival, slow), winner, "fast")
    assert found is not None
    assert found.n_cpu_moe == 38
    assert near_tied_rival((winner, sample(65536, 38, e2e_ms=130.0)), winner, "fast") is None
