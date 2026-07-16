"""Candidate-level VRAM baseline drift tests with explicit release tolerance."""

from __future__ import annotations

from dataclasses import replace

import pytest

import qwen_launcher._calibration_runner as runner
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationSettings,
    Candidate,
    validate_settings,
)
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import TokenRate
from tests.test_calibration import cpu_target


def measured() -> BenchmarkResult:
    """Build one complete benchmark result for the final stable start."""
    values = (10.0, 10.0, 10.0, 10.0, 10.0)
    return BenchmarkResult(10, values, TokenRate(10, 10, 10))


def cuda_target():
    """Build a single-GPU CUDA target without probing host hardware."""
    hardware = HardwareInfo("linux", "test", "CPU", 12, 32, 24, "cuda", 1, 0, "GPU", 8, 7)
    return replace(cpu_target(), hardware=hardware)


def test_settings_require_tolerance_only_for_cuda() -> None:
    """Reject omitted, negative, or CPU-only release tolerance before process startup."""
    candidate = Candidate("safe", 8192, 48)
    with pytest.raises(CalibrationError, match="tolerance"):
        validate_settings(CalibrationSettings((candidate,), 1, 1, None), "cuda")
    with pytest.raises(CalibrationError, match="tolerance"):
        validate_settings(CalibrationSettings((candidate,), 1, 1, -0.1), "cuda")
    with pytest.raises(CalibrationError, match="forbidden"):
        cpu = Candidate("safe", 8192, None)
        validate_settings(CalibrationSettings((cpu,), 1, None, 0), "cpu")


@pytest.mark.parametrize(("second_baseline", "outcome"), [(1.1, "valid"), (1.2, "discarded")])
def test_baseline_drift_is_candidate_level(second_baseline, outcome, tmp_path, monkeypatch) -> None:
    """Accept drift within tolerance and discard, rather than abort, drift beyond it."""
    target = cuda_target()
    candidate = Candidate("safe", 8192, 48)
    settings = CalibrationSettings((candidate,), 2, 1, 0.125)
    summaries = iter(
        (
            VramSummary(1, 6, 2, 1, "610.47"),
            VramSummary(second_baseline, 6, 2, second_baseline, "610.47"),
        )
    )

    def fake_start(target_value, settings_value, spec):
        """Return distinct stable-start baselines and benchmark only on the final start."""
        del target_value, settings_value
        return (measured() if spec.is_final else None, next(summaries))

    monkeypatch.setattr(runner, "run_start", fake_start)
    result = runner.run_trials(target, settings, tmp_path)
    trial = result.modes[0].candidates[0]

    assert trial.outcome == outcome
    if outcome == "discarded":
        assert "drift exceeded" in (trial.discard_reason or "")
        assert result.modes[0].proposed_candidate_id is None
