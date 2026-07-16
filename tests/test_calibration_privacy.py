"""Calibration document redaction and bundle privacy-scanner regression tests."""

from __future__ import annotations

import getpass
import json
import socket
from dataclasses import replace

import pytest

import qwen_launcher._calibration_runner as runner
from qwen_launcher._calibration_bundle import _write_manifest
from qwen_launcher._calibration_types import CandidateTrial, ModeTrials, TrialResult
from qwen_launcher._calibration_validation import validate_bundle
from qwen_launcher.calibration import CalibrationSettings, Candidate, run_calibration
from tests.test_calibration_bundle import target


def discarded_trial(runtime, selected_target) -> TrialResult:
    """Build one discarded trial whose reason and log contain private host values."""
    log = runtime / "coding/safe/start-1/logs/server.log"
    log.parent.mkdir(parents=True)
    private = f"{selected_target.model_path} {getpass.getuser()} {socket.gethostname()}"
    log.write_text(private + "\n", encoding="utf-8")
    candidate = Candidate("safe", 8192, None)
    reason = f"startup failed; inspect {log}; host evidence: {private}"
    trial = CandidateTrial(candidate, "discarded", reason, 0, None, None, (log,))
    mode = ModeTrials(selected_target.modes[0], (trial,), None)
    return TrialResult((mode,), None)


def test_report_uses_relative_log_reason_and_redacts_every_json(tmp_path, monkeypatch) -> None:
    """Keep discard diagnostics useful while removing paths and identity from all documents."""
    selected_target = target()
    private_hardware = replace(selected_target.hardware, cpu_name=str(selected_target.model_path))
    selected_target = replace(selected_target, hardware=private_hardware)
    settings = CalibrationSettings((Candidate("safe", 8192, None),), 1, None, None)
    monkeypatch.setattr(
        runner,
        "run_trials",
        lambda target_value, settings_value, runtime: discarded_trial(runtime, target_value),
    )

    outcome = run_calibration(selected_target, settings, tmp_path)
    report_path = outcome.bundle_path / f"{outcome.report_id}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    reason = report["modes"]["coding"]["candidates"][0]["discard_reason"]
    json_text = "".join(path.read_text() for path in outcome.bundle_path.glob("*.json"))

    assert "logs/coding/safe/run-1.log" in reason
    assert str(selected_target.model_path) not in json_text
    assert getpass.getuser() not in json_text
    assert socket.gethostname() not in json_text
    assert validate_bundle(outcome.bundle_path).errors == ()


def test_fallback_log_is_redacted_without_leaving_raw_copy(tmp_path, monkeypatch) -> None:
    """Write only the sanitized fallback log when no process log survived startup."""
    selected_target = target()
    candidate = Candidate("safe", 8192, None)
    reason = f"failed before logging at {selected_target.model_path}"
    trial = CandidateTrial(candidate, "discarded", reason, 0, None, None, ())
    result = TrialResult((ModeTrials(selected_target.modes[0], (trial,), None),), None)
    monkeypatch.setattr(runner, "run_trials", lambda *args: result)
    settings = CalibrationSettings((candidate,), 1, None, None)

    outcome = run_calibration(selected_target, settings, tmp_path)
    logs = list(outcome.bundle_path.glob("logs/**/*.log"))

    assert [path.name for path in logs] == ["run-1.log"]
    assert str(selected_target.model_path) not in logs[0].read_text()
    assert "<redacted>" in logs[0].read_text()


@pytest.mark.parametrize(
    "private_path", ["/home/alice/private/model.gguf", r"C:\Users\Alice\model.gguf"]
)
def test_validate_rejects_private_absolute_path_patterns(
    private_path, tmp_path, monkeypatch
) -> None:
    """Reject POSIX and Windows private paths even in an otherwise valid foreign bundle."""
    selected_target = target()
    settings = CalibrationSettings((Candidate("safe", 8192, None),), 1, None, None)
    monkeypatch.setattr(
        runner,
        "run_trials",
        lambda target_value, settings_value, runtime: discarded_trial(runtime, target_value),
    )
    outcome = run_calibration(selected_target, settings, tmp_path)
    proposal_path = outcome.bundle_path / "profile-proposal.json"
    proposal = json.loads(proposal_path.read_text())
    proposal["next_step"] = f"inspect {private_path}"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    _write_manifest(outcome.bundle_path)

    result = validate_bundle(outcome.bundle_path)

    assert any("private absolute path" in issue.message for issue in result.errors)
