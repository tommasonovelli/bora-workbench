"""Offline calibration/v3 orchestration tests with fake processes and paired evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

import qwen_launcher._calibration_v3_confirm as confirm_module
import qwen_launcher._calibration_v3_mode as mode_module
import qwen_launcher._calibration_v3_runner as runner_module
import qwen_launcher._calibration_v3_screening as screening_module
from qwen_launcher._calibration_gpu_contexts import GpuContextBaseline
from qwen_launcher._calibration_ram import RamReserveError, RamSummary
from qwen_launcher._calibration_record import load_record
from qwen_launcher._calibration_v3_process import TrialFailure, TrialMeasurement
from qwen_launcher._calibration_v3_runner import run_calibration_v3
from qwen_launcher._calibration_v3_types import TrialEvidence, V3RunOptions
from qwen_launcher._calibration_vram import VramEnvironmentError, VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.calibration import CalibrationError
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.process import ProcessError
from qwen_launcher.profiles import TokenRate
from tests.test_calibration import cpu_target

_START = "2026-07-18T10:00:00Z"
_END = "2026-07-18T10:01:00Z"


def cuda_target(mode_ids: tuple[str, ...] = ("coding",)):
    """Build a verified-artifact-shaped CUDA target without host probes."""
    hardware = HardwareInfo("linux", "test", "CPU", 12, 32, 24, "cuda", 1, 0, "GPU", 8, 7)
    return replace(cpu_target(mode_ids), hardware=hardware)


def benchmark(rate: float) -> BenchmarkResult:
    """Build one complete benchmark result with a constant measured rate."""
    values = (rate, rate, rate, rate, rate)
    return BenchmarkResult(rate, values, TokenRate(rate, rate, rate))


def fake_trial(is_feasible, driver: str = "test-driver", baseline: float = 0.5):
    """Build a deterministic run_trial fake with monotone VRAM and fixed RAM."""

    def run(target, spec):
        """Simulate one fresh trial and preserve its supplied deterministic order."""
        moe = spec.plan.n_cpu_moe
        ram = RamSummary(24.0, 20.0)
        vram = None
        if target.hardware.backend == "cuda":
            peak = 7.5 - 0.05 * (moe or 0)
            vram = VramSummary(baseline, peak, 8 - peak, baseline, driver)
        measured = benchmark(100.0 - (moe or 0)) if spec.with_benchmark else None
        evidence = TrialEvidence(spec.order, _START, _END, measured, vram, ram, None)
        if not is_feasible(spec):
            raise TrialFailure(ProcessError("CUDA out of memory"), evidence)
        return TrialMeasurement(measured, vram, ram, evidence)

    return run


def install_fakes(monkeypatch, run, block_count: int = 41) -> None:
    """Install one trial fake for screening and confirmation plus the legal domain."""
    monkeypatch.setattr(screening_module, "run_trial", run)
    monkeypatch.setattr(confirm_module, "run_trial", run)
    monkeypatch.setattr(mode_module, "read_block_count", lambda path: block_count)
    monkeypatch.setattr(
        runner_module, "capture_gpu_context_baseline", lambda index: GpuContextBaseline(True, ())
    )


def active_record(root):
    """Load the active coding record from one isolated calibration root."""
    return load_record(root / "records" / "coding.json")


def test_cuda_search_runs_abba_and_activates_a_valid_record(tmp_path, monkeypatch) -> None:
    """Screen, benchmark all four ABBA starts, select dominance, and activate."""
    install_fakes(monkeypatch, fake_trial(lambda spec: (spec.plan.n_cpu_moe or 0) >= 38))

    outcome = run_calibration_v3(cuda_target(), destination_root=tmp_path)

    record = active_record(tmp_path)
    assert record["envelope"] == {"ctx": 131072, "n_cpu_moe": 38}
    assert record["selection_rule"] == "dominance-unanimous-rounds"
    finalists = record["search"]["finalists"]
    assert [session["global_position"] for session in finalists[0]["sessions"]] == [1, 4]
    assert [session["global_position"] for session in finalists[1]["sessions"]] == [2, 3]
    assert all(session["benchmark"] for item in finalists for session in item["sessions"])
    assert outcome.active_paths == (tmp_path / "records" / "coding.json",)
    assert outcome.evidence_path.is_dir()


def test_no_activate_retains_candidate_and_prior_active(tmp_path, monkeypatch) -> None:
    """Keep Gate evidence pending until an explicit promotion without changing active state."""
    install_fakes(monkeypatch, fake_trial(lambda spec: (spec.plan.n_cpu_moe or 0) >= 38))
    run_calibration_v3(cuda_target(), destination_root=tmp_path)

    outcome = run_calibration_v3(
        cuda_target(), V3RunOptions(is_activate=False), destination_root=tmp_path
    )

    assert (tmp_path / "records" / "coding.json").is_file()
    assert (tmp_path / "records" / "coding.candidate.json").is_file()
    assert outcome.active_paths == ()
    assert len(list((tmp_path / "evidence").iterdir())) == 1


def test_context_descends_or_obeys_an_expert_target(tmp_path, monkeypatch) -> None:
    """Descend by default while an explicit target fixes one comparable context."""

    def is_feasible(spec) -> bool:
        """Make the top context infeasible and the next context feasible at the boundary."""
        return spec.plan.ctx <= 65536 and (spec.plan.n_cpu_moe or 0) >= 38

    install_fakes(monkeypatch, fake_trial(is_feasible))
    run_calibration_v3(cuda_target(), destination_root=tmp_path)
    assert active_record(tmp_path)["envelope"]["ctx"] == 65536

    with pytest.raises(CalibrationError, match="requested context"):
        run_calibration_v3(
            cuda_target(), V3RunOptions(target_ctx=131072), destination_root=tmp_path / "fixed"
        )


def test_expert_target_between_automatic_rungs_stays_fixed(tmp_path, monkeypatch) -> None:
    """Allow 96k explicitly without changing the automatic context scale."""
    install_fakes(monkeypatch, fake_trial(lambda spec: True))
    run_calibration_v3(cuda_target(), V3RunOptions(target_ctx=98304), destination_root=tmp_path)
    record = active_record(tmp_path)
    assert record["envelope"]["ctx"] == record["search"]["target_ctx"] == 98304
    assert record["search"]["context_scale"] == [131072, 65536, 32768, 16384, 8192]


def test_cpu_confirms_two_benchmarked_baseline_rounds(tmp_path, monkeypatch) -> None:
    """Record two CPU benchmark sessions without pretending to search an axis."""
    install_fakes(monkeypatch, fake_trial(lambda spec: True))

    run_calibration_v3(cpu_target(), destination_root=tmp_path)

    record = active_record(tmp_path)
    assert record["selection_rule"] == "cpu-baseline-confirmation"
    assert record["search"]["probes"] == []
    assert len(record["benchmark"]["measured_tok_s"]) == 10


def test_baseline_drift_degrades_selection_instead_of_discarding(tmp_path, monkeypatch) -> None:
    """Preserve both finalists but suppress dominance after aggregate baseline drift."""
    calls = 0

    def run(target, spec):
        """Vary confirmation baselines beyond tolerance while leaving reserves valid."""
        nonlocal calls
        calls += 1
        baseline = 0.5 if calls % 2 else 0.8
        return fake_trial(lambda item: True, baseline=baseline)(target, spec)

    install_fakes(monkeypatch, run)
    run_calibration_v3(cuda_target(), destination_root=tmp_path)

    record = active_record(tmp_path)
    assert record["selection_rule"] == "equivalent-after-baseline-drift"
    assert record["search"]["baseline_drift_gib"] == pytest.approx(0.3)


def test_ram_reserve_violation_makes_a_probe_infeasible(tmp_path, monkeypatch) -> None:
    """Treat a low available-RAM measurement as candidate failure rather than invalid monitor."""

    def run(target, spec):
        """Fail every process with retained evidence below the universal reserve."""
        ram = RamSummary(24.0, 1.5)
        vram = VramSummary(0.5, 5.0, 3.0, 0.5, "test-driver")
        evidence = TrialEvidence(spec.order, _START, _END, None, vram, ram, None)
        raise TrialFailure(RamReserveError(ram), evidence)

    install_fakes(monkeypatch, run)
    with pytest.raises(CalibrationError, match="no feasible envelope"):
        run_calibration_v3(cuda_target(), destination_root=tmp_path)


def test_discarded_finalists_and_environment_errors_fail_honestly(tmp_path, monkeypatch) -> None:
    """Keep baseline active after confirmation failure or run-level contamination."""
    install_fakes(
        monkeypatch,
        fake_trial(lambda spec: not spec.root.name.startswith("final-")),
    )
    with pytest.raises(CalibrationError, match="no finalist passed"):
        run_calibration_v3(cuda_target(), destination_root=tmp_path / "discarded")

    def contaminated(target, spec):
        """Simulate a foreign GPU context reported by the monitor."""
        raise VramEnvironmentError("concurrent GPU workload")

    install_fakes(monkeypatch, contaminated)
    with pytest.raises(CalibrationError, match="run invalidated"):
        run_calibration_v3(cuda_target(), destination_root=tmp_path / "invalid")
