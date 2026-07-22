"""Render calibration/v4 progress without changing the measured protocol."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from types import TracebackType

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

from qwen_launcher._calibration_v4_types import ProgressEvent


def _format_duration(seconds: float) -> str:
    """Format a learned or elapsed duration for compact terminal feedback."""
    rounded = max(0, round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


def _count_text(event: ProgressEvent) -> str:
    """Distinguish the screening budget cap from an exact phase total."""
    separator = "/≤" if event.phase == "screening" else "/"
    return f"{event.completed}{separator}{event.total}"


def _remaining_text(event: ProgressEvent) -> str:
    """Label screening time as a cap projection and confirmation time as an ETA."""
    if event.estimated_remaining_seconds is None:
        return "learning duration…"
    duration = _format_duration(event.estimated_remaining_seconds)
    if event.phase == "screening":
        return f"cap projection ≈ {duration}"
    return f"ETA ≈ {duration}"


def _plain_line(event: ProgressEvent) -> str:
    """Build stable non-interactive output for one completed trial."""
    message = f"{event.mode_id} {event.phase}: {_count_text(event)}"
    if event.estimated_remaining_seconds is None:
        return message
    return f"{message}; {_remaining_text(event)}"


class CalibrationProgress:
    """Show a live TTY task while preserving line-oriented redirected output."""

    def __init__(self, console: Console, get_time: Callable[[], float] = monotonic) -> None:
        """Bind progress to the caller's console so terminal detection remains accurate."""
        self._console = console
        self._get_time = get_time
        self._is_live = console.is_terminal
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("{task.fields[count]}"),
            TimeElapsedColumn(),
            TextColumn("{task.fields[remaining]}"),
            console=console,
            refresh_per_second=4,
            transient=True,
            redirect_stdout=False,
            redirect_stderr=False,
            get_time=get_time,
        )
        self._task_id: TaskID | None = None
        self._phase_key: tuple[str, str] | None = None
        self._phase_started_at = 0.0
        self._last_event: ProgressEvent | None = None

    def __enter__(self) -> CalibrationProgress:
        """Start live refresh only for an interactive terminal."""
        if self._is_live:
            self._progress.start()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop Rich cleanly and retain a phase summary on success or failure."""
        del exception, traceback
        if not self._is_live:
            return
        try:
            is_success = exception_type is None or self._is_exact_phase_complete()
            self._finish_phase(is_success)
        finally:
            self._progress.stop()

    def __call__(self, event: ProgressEvent) -> None:
        """Consume one core event as live or line-oriented presentation."""
        if not self._is_live:
            if not event.is_running:
                self._console.print(_plain_line(event))
            return
        self._update_live(event)

    def _update_live(self, event: ProgressEvent) -> None:
        """Create or refresh the single visible mode-phase task."""
        phase_key = (event.mode_id, event.phase)
        if phase_key != self._phase_key:
            self._finish_phase(True)
            self._phase_key = phase_key
            self._phase_started_at = self._get_time()
            self._task_id = self._progress.add_task(
                self._description(event),
                total=event.total,
                completed=event.completed,
                count=_count_text(event),
                remaining=_remaining_text(event),
            )
        else:
            assert self._task_id is not None
            self._progress.update(
                self._task_id,
                total=event.total,
                completed=event.completed,
                description=self._description(event),
                count=_count_text(event),
                remaining=_remaining_text(event),
                refresh=True,
            )
        self._last_event = event

    def _description(self, event: ProgressEvent) -> str:
        """Name the mode, phase, and currently running or completed trial."""
        trial = event.completed + 1 if event.is_running else event.completed
        state = "running" if event.is_running else "complete"
        return f"{event.mode_id} · {event.phase} · trial {trial} {state}"

    def _is_exact_phase_complete(self) -> bool:
        """Recognize completed confirmation even if later record persistence fails."""
        event = self._last_event
        return bool(
            event
            and event.phase == "confirmation"
            and not event.is_running
            and event.completed == event.total
        )

    def _finish_phase(self, is_success: bool) -> None:
        """Persist a concise phase result before replacing the transient task."""
        if self._task_id is None or self._last_event is None or self._phase_key is None:
            return
        elapsed = _format_duration(self._get_time() - self._phase_started_at)
        state = "complete" if is_success else "stopped"
        mode_id, phase = self._phase_key
        completed = self._last_event.completed
        self._progress.remove_task(self._task_id)
        self._progress.console.print(
            f"[cyan]{mode_id}[/cyan] {phase} {state}: {completed} trial(s) in {elapsed}."
        )
        self._task_id = None
        self._phase_key = None
        self._last_event = None
