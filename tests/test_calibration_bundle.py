"""Atomic bundle, digest, privacy, and explicit-path validation tests."""

from __future__ import annotations

import getpass
import json
from dataclasses import replace
from pathlib import Path

import pytest

import qwen_launcher._calibration_runner as runner
from qwen_launcher._calibration_types import CandidateTrial, ModeTrials, TrialResult
from qwen_launcher._calibration_validation import validate_bundle
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.calibration import (
    CalibrationSettings,
    CalibrationTarget,
    Candidate,
    run_calibration,
)
from qwen_launcher.config import Config
from qwen_launcher.engine import load_engine_lock
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import TokenRate, load_catalog


def target() -> CalibrationTarget:
    """Build one privacy-sensitive CPU target without touching real hardware or artifacts."""
    catalog = load_catalog()
    mode = catalog.mode("coding")
    assert mode is not None
    hardware = HardwareInfo(
        "linux", "test", "Test CPU", 12, 32, 24, "cpu", 0, None, None, None, None
    )
    home = Path.home()
    return CalibrationTarget(
        Config(),
        hardware,
        catalog,
        (mode,),
        load_engine_lock(),
        home / "private/llama-server",
        home / "private/model.gguf",
        None,
    )


def trial(runtime: Path, selected_target: CalibrationTarget) -> TrialResult:
    """Create one complete valid trial whose source log contains private host values."""
    log = runtime / "coding/safe/start-1/logs/server.log"
    log.parent.mkdir(parents=True)
    private_line = (
        f"user={getpass.getuser()} model={selected_target.model_path} "
        f"engine={selected_target.executable}\n"
    )
    log.write_text(private_line, encoding="utf-8")
    rates = (1.0, 2.0, 3.0, 4.0, 5.0)
    measured = BenchmarkResult(0.5, rates, TokenRate(1, 3, 5))
    candidate = Candidate("safe", 8192, None)
    result = CandidateTrial(candidate, "valid", None, 1, measured, None, (log,))
    return TrialResult((ModeTrials(selected_target.modes[0], (result,), "safe"),), None)


def test_bundle_is_atomic_valid_digest_complete_and_privacy_safe(tmp_path, monkeypatch) -> None:
    """Promote only a complete bundle with redacted logs, draft report, and verified manifest."""
    selected_target = target()
    settings = CalibrationSettings((Candidate("safe", 8192, None),), 1, None)

    def fake_trials(target_value, settings_value, runtime):
        """Return deterministic evidence rooted in the workspace transient directory."""
        assert target_value is selected_target
        assert settings_value is settings
        return trial(runtime, target_value)

    monkeypatch.setattr(runner, "run_trials", fake_trials)
    outcome = run_calibration(selected_target, settings, tmp_path)

    assert outcome.bundle_path.is_dir()
    assert not list(tmp_path.glob(".*.tmp-*"))
    assert validate_bundle(outcome.bundle_path).errors == ()
    report = json.loads((outcome.bundle_path / f"{outcome.report_id}.json").read_text())
    assert report["decision"] == "draft"
    assert report["privacy_reviewed"] is False
    assert report["modes"]["coding"]["selected_candidate_id"] is None
    proposal = json.loads((outcome.bundle_path / "profile-proposal.json").read_text())
    assert proposal["status"] == "draft-not-distributable"
    assert proposal["match"] is None
    shared_logs = "".join(path.read_text() for path in outcome.bundle_path.glob("logs/**/*.log"))
    assert str(Path.home()) not in shared_logs
    assert getpass.getuser() not in shared_logs
    assert "<redacted>" in shared_logs


def test_tampered_bundle_fails_manifest_and_log_digest_validation(tmp_path, monkeypatch) -> None:
    """Detect any post-generation evidence change through both manifest and report log digests."""
    selected_target = target()
    settings = CalibrationSettings((Candidate("safe", 8192, None),), 1, None)
    monkeypatch.setattr(
        runner,
        "run_trials",
        lambda target_value, settings_value, runtime: trial(runtime, target_value),
    )
    outcome = run_calibration(selected_target, settings, tmp_path)
    log = next(outcome.bundle_path.glob("logs/**/*.log"))
    log.write_text("tampered\n", encoding="utf-8")

    result = validate_bundle(outcome.bundle_path)

    assert any("SHA-256 mismatch" in issue.message for issue in result.errors)
    assert any("log SHA-256 mismatch" in issue.message for issue in result.errors)


def test_cuda_draft_contains_non_null_gpu_and_candidate_evidence(tmp_path, monkeypatch) -> None:
    """Generate schema-valid CUDA evidence required for the first 8 GiB calibration gate."""
    selected_target = target()
    cuda = HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cuda", 1, 0, "Test GPU", 8, 7)
    selected_target = replace(selected_target, hardware=cuda)
    candidate = Candidate("safe", 8192, 48)
    settings = CalibrationSettings((candidate,), 1, 1)

    def cuda_trials(target_value, settings_value, runtime):
        """Build complete CUDA memory, driver, benchmark, and log evidence."""
        del settings_value
        log = runtime / "coding/safe/start-1/logs/server.log"
        log.parent.mkdir(parents=True)
        log.write_text("CUDA candidate complete\n", encoding="utf-8")
        measured = BenchmarkResult(1, (1, 2, 3, 4, 5), TokenRate(1, 3, 5))
        vram = VramSummary(1, 6.5, 1.5, "610.47")
        result = CandidateTrial(candidate, "valid", None, 1, measured, vram, (log,))
        return TrialResult((ModeTrials(target_value.modes[0], (result,), "safe"),), "610.47")

    monkeypatch.setattr(runner, "run_trials", cuda_trials)
    outcome = run_calibration(selected_target, settings, tmp_path)

    assert validate_bundle(outcome.bundle_path).errors == ()
    report = json.loads((outcome.bundle_path / f"{outcome.report_id}.json").read_text())
    evidence = report["modes"]["coding"]["candidates"][0]
    assert report["hardware"]["gpu_driver"] == "610.47"
    assert evidence["n_cpu_moe"] == 48
    assert evidence["vram_min_free_gib"] == 1.5


def test_interruption_removes_staging_and_never_promotes_partial_bundle(
    tmp_path, monkeypatch
) -> None:
    """Clean only transient managed evidence and leave no bundle after Ctrl-C."""
    selected_target = target()
    settings = CalibrationSettings((Candidate("safe", 8192, None),), 1, None)

    def interrupted(*args):
        """Interrupt candidate execution before document generation."""
        del args
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_trials", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_calibration(selected_target, settings, tmp_path)

    assert list(tmp_path.iterdir()) == []
