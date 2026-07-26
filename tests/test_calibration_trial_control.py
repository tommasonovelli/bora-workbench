"""Offline tests for trial port isolation, trial counting, and duration projection."""

from __future__ import annotations

import socket
from dataclasses import replace

import pytest

import bora_workbench._calibration_trial as trial_module
from bora_workbench._calibration_memory import RamSummary
from bora_workbench._calibration_trial import TrialRunner
from bora_workbench._calibration_trial_control import ProgressEvent, TrialProgress
from bora_workbench.config import Config
from tests.record_fixtures import cpu_hardware, record_target


class _Clock:
    """Advance a deterministic monotonic clock by a fixed step per reading."""

    def __init__(self, step: float) -> None:
        """Start at zero and advance by ``step`` on every call."""
        self._now = 0.0
        self._step = step

    def __call__(self) -> float:
        """Return the current time and advance it."""
        value = self._now
        self._now += self._step
        return value


def test_calibration_plans_avoid_an_occupied_configured_port(tmp_path) -> None:
    """Keep calibration usable while another local service already owns llama_port."""
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        target = replace(record_target(cpu_hardware()), config=Config(llama_port=port))
        runner = TrialRunner(target, target.modes[0], tmp_path)
        plan = runner._plan((8192, None))

    assert plan.port != port


def test_calibration_plans_use_the_configured_port_when_it_is_free(tmp_path) -> None:
    """Prefer the configured port so a trial stays observable at the documented address."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    target = replace(record_target(cpu_hardware()), config=Config(llama_port=port))

    plan = TrialRunner(target, target.modes[0], tmp_path)._plan((8192, None))

    assert plan.port == port


def test_each_trial_reports_a_running_then_a_completed_event() -> None:
    """Report the trial about to start and the trial that finished, however it ended."""
    events: list[ProgressEvent] = []
    progress = TrialProgress(events.append)
    progress.enter("coding+studio", "search", 28)
    progress.started()
    progress.finished()
    assert [(event.completed, event.is_running) for event in events] == [(0, True), (1, False)]
    assert all(event.mode_id == "coding+studio" and event.phase == "search" for event in events)


def test_entering_a_phase_resets_the_count_and_the_projection() -> None:
    """Keep each phase's position independent, because phases have different trial counts."""
    events: list[ProgressEvent] = []
    progress = TrialProgress(events.append)
    progress.enter("coding", "search", 28)
    progress.started()
    progress.finished()
    progress.enter("coding", "gate", 3)
    progress.started()
    last = events[-1]
    assert (last.phase, last.completed, last.total) == ("gate", 0, 3)
    assert last.estimated_remaining_seconds is None


def test_the_projection_uses_the_trials_this_phase_already_measured() -> None:
    """Learn the duration from measured trials instead of assuming a fixed trial cost."""
    events: list[ProgressEvent] = []
    progress = TrialProgress(events.append, _Clock(10.0))
    progress.enter("coding", "gate", 3)
    progress.started()
    progress.finished()
    assert events[-1].estimated_remaining_seconds == 20.0


def test_a_run_without_presentation_still_counts_trials() -> None:
    """Keep the counter usable when no console is attached, so nothing depends on rendering."""
    progress = TrialProgress()
    progress.enter("coding", "search", 28)
    progress.started()
    progress.finished()
    assert progress.completed == 1


def test_a_failing_renderer_cannot_end_a_measurement_run() -> None:
    """Keep measuring when the console rejects an event, and stop retrying that console.

    Progress is presentation only, so a redirected stream that cannot encode a line must not
    discard the trials a run has already paid for.
    """
    attempts: list[ProgressEvent] = []

    def callback(event: ProgressEvent) -> None:
        """Fail the way a console on an unusable stream fails."""
        attempts.append(event)
        raise RuntimeError("console is unusable")

    progress = TrialProgress(callback)
    progress.enter("coding", "search", 28)
    progress.started()
    progress.finished()

    assert progress.completed == 1
    assert len(attempts) == 1


def test_progress_cleanup_failure_cannot_mask_workload_interrupt(tmp_path, monkeypatch) -> None:
    """Keep Ctrl-C ahead of a renderer failure emitted after trial cleanup."""
    target = record_target(cpu_hardware())

    def callback(event: ProgressEvent) -> None:
        """Fail only while announcing the completed trial."""
        if not event.is_running:
            raise RuntimeError("renderer failed")

    class _Session:
        """Provide completed monitor cleanup without starting host resources."""

        def __init__(self) -> None:
            """Expose the fields consumed by the trial runner."""
            self.spawned = lambda pid: None
            self.running = None

        def start(self) -> None:
            """Stand in for monitor startup."""

        def finish(self, root):
            """Return valid cleanup summaries after the workload fails."""
            return trial_module._SessionResources(None, RamSummary(24.0, 20.0), None)

    progress = TrialProgress(callback)
    progress.enter("coding", "search", 1)
    runner = TrialRunner(target, target.modes[0], tmp_path, progress=progress)
    monkeypatch.setattr(trial_module, "_create_session", lambda *args: _Session())
    monkeypatch.setattr(trial_module, "build_command", lambda *args: ("server",))
    monkeypatch.setattr(trial_module, "start_service", lambda *args: object())

    with pytest.raises(KeyboardInterrupt):
        runner._run(
            (8192, None),
            lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
