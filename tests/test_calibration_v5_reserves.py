"""Offline finalist-level reserve tests for calibration/v5."""

from __future__ import annotations

from qwen_launcher._calibration_ram import RamReserveError, RamSummary
from qwen_launcher._calibration_record import load_record
from qwen_launcher._calibration_v5_process import TrialFailure
from qwen_launcher._calibration_v5_runner import run_calibration_v5
from qwen_launcher._calibration_v5_types import TrialEvidence
from qwen_launcher._calibration_vram import VramSummary
from tests.test_calibration_v5_runner import cuda_target, fake_trial, install_fakes

_START = "2026-07-18T10:00:00Z"
_END = "2026-07-18T10:01:00Z"


def test_ram_reserve_violation_discards_only_the_affected_finalist(tmp_path, monkeypatch) -> None:
    """Keep a prudent valid finalist when the aggressive confirmation violates RAM reserve."""
    feasible = fake_trial(lambda spec: (spec.plan.n_cpu_moe or 0) >= 38)

    def run(target, spec):
        """Fail n38 only during paired confirmation and retain its measured RAM evidence."""
        if spec.with_benchmark and spec.plan.n_cpu_moe == 38:
            ram = RamSummary(24.0, 1.5)
            vram = VramSummary(0.5, 5.6, 2.4, 0.5, "test-driver")
            evidence = TrialEvidence(spec.order, _START, _END, None, vram, ram, None)
            raise TrialFailure(RamReserveError(ram), evidence)
        return feasible(target, spec)

    install_fakes(monkeypatch, run)
    run_calibration_v5(cuda_target(), destination_root=tmp_path)

    record = load_record(tmp_path / "records" / "coding.json")
    assert record["envelope"]["n_cpu_moe"] == 39
    assert record["selection_rule"] == "single-finalist"
    assert record["search"]["finalists"][0]["outcome"] == "discarded"
