"""CLI tests for adaptive calibration/v2 dispatch, cancellation, and failures."""

from __future__ import annotations

from typer.testing import CliRunner

import qwen_launcher._cli_calibration_v2 as calibration_v2_cli
from qwen_launcher._calibration_v2_types import V2Outcome
from qwen_launcher.calibration import CalibrationRunError
from qwen_launcher.cli import app
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import cuda_calibration
from tests.test_calibration import cpu_target

runner = CliRunner()


def test_default_calibrate_runs_v2_and_shows_records(tmp_path, monkeypatch) -> None:
    """Run the zero-input adaptive protocol by default and present its record paths."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    outcome = V2Outcome((cuda_calibration(mode),), (tmp_path / "records" / "coding.json",))
    monkeypatch.setattr(calibration_v2_cli, "prepare_target", lambda mode_value: cpu_target())
    monkeypatch.setattr(calibration_v2_cli, "run_calibration_v2", lambda target: outcome)

    result = runner.invoke(app, ["calibrate", "--mode", "coding"], input="y\n")

    assert result.exit_code == 0
    assert "calibration/v2" in result.stdout
    assert "zero mandatory inputs" in result.stdout
    assert "ctx=131072, n_cpu_moe=38" in result.stdout
    assert "Record:" in result.stdout


def test_v2_refusal_cancels_before_any_process(monkeypatch) -> None:
    """Map a clean operator refusal of the adaptive preflight to exit code 130."""
    monkeypatch.setattr(calibration_v2_cli, "prepare_target", lambda mode_value: cpu_target())

    def forbidden(target):
        """Prove no probe process starts before explicit confirmation."""
        raise AssertionError("calibration must not start")

    monkeypatch.setattr(calibration_v2_cli, "run_calibration_v2", forbidden)

    result = runner.invoke(app, ["calibrate", "--mode", "coding"], input="n\n")

    assert result.exit_code == 130
    assert "cancelled" in result.output


def test_explicit_candidates_require_the_v1_protocol() -> None:
    """Keep manual candidate lists out of the adaptive zero-input protocol."""
    result = runner.invoke(app, ["calibrate", "--mode", "coding", "--candidate", "safe:8192"])

    assert result.exit_code == 2
    assert "--protocol v1" in result.output


def test_v2_runtime_failure_is_operational_exit_one(monkeypatch) -> None:
    """Map a failed measured search to code 1 rather than an input error."""
    monkeypatch.setattr(calibration_v2_cli, "prepare_target", lambda mode_value: cpu_target())
    failure = CalibrationRunError("no finalist passed confirmation")
    monkeypatch.setattr(
        calibration_v2_cli,
        "run_calibration_v2",
        lambda target: (_ for _ in ()).throw(failure),
    )

    result = runner.invoke(app, ["calibrate", "--mode", "coding"], input="y\n")

    assert result.exit_code == 1
    assert "Calibration error" in result.stderr
    assert "Traceback" not in result.output
