"""Count calibration trials and report them where every fresh process passes.

Progress is presentation only: it never changes the measured protocol or the persisted evidence.
The search is adaptive, so no phase knows its exact trial count in advance; counting inside the
trial runner keeps the reported position exact without threading a callback through the search,
confirmation, and gate orchestration (spec 5.6).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Report phase progress for one mode without changing persisted calibration evidence.

    ``completed`` always counts finished trials; while running, the current trial is the next one.
    """

    mode_id: str
    phase: str
    completed: int
    total: int
    estimated_remaining_seconds: float | None
    is_running: bool = False


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(slots=True)
class TrialProgress:
    """Track the current phase of one mode group and emit one event per fresh process."""

    callback: ProgressCallback | None = None
    get_time: Callable[[], float] = monotonic
    mode_id: str = ""
    phase: str = "search"
    total: int = 0
    completed: int = 0
    _elapsed: float = 0.0
    _started_at: float | None = None

    def enter(self, mode_id: str, phase: str, total: int) -> None:
        """Begin one phase of one mode, resetting the per-phase trial count and timing."""
        self.mode_id = mode_id
        self.phase = phase
        self.total = total
        self.completed = 0
        self._elapsed = 0.0
        self._started_at = None

    def started(self) -> None:
        """Announce the trial that is about to start its fresh server."""
        self._started_at = self.get_time()
        self._emit(True)

    def finished(self) -> None:
        """Record one completed trial, however it ended, and refresh the duration estimate."""
        if self._started_at is not None:
            self._elapsed += self.get_time() - self._started_at
            self._started_at = None
        self.completed += 1
        self._emit(False)

    def _remaining_seconds(self) -> float | None:
        """Project the remaining phase duration from the trials this phase already measured."""
        if not self.completed or self.completed >= self.total:
            return None
        return (self._elapsed / self.completed) * (self.total - self.completed)

    def _emit(self, is_running: bool) -> None:
        """Send one event, tolerating a run that was started without any presentation."""
        if self.callback is None:
            return
        self.callback(
            ProgressEvent(
                self.mode_id,
                self.phase,
                self.completed,
                self.total,
                self._remaining_seconds(),
                is_running,
            )
        )
