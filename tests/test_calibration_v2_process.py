"""Offline tests for calibration/v2 trial cleanup and failure precedence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import qwen_launcher._calibration_v2_process as process_module
from qwen_launcher._calibration_ram import RamError
from qwen_launcher._calibration_v2_confirm import build_plan
from qwen_launcher._calibration_v2_process import TrialSpec, run_trial
from tests.test_calibration import cpu_target


class _BrokenRamMonitor:
    """Fail the baseline query and then report that cleanup never started it."""

    def start(self) -> None:
        """Simulate the original run-invalidating baseline failure."""
        raise RamError("baseline RAM query failed")

    def finish(self) -> None:
        """Simulate the secondary unstarted-monitor cleanup failure."""
        raise RamError("RAM monitor was not started")


def test_baseline_monitor_failure_is_not_masked_by_cleanup(tmp_path, monkeypatch) -> None:
    """Preserve the actionable original monitor diagnosis after full cleanup."""
    target = cpu_target()
    mode = target.modes[0]
    run = SimpleNamespace(target=target, mode=mode)
    plan = build_plan(run, 8192, None)
    monkeypatch.setattr(process_module, "_monitors", lambda target: (None, _BrokenRamMonitor()))

    with pytest.raises(RamError, match="baseline RAM query failed"):
        run_trial(target, TrialSpec(plan, tmp_path / "trial", False))
