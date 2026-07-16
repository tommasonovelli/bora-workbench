"""Offline calibration input, ordering, selection, and isolated-trial tests."""

from __future__ import annotations

from pathlib import Path

import pytest

import qwen_launcher._calibration_process as calibration_process
import qwen_launcher._calibration_runner as runner
from qwen_launcher._calibration_process import StartFailure
from qwen_launcher._calibration_types import CandidateTrial, select_candidate
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationSettings,
    CalibrationTarget,
    Candidate,
    parse_candidate,
    validate_settings,
)
from qwen_launcher.config import Config
from qwen_launcher.engine import load_engine_lock
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.process import ProcessError
from qwen_launcher.profiles import TokenRate, load_catalog
from qwen_launcher.resources import resource


def cpu_target(mode_ids: tuple[str, ...] = ("coding",)) -> CalibrationTarget:
    """Build a verified-artifact-shaped CPU target without host or process probes."""
    catalog = load_catalog()
    modes = tuple(mode for mode in catalog.modes if mode.id in mode_ids)
    hardware = HardwareInfo("linux", "test", "CPU", 12, 32, 24, "cpu", 0, None, None, None, None)
    return CalibrationTarget(
        Config(),
        hardware,
        catalog,
        modes,
        load_engine_lock(),
        Path("/engine/llama-server"),
        Path("/models/model.gguf"),
        Path("/models/mmproj.gguf"),
    )


def benchmark(rate: float) -> BenchmarkResult:
    """Build one complete benchmark result with a selected median rate."""
    values = (rate, rate, rate, rate, rate)
    return BenchmarkResult(rate, values, TokenRate(rate, rate, rate))


def test_step_5a_has_no_packaged_policy_and_requires_explicit_values() -> None:
    """Keep policy absent and reject any attempt to calibrate from author-memory defaults."""
    assert not resource("content/calibration-policy.json").is_file()
    with pytest.raises(CalibrationError, match="explicit candidate"):
        validate_settings(CalibrationSettings((), 0, None), "cuda")


def test_candidate_syntax_is_backend_specific_and_preserves_order() -> None:
    """Parse explicit CUDA and CPU envelopes without adding hidden n_cpu_moe values."""
    cuda = tuple(parse_candidate(value, "cuda") for value in ("safe:8192:48", "fast:8192:32"))
    cpu = parse_candidate("safe:8192", "cpu")

    assert [candidate.id for candidate in cuda] == ["safe", "fast"]
    assert [candidate.n_cpu_moe for candidate in cuda] == [48, 32]
    assert cpu.n_cpu_moe is None
    with pytest.raises(CalibrationError, match="syntax"):
        parse_candidate("unsafe:8192", "cuda")


def test_selection_uses_median_then_free_vram_then_declared_order() -> None:
    """Apply all three deterministic selection keys without assuming monotonic candidates."""
    candidates = (Candidate("first", 8192, 48), Candidate("second", 8192, 32))
    trials = (
        CandidateTrial(
            candidates[0], "valid", None, 2, benchmark(10), VramSummary(1, 7, 1, "x"), ()
        ),
        CandidateTrial(
            candidates[1], "valid", None, 2, benchmark(10), VramSummary(1, 6, 2, "x"), ()
        ),
    )
    assert select_candidate(trials) == "second"

    equal_free = trials[1].__class__(
        candidates[1], "valid", None, 2, benchmark(10), VramSummary(1, 7, 1, "x"), ()
    )
    assert select_candidate((trials[0], equal_free)) == "first"


def test_modes_and_candidates_use_distinct_fresh_process_roots(tmp_path, monkeypatch) -> None:
    """Run every mode/candidate in declared order with a distinct root for every stable start."""
    target = cpu_target(("coding", "studio", "vstudio"))
    settings = CalibrationSettings(
        (Candidate("safe", 8192, None), Candidate("fast", 16384, None)), 2, None
    )
    roots: list[Path] = []

    def fake_start(target_value, settings_value, spec):
        """Record isolation and return benchmark evidence only on each final start."""
        del target_value, settings_value
        roots.append(spec.root)
        log = spec.root / "logs/server.log"
        log.parent.mkdir(parents=True)
        log.write_text("safe log", encoding="utf-8")
        return (benchmark(float(spec.plan.ctx)) if spec.is_final else None, None)

    monkeypatch.setattr(runner, "run_start", fake_start)
    result = runner.run_trials(target, settings, tmp_path)

    assert len(roots) == 12
    assert len(set(roots)) == 12
    assert [mode.mode.id for mode in result.modes] == ["coding", "studio", "vstudio"]
    assert all(mode.proposed_candidate_id == "fast" for mode in result.modes)


@pytest.mark.parametrize("message", ["CUDA out of memory", "health timeout", "process crashed"])
def test_candidate_failure_is_discarded_and_next_candidate_runs(
    tmp_path, monkeypatch, message
) -> None:
    """Retain OOM/crash/timeout diagnosis without contaminating the following candidate."""
    target = cpu_target()
    settings = CalibrationSettings(
        (Candidate("bad", 8192, None), Candidate("good", 16384, None)), 1, None
    )

    def fake_start(target_value, settings_value, spec):
        """Fail the first context and complete the second with exact benchmark evidence."""
        del target_value, settings_value
        if spec.plan.ctx == 8192:
            raise StartFailure(ProcessError(message), None)
        return benchmark(20), None

    monkeypatch.setattr(runner, "run_start", fake_start)
    result = runner.run_trials(target, settings, tmp_path)

    first, second = result.modes[0].candidates
    assert first.outcome == "discarded"
    assert ("OOM" in first.discard_reason) is ("memory" in message)
    assert second.outcome == "valid"
    assert result.modes[0].proposed_candidate_id == "good"


@pytest.mark.parametrize(
    ("mode_id", "vision_calls"), [("coding", 0), ("studio", 0), ("vstudio", 1)]
)
def test_each_mode_runs_text_benchmark_and_vstudio_adds_vision(
    mode_id, vision_calls, monkeypatch
) -> None:
    """Exercise the verified text load for every mode and the image load only for vstudio."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    calls = {"benchmark": 0, "vision": 0}

    def fake_benchmark(base_url):
        """Record the final benchmark request without opening a network connection."""
        assert base_url == "http://127.0.0.1:8080"
        calls["benchmark"] += 1
        return benchmark(10)

    def fake_vision(base_url):
        """Record the verified image workload without opening a network connection."""
        assert base_url == "http://127.0.0.1:8080"
        calls["vision"] += 1

    monkeypatch.setattr(calibration_process, "run_benchmark", fake_benchmark)
    monkeypatch.setattr(calibration_process, "run_vision_probe", fake_vision)
    result = calibration_process._workload(mode, "http://127.0.0.1:8080", True)

    assert result is not None
    assert calls == {"benchmark": 1, "vision": vision_calls}


def test_keyboard_interrupt_stops_without_generating_partial_trials(tmp_path, monkeypatch) -> None:
    """Propagate interruption so the workspace owner can remove transient process evidence."""
    target = cpu_target()
    settings = CalibrationSettings((Candidate("safe", 8192, None),), 1, None)

    def interrupted(*args):
        """Simulate Ctrl-C from an active candidate process."""
        del args
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_start", interrupted)
    with pytest.raises(KeyboardInterrupt):
        runner.run_trials(target, settings, tmp_path)
