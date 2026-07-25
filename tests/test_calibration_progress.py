"""Offline tests for calibration trial counting and duration projection."""

from __future__ import annotations

from qwen_launcher._calibration_progress import ProgressEvent, TrialProgress


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
