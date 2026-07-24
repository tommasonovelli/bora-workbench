"""Offline tests for calibration/v5 trial cleanup and failure precedence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import qwen_launcher._calibration_v5_process as process_module
from qwen_launcher._calibration_ram import RamError
from qwen_launcher._calibration_v5_plan import build_plan
from qwen_launcher._calibration_v5_process import TrialSpec, run_trial
from qwen_launcher._calibration_v5_types import TrialOrder
from qwen_launcher._calibration_vram import VramEnvironmentError
from qwen_launcher.benchmark import BenchmarkError
from tests.test_calibration import cpu_target


class _BrokenRamMonitor:
    """Fail the baseline query and then report cleanup never started it."""

    def start(self) -> None:
        """Simulate the original run-invalidating baseline failure."""
        raise RamError("baseline RAM query failed")

    def finish(self) -> None:
        """Simulate the secondary unstarted-monitor cleanup failure."""
        raise RamError("RAM monitor was not started")


def test_baseline_monitor_failure_is_not_masked_by_cleanup(tmp_path, monkeypatch) -> None:
    """Preserve the actionable original monitor diagnosis after full cleanup."""
    target = cpu_target()
    run = SimpleNamespace(target=target, mode=target.modes[0])
    plan = build_plan(run, 8192, None)
    monkeypatch.setattr(
        process_module,
        "_monitors",
        lambda target, baseline: (None, _BrokenRamMonitor()),
    )
    spec = TrialSpec(plan, tmp_path / "trial", False, tmp_path, TrialOrder("screening", 1))

    with pytest.raises(RamError, match="baseline RAM query failed"):
        run_trial(target, spec)


def test_cleanup_environment_failure_overrides_workload_failure(tmp_path, monkeypatch) -> None:
    """Invalidate the run when cleanup evidence outranks a failed candidate workload."""
    target = cpu_target()
    run = SimpleNamespace(target=target, mode=target.modes[0])
    plan = build_plan(run, 8192, None)
    spec = TrialSpec(plan, tmp_path / "trial", False, tmp_path, TrialOrder("screening", 1))
    assembled: list[object] = []
    original_evidence = process_module._evidence

    def fail_workload(*args) -> None:
        """Simulate a semantic workload failure before cleanup."""
        raise BenchmarkError("invalid completion")

    def finish_with_environment_error(*args):
        """Return the run-invalidating monitor diagnosis found during cleanup."""
        return None, None, VramEnvironmentError("GPU evidence changed")

    def record_evidence(*args):
        """Prove evidence assembly happens before the preferred error is raised."""
        assembled.append(args)
        return original_evidence(*args)

    monkeypatch.setattr(process_module, "_execute", fail_workload)
    monkeypatch.setattr(process_module, "_finish", finish_with_environment_error)
    monkeypatch.setattr(process_module, "_evidence", record_evidence)

    with pytest.raises(VramEnvironmentError, match="GPU evidence changed"):
        run_trial(target, spec)

    assert len(assembled) == 1


def test_control_flow_failure_survives_cleanup_failure(tmp_path, monkeypatch) -> None:
    """Never replace KeyboardInterrupt with a cleanup diagnostic."""
    target = cpu_target()
    run = SimpleNamespace(target=target, mode=target.modes[0])
    plan = build_plan(run, 8192, None)
    spec = TrialSpec(plan, tmp_path / "trial", False, tmp_path, TrialOrder("screening", 1))
    monkeypatch.setattr(
        process_module,
        "_execute",
        lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        process_module,
        "_finish",
        lambda *args: (None, None, VramEnvironmentError("cleanup")),
    )

    with pytest.raises(KeyboardInterrupt):
        run_trial(target, spec)
