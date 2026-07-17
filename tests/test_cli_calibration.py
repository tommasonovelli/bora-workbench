"""CLI tests for explicit inputs, interactive completion, cancellation, and bundle paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import qwen_launcher._cli_calibration as calibration_cli
from qwen_launcher.calibration import CalibrationOutcome
from qwen_launcher.cli import app
from tests.test_calibration import cpu_target
from tests.test_calibration_drift import cuda_target

runner = CliRunner()


def fake_outcome(tmp_path: Path) -> CalibrationOutcome:
    """Create the two exact preview documents expected from a completed draft bundle."""
    report_id = "calibration-20260716t120000000000"
    bundle = tmp_path / report_id
    bundle.mkdir()
    (bundle / f"{report_id}.json").write_text(
        json.dumps({"decision": "draft", "privacy_reviewed": False}), encoding="utf-8"
    )
    (bundle / "profile-proposal.json").write_text(
        json.dumps({"status": "draft-not-distributable"}), encoding="utf-8"
    )
    return CalibrationOutcome(bundle, report_id, (("coding", "safe"),))


def test_explicit_policy_free_options_still_require_confirmation(tmp_path, monkeypatch) -> None:
    """Display preflight and map a clean operator refusal to exit code 130 before any trial."""
    monkeypatch.setattr(calibration_cli, "prepare_target", lambda mode: cpu_target())
    called = False

    def forbidden(*args):
        """Prove cancellation happens before candidate processes or bundle generation."""
        nonlocal called
        called = True
        raise AssertionError("calibration must not start")

    monkeypatch.setattr(calibration_cli, "run_calibration", forbidden)
    result = runner.invoke(
        app,
        [
            "calibrate",
            "--mode",
            "coding",
            "--candidate",
            "safe:8192",
            "--settings",
            "1",
        ],
        input="n\n",
    )

    assert result.exit_code == 130
    assert "potentially hours" in result.stdout
    assert "gate-only" in result.stdout
    assert "cancelled" in result.output
    assert called is False


def test_interactive_values_generate_exact_draft_preview(tmp_path, monkeypatch) -> None:
    """Collect every absent value explicitly and show generated shareable JSON without upload."""
    outcome = fake_outcome(tmp_path)
    monkeypatch.setattr(calibration_cli, "prepare_target", lambda mode: cpu_target())
    monkeypatch.setattr(calibration_cli, "run_calibration", lambda target, settings: outcome)

    result = runner.invoke(
        app,
        ["calibrate", "--mode", "coding"],
        input="safe:8192\nn\n1\ny\n",
    )

    assert result.exit_code == 0
    assert "Exact shareable preview" in result.stdout
    assert '"decision": "draft"' in result.stdout
    assert "no data was uploaded" in result.stdout


def test_cuda_settings_require_reserve_and_release_tolerance() -> None:
    """Accept only the new explicit three-part CUDA settings syntax."""
    selected_target = cuda_target()

    assert calibration_cli._explicit_settings("2:0.25:0.0625", selected_target) == (
        2,
        0.25,
        0.0625,
    )
    with pytest.raises(calibration_cli.CalibrationError, match="RELEASE_TOLERANCE_GIB"):
        calibration_cli._explicit_settings("2:0.25", selected_target)


def test_all_discarded_outcome_is_explicit(tmp_path, monkeypatch) -> None:
    """Tell the operator when a successful bundle contains no valid candidate."""
    outcome = fake_outcome(tmp_path)
    outcome = CalibrationOutcome(outcome.bundle_path, outcome.report_id, (("coding", None),))
    monkeypatch.setattr(calibration_cli, "prepare_target", lambda mode: cpu_target())
    monkeypatch.setattr(calibration_cli, "run_calibration", lambda target, settings: outcome)

    result = runner.invoke(
        app,
        ["calibrate", "--mode", "coding", "--candidate", "safe:8192", "--settings", "1"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "no valid candidate; bundle contains discards only" in result.stdout


def test_invalid_candidate_is_cli_input_error(monkeypatch) -> None:
    """Map malformed explicit candidate syntax to code 2 with no traceback."""
    monkeypatch.setattr(calibration_cli, "prepare_target", lambda mode: cpu_target())

    result = runner.invoke(
        app,
        [
            "calibrate",
            "--mode",
            "coding",
            "--candidate",
            "safe:8192:48",
            "--settings",
            "1",
        ],
    )

    assert result.exit_code == 2
    assert "Calibration input error" in result.output
    assert "Traceback" not in result.output


def test_validate_path_does_not_replace_default_resource_validation(tmp_path) -> None:
    """Dispatch an explicit bundle path independently while retaining default validate behavior."""
    invalid_bundle = tmp_path / "bundle"
    invalid_bundle.mkdir()

    explicit = runner.invoke(app, ["validate", "--path", str(invalid_bundle)])
    default = runner.invoke(app, ["validate"])

    assert explicit.exit_code == 1
    assert "exactly one report" in explicit.output
    assert default.exit_code == 0
    assert "Validation passed" in default.stdout
