"""Offline tests for the ABBA third-round rule and resolution."""

from __future__ import annotations

from bora_workbench._calibration_confirm import RoundResult, needs_third_round, resolve
from tests.sample_fixtures import sample

_QUIET = (0.02, 0.02)


def test_third_round_triggers_on_discordant_winners() -> None:
    """Re-measure when the two rounds pick different decisive winners."""
    rounds = (RoundResult((100.0, 110.0), _QUIET), RoundResult((110.0, 100.0), _QUIET))
    assert needs_third_round(rounds)


def test_third_round_triggers_on_sub_deadband_gap() -> None:
    """Re-measure when the aggregate gap is below 1.5x the deadband."""
    rounds = (RoundResult((100.0, 102.0), _QUIET), RoundResult((100.0, 102.0), _QUIET))
    assert needs_third_round(rounds)


def test_third_round_triggers_on_noisy_round() -> None:
    """Re-measure when either finalist's intra-round dispersion exceeds ten percent."""
    rounds = (RoundResult((100.0, 120.0), (0.2, 0.02)), RoundResult((100.0, 120.0), _QUIET))
    assert needs_third_round(rounds)


def test_third_round_does_not_trigger_when_clear_and_quiet() -> None:
    """Accept a stable, decisive two-round result without a third round."""
    rounds = (RoundResult((100.0, 120.0), _QUIET), RoundResult((100.0, 120.0), _QUIET))
    assert not needs_third_round(rounds)


def test_resolve_uses_majority_then_material_equivalence() -> None:
    """Resolve by decisive-round majority, then by VRAM margin when the rounds tie."""
    first = sample(65536, 40, 100.0, vram_free=1.0)
    second = sample(65536, 38, 100.0, vram_free=2.0)
    decisive = (
        RoundResult((100.0, 120.0), _QUIET),
        RoundResult((100.0, 120.0), _QUIET),
        RoundResult((120.0, 100.0), _QUIET),
    )
    assert resolve(decisive, (first, second)) == 0
    tie = (RoundResult((100.0, 100.5), _QUIET), RoundResult((100.0, 100.5), _QUIET))
    assert resolve(tie, (first, second)) == 1
