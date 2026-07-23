"""Test doctor presentation of local calibration record lifecycle states."""

import qwen_launcher._cli_doctor as doctor_cli
from qwen_launcher._calibration_reuse import RecordEvaluation


def test_doctor_distinguishes_record_lifecycle_states() -> None:
    """Present active, candidate, superseded, invalid, stale, and headroom states."""
    evaluations = {
        "active record valid": RecordEvaluation("valid", 8192, None, ()),
        "no active record": RecordEvaluation("missing", None, None, ()),
        "awaits activation": RecordEvaluation("candidate", None, None, ("pending",), "valid"),
        "superseded": RecordEvaluation("superseded", None, None, ("rerun calibrate",)),
        "stale": RecordEvaluation("incompatible", 8192, None, ("engine changed",)),
        "invalid": RecordEvaluation("invalid", None, None, ("broken JSON",)),
        "free VRAM": RecordEvaluation("insufficient-headroom", 8192, None, ("free VRAM low",)),
    }
    for expected, evaluation in evaluations.items():
        assert expected in doctor_cli._record_line("coding", evaluation)


def test_doctor_shows_calibrated_parameters_for_valid_records() -> None:
    """Expose the active record's ctx and n_cpu_moe instead of a bare valid label."""
    cuda_line = doctor_cli._record_line("coding", RecordEvaluation("valid", 98304, 12, ()))
    cpu_line = doctor_cli._record_line("coding", RecordEvaluation("valid", 8192, None, ()))

    assert "active record valid (ctx 98304, --n-cpu-moe 12)." in cuda_line
    assert "active record valid (ctx 8192)." in cpu_line
    assert "--n-cpu-moe" not in cpu_line


def test_doctor_keeps_candidate_hint_when_active_is_superseded() -> None:
    """Report the pending valid candidate even when the active record is superseded."""
    evaluation = RecordEvaluation("superseded", None, None, ("rerun calibrate",), "valid")

    line = doctor_cli._record_line("coding", evaluation)

    assert "record schema superseded: rerun calibrate" in line
    assert "Pending candidate is valid and awaits `calibrate --activate`." in line
