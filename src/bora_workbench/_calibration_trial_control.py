"""Give every fresh calibration trial its port, its count, and its failure order (spec 5.6).

The three rules here surround one trial without measuring it. A trial server binds an isolated
loopback port, because the configured port may already belong to a running service. A trial is
counted where every fresh process passes, because the search is adaptive and no phase knows its
exact trial count in advance; counting here keeps the reported position exact without threading a
callback through the search, confirmation, and gate orchestration. Progress stays presentation
only: it never changes the measured protocol or the persisted evidence.

Cleanup runs even when the workload already failed, so two errors can compete for the same trial.
D-058 fixes the order: control flow first, then evidence that invalidates the whole run, then the
diagnostics that only discard one candidate.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from bora_workbench._calibration_memory import RamError, VramEnvironmentError
from bora_workbench.process import port_is_available


def select_trial_port(preferred_port: int) -> int:
    """Use the configured port when free, otherwise ask the OS for a temporary loopback port."""
    if port_is_available(preferred_port):
        return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


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
    _is_reporting: bool = True

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
        """Send one event, tolerating a run started without presentation or with a failing one.

        A console that cannot encode, render, or accept an event must not end a measurement that
        costs hours, so reporting stops here instead of reaching the trial. The failure is not
        announced through that same console, which is the one that just proved unusable.
        Control-flow exceptions keep the precedence `prefer_cleanup_error` gives them.
        """
        if self.callback is None or not self._is_reporting:
            return
        event = ProgressEvent(
            self.mode_id,
            self.phase,
            self.completed,
            self.total,
            self._remaining_seconds(),
            is_running,
        )
        try:
            self.callback(event)
        except Exception:
            self._is_reporting = False


def prefer_cleanup_error(current: BaseException | None, new: BaseException) -> BaseException:
    """Prefer control flow, then run-invalidating failures, over candidate diagnostics."""
    if current is not None and not isinstance(current, Exception):
        return current
    if not isinstance(new, Exception):
        return new
    if isinstance(current, (VramEnvironmentError, RamError)):
        return current
    if isinstance(new, (VramEnvironmentError, RamError)):
        return new
    return new if current is None else current
