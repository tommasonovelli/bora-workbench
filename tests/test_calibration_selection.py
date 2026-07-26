"""Offline tests for envelope selection policies."""

from __future__ import annotations

from bora_workbench._calibration_runner import near_tied_rival, select_envelopes
from tests.sample_fixtures import sample


def test_trade_off_keeps_balanced_below_max_context() -> None:
    """When a lower context wins beyond the ceiling, balanced drops but max_context stays high."""
    samples = (
        sample(131072, 37, e2e_ms=200.0, decode_tps=30.0),
        sample(65536, 40, e2e_ms=100.0, decode_tps=50.0),
    )
    envelopes = select_envelopes(samples)
    assert envelopes["fast"].ctx == 65536
    assert envelopes["balanced"].ctx == 65536
    assert envelopes["max_context"].ctx == 131072


def test_balanced_takes_max_context_when_within_ceiling() -> None:
    """Balanced keeps the largest context whose end-to-end stays within 1.10x of fast."""
    samples = (sample(131072, 37, e2e_ms=105.0), sample(65536, 40, e2e_ms=100.0))
    envelopes = select_envelopes(samples)
    assert envelopes["fast"].ctx == 65536
    assert envelopes["balanced"].ctx == 131072
    assert envelopes["max_context"].ctx == 131072


def test_near_tied_rival_detects_and_ignores_competitors() -> None:
    """Detect a distinct deadband competitor for fast and ignore a clearly slower sample."""
    winner = sample(65536, 40, e2e_ms=100.0)
    rival = sample(65536, 38, e2e_ms=102.0, vram_free=2.0)
    slow = sample(32768, 41, e2e_ms=200.0)
    found = near_tied_rival((winner, rival, slow), winner, "fast")
    assert found is not None
    assert found.n_cpu_moe == 38
    assert near_tied_rival((winner, sample(65536, 38, e2e_ms=130.0)), winner, "fast") is None
