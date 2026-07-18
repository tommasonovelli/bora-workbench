"""Offline calibration/v2 orchestration tests with fake processes and monitors."""

from __future__ import annotations

from dataclasses import replace

import pytest

import qwen_launcher._calibration_v2_confirm as confirm_module
import qwen_launcher._calibration_v2_runner as runner_module
from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_record import load_record
from qwen_launcher._calibration_v2_process import TrialFailure, TrialMeasurement
from qwen_launcher._calibration_v2_runner import run_calibration_v2
from qwen_launcher._calibration_vram import VramEnvironmentError, VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.calibration import CalibrationError
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.process import ProcessError
from qwen_launcher.profiles import TokenRate
from tests.test_calibration import cpu_target


def cuda_target(mode_ids: tuple[str, ...] = ("coding",)):
    """Build a verified-artifact-shaped CUDA target without host or process probes."""
    hardware = HardwareInfo("linux", "test", "CPU", 12, 32, 24, "cuda", 1, 0, "GPU", 8, 7)
    return replace(cpu_target(mode_ids), hardware=hardware)


def benchmark(rate: float) -> BenchmarkResult:
    """Build one complete benchmark result with a constant measured rate."""
    values = (rate, rate, rate, rate, rate)
    return BenchmarkResult(rate, values, TokenRate(rate, rate, rate))


def fake_trial(is_feasible, driver: str = "test-driver"):
    """Build a deterministic run_trial fake with monotone VRAM and fixed RAM evidence."""

    def run(target, spec):
        """Simulate one fresh trial for the requested envelope."""
        moe = spec.plan.n_cpu_moe
        ram = RamSummary(24.0, 20.0)
        vram = None
        if target.hardware.backend == "cuda":
            peak = 7.5 - 0.05 * (moe or 0)
            vram = VramSummary(0.5, peak, 8 - peak, 0.5, driver)
        if not is_feasible(spec):
            raise TrialFailure(ProcessError("CUDA out of memory"), (vram, ram))
        measured = benchmark(100.0 - (moe or 0)) if spec.with_benchmark else None
        return TrialMeasurement(measured, vram, ram)

    return run


def install_fakes(monkeypatch, run, block_count: int = 41) -> None:
    """Install one run_trial fake for screening and confirmation plus the domain."""
    monkeypatch.setattr(runner_module, "run_trial", run)
    monkeypatch.setattr(confirm_module, "run_trial", run)
    monkeypatch.setattr(runner_module, "read_block_count", lambda path: block_count)


def test_cuda_search_selects_the_boundary_and_writes_a_valid_record(tmp_path, monkeypatch) -> None:
    """Screen to the boundary, confirm both finalists, select by dominance, and record."""
    install_fakes(monkeypatch, fake_trial(lambda spec: (spec.plan.n_cpu_moe or 0) >= 38))

    outcome = run_calibration_v2(cuda_target(), tmp_path)

    record = load_record(tmp_path / "records" / "coding.json")
    assert record["envelope"] == {"ctx": 131072, "n_cpu_moe": 38}
    assert record["selection_rule"] == "dominance-median-over-maximum"
    assert record["backend"] == "cuda"
    calibration = outcome.calibrations[0]
    assert [finalist.n_cpu_moe for finalist in calibration.finalists] == [38, 39]
    assert len(calibration.probes) <= 12
    assert not list(tmp_path.glob(".runtime-*"))


def test_context_descends_only_when_the_most_prudent_envelope_is_infeasible(
    tmp_path, monkeypatch
) -> None:
    """Keep comparisons at one context and record the context actually reached."""

    def is_feasible(spec) -> bool:
        """Make the whole domain infeasible at the top context only."""
        return spec.plan.ctx <= 65536 and (spec.plan.n_cpu_moe or 0) >= 38

    install_fakes(monkeypatch, fake_trial(is_feasible))

    run_calibration_v2(cuda_target(), tmp_path)

    record = load_record(tmp_path / "records" / "coding.json")
    assert record["envelope"] == {"ctx": 65536, "n_cpu_moe": 38}
    probes = record["search"]["probes"]
    assert probes[0]["ctx"] == 131072 and probes[0]["is_feasible"] is False
    assert "OOM" in probes[0]["reason"]


def test_cpu_backend_confirms_the_baseline_without_a_fake_search(tmp_path, monkeypatch) -> None:
    """Record the CPU baseline as confirmed, never as a launcher-produced optimum."""
    install_fakes(monkeypatch, fake_trial(lambda spec: True))

    outcome = run_calibration_v2(cpu_target(), tmp_path)

    record = load_record(tmp_path / "records" / "coding.json")
    assert record["backend"] == "cpu"
    assert record["selection_rule"] == "cpu-baseline-confirmation"
    assert record["envelope"] == {"ctx": 8192, "n_cpu_moe": None}
    assert record["search"]["probes"] == []
    assert outcome.calibrations[0].probes == ()


def test_all_discarded_finalists_keep_the_baseline_active(tmp_path, monkeypatch) -> None:
    """Fail honestly instead of recording an envelope no finalist confirmed."""

    def is_feasible(spec) -> bool:
        """Pass screening but fail every confirmation start."""
        return not spec.root.name.startswith("final-")

    install_fakes(monkeypatch, fake_trial(is_feasible))

    with pytest.raises(CalibrationError, match="no finalist passed confirmation"):
        run_calibration_v2(cuda_target(), tmp_path)
    assert not (tmp_path / "records" / "coding.json").exists()


def test_no_feasible_context_is_an_actionable_error(tmp_path, monkeypatch) -> None:
    """Exhaust the approved context scale without inventing a smaller domain."""
    install_fakes(monkeypatch, fake_trial(lambda spec: False))

    with pytest.raises(CalibrationError, match="no feasible envelope"):
        run_calibration_v2(cuda_target(), tmp_path)


def test_driver_change_invalidates_the_whole_run(tmp_path, monkeypatch) -> None:
    """Treat a driver change during calibration as environmental invalidation."""
    drivers = iter(f"driver-{index}" for index in range(100))

    def run(target, spec):
        """Serve each trial under a different reported driver version."""
        return fake_trial(lambda _spec: True, driver=next(drivers))(target, spec)

    monkeypatch.setattr(runner_module, "run_trial", run)
    monkeypatch.setattr(confirm_module, "run_trial", run)
    monkeypatch.setattr(runner_module, "read_block_count", lambda path: 41)

    with pytest.raises(CalibrationError, match="driver version changed"):
        run_calibration_v2(cuda_target(), tmp_path)


def test_environment_error_invalidates_the_run_with_context(tmp_path, monkeypatch) -> None:
    """Map contaminated monitoring to one actionable run-level calibration error."""

    def run(target, spec):
        """Simulate a foreign compute workload detected by the monitor."""
        raise VramEnvironmentError("concurrent GPU compute workload contaminated calibration")

    monkeypatch.setattr(runner_module, "run_trial", run)
    monkeypatch.setattr(confirm_module, "run_trial", run)
    monkeypatch.setattr(runner_module, "read_block_count", lambda path: 41)

    with pytest.raises(CalibrationError, match="calibration run invalidated"):
        run_calibration_v2(cuda_target(), tmp_path)
