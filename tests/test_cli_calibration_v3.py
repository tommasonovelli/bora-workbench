"""CLI tests for calibration/v3 dispatch, lifecycle options, cancellation, and failures."""

from __future__ import annotations

from typer.testing import CliRunner

import qwen_launcher._cli_calibration_v3 as calibration_v3_cli
import qwen_launcher._cli_doctor as doctor_cli
from qwen_launcher._calibration_record import RecordError
from qwen_launcher._calibration_reuse import RecordEvaluation
from qwen_launcher._calibration_v3_types import V3Outcome
from qwen_launcher.calibration import CalibrationRunError
from qwen_launcher.cli import app
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import cuda_calibration
from tests.test_calibration import cpu_target

runner = CliRunner()


def outcome(tmp_path) -> V3Outcome:
    """Build one complete CLI-facing outcome without real processes."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    active = tmp_path / "records" / "coding.json"
    evidence = tmp_path / "evidence" / ("a" * 32)
    return V3Outcome((cuda_calibration(mode),), (), (active,), evidence)


def test_default_calibrate_runs_v3_and_shows_active_record(tmp_path, monkeypatch) -> None:
    """Run paired zero-input protocol by default and present its active path."""
    monkeypatch.setattr(calibration_v3_cli, "prepare_target", lambda mode_value: cpu_target())
    monkeypatch.setattr(
        calibration_v3_cli, "run_calibration_v3", lambda target, options: outcome(tmp_path)
    )

    result = runner.invoke(app, ["calibrate", "--mode", "coding"], input="y\n")

    assert result.exit_code == 0
    assert "calibration/v3" in result.stdout
    assert "zero mandatory technical inputs" in result.stdout
    assert "ctx=131072, n_cpu_moe=38" in result.stdout
    assert "Active record:" in result.stdout


def test_refusal_cancels_before_any_process(monkeypatch) -> None:
    """Map a clean operator refusal to contractual exit code 130."""
    monkeypatch.setattr(calibration_v3_cli, "prepare_target", lambda mode_value: cpu_target())

    def forbidden(target, options):
        """Prove no probe starts before explicit confirmation."""
        raise AssertionError("calibration must not start")

    monkeypatch.setattr(calibration_v3_cli, "run_calibration_v3", forbidden)
    result = runner.invoke(app, ["calibrate", "--mode", "coding"], input="n\n")

    assert result.exit_code == 130
    assert "cancelled" in result.output


def test_no_activate_and_target_context_reach_runner(tmp_path, monkeypatch) -> None:
    """Pass expert controls without adding mandatory input to the default path."""
    captured = []
    monkeypatch.setattr(calibration_v3_cli, "prepare_target", lambda mode_value: cpu_target())

    def run(target, options):
        """Capture grouped core options and return a synthetic outcome."""
        captured.append(options)
        return outcome(tmp_path)

    monkeypatch.setattr(calibration_v3_cli, "run_calibration_v3", run)
    result = runner.invoke(
        app,
        ["calibrate", "--mode", "coding", "--no-activate", "--target-ctx", "32768"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert captured[0].target_ctx == 32768
    assert not captured[0].is_activate


def test_activate_promotes_without_preparing_hardware(tmp_path, monkeypatch) -> None:
    """Promote a pending candidate without rerunning model, engine, or hardware preflight."""
    active = tmp_path / "records" / "coding.json"
    monkeypatch.setattr(calibration_v3_cli, "promote_candidate", lambda mode_id: active)
    monkeypatch.setattr(
        calibration_v3_cli,
        "prepare_target",
        lambda mode: (_ for _ in ()).throw(AssertionError("must not prepare")),
    )

    result = runner.invoke(app, ["calibrate", "--mode", "coding", "--activate"])

    assert result.exit_code == 0
    assert "Activated calibration candidate" in result.stdout


def test_activate_missing_candidate_is_operational_without_traceback(monkeypatch) -> None:
    """Map an absent pending candidate to the expected operational error boundary."""
    failure = RecordError("no pending calibration candidate")
    monkeypatch.setattr(
        calibration_v3_cli,
        "promote_candidate",
        lambda mode: (_ for _ in ()).throw(failure),
    )

    result = runner.invoke(app, ["calibrate", "--mode", "coding", "--activate"])

    assert result.exit_code == 1
    assert "no pending calibration candidate" in result.stderr
    assert "Traceback" not in result.output


def test_invalid_option_combinations_and_v1_boundary() -> None:
    """Reject conflicting lifecycle controls and keep manual candidates in v1."""
    conflict = runner.invoke(app, ["calibrate", "--mode", "coding", "--activate", "--no-activate"])
    explicit = runner.invoke(app, ["calibrate", "--mode", "coding", "--candidate", "safe:8192"])

    assert conflict.exit_code == 2
    assert "mutually exclusive" in conflict.output
    assert explicit.exit_code == 2
    assert "--protocol v1" in explicit.output


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


def test_runtime_failure_is_operational_exit_one(monkeypatch) -> None:
    """Map a measured search failure to code 1 without traceback."""
    monkeypatch.setattr(calibration_v3_cli, "prepare_target", lambda mode_value: cpu_target())
    failure = CalibrationRunError("no finalist passed confirmation")
    monkeypatch.setattr(
        calibration_v3_cli,
        "run_calibration_v3",
        lambda target, options: (_ for _ in ()).throw(failure),
    )

    result = runner.invoke(app, ["calibrate", "--mode", "coding"], input="y\n")

    assert result.exit_code == 1
    assert "Calibration error" in result.stderr
    assert "Traceback" not in result.output
