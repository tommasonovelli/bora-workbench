"""Verify calibration/v3 progress ordering and phase-local duration learning."""

from __future__ import annotations

import pytest

from qwen_launcher._calibration_ram import RamError
from qwen_launcher._calibration_v3_runner import run_calibration_v3
from qwen_launcher._calibration_v3_types import ProgressEvent, V3RunOptions
from qwen_launcher.calibration import CalibrationRunError
from tests.test_calibration_v3_runner import cuda_target, fake_trial, install_fakes


def test_progress_pairs_started_and_completed_events_by_phase(tmp_path, monkeypatch) -> None:
    """Show every blocking trial and avoid carrying screening timing into confirmation."""
    events: list[ProgressEvent] = []
    trial = fake_trial(lambda spec: (spec.plan.n_cpu_moe or 0) >= 38)
    install_fakes(monkeypatch, trial)

    run_calibration_v3(
        cuda_target(),
        V3RunOptions(progress=events.append),
        destination_root=tmp_path,
    )

    assert len(events) % 2 == 0
    for started, completed in zip(events[::2], events[1::2], strict=True):
        assert started.is_running and not completed.is_running
        assert started.phase == completed.phase
        assert started.completed + 1 == completed.completed
    learned = next(item for item in events if item.phase == "screening" and item.completed == 2)
    assert learned.estimated_remaining_seconds == 600.0
    confirmation = [item for item in events if item.phase == "confirmation"]
    assert confirmation[0].is_running
    assert confirmation[0].estimated_remaining_seconds is None
    assert confirmation[1].estimated_remaining_seconds == 180.0


def test_invalidated_run_leaves_the_current_trial_visible(tmp_path, monkeypatch) -> None:
    """Emit started without a false completion when monitoring invalidates the run."""
    events: list[ProgressEvent] = []

    def invalidated(target, spec):
        """Simulate a run-level RAM monitor failure after progress starts."""
        raise RamError("RAM monitoring failed")

    install_fakes(monkeypatch, invalidated)
    with pytest.raises(CalibrationRunError, match="run invalidated"):
        run_calibration_v3(
            cuda_target(),
            V3RunOptions(progress=events.append),
            destination_root=tmp_path,
        )

    assert len(events) == 1
    assert events[0].is_running
    assert events[0].completed == 0
