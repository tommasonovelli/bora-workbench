"""Render managed-engine phase, byte progress, and transfer ETA."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from types import TracebackType

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn

from qwen_launcher._engine_types import InstallProgressEvent


def _format_duration(seconds: float) -> str:
    """Format a short transfer estimate without implying subsecond precision."""
    rounded = max(0, round(seconds))
    minutes, remaining_seconds = divmod(rounded, 60)
    if minutes:
        return f"{minutes}m {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


def _format_bytes(size: float) -> str:
    """Format transfer bytes with compact binary units."""
    units = ("B", "KiB", "MiB", "GiB")
    value = max(0.0, size)
    for unit in units[:-1]:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {units[-1]}"


def _position(event: InstallProgressEvent) -> str:
    """Show which locked asset is active when the target contains multiple archives."""
    if event.item_index is None or event.item_count is None:
        return ""
    return f"[{event.item_index}/{event.item_count}] "


def _phase_message(event: InstallProgressEvent) -> str:
    """Translate one core event into concise user-facing installation progress."""
    asset = event.detail or "asset"
    position = _position(event)
    messages = {
        "asset": f"Checking locked asset {position}{asset}",
        "download": f"Downloading {position}{asset}",
        "extract": f"Extracting {position}{asset}",
        "compile": "Configuring and compiling Ubuntu CUDA llama-server",
        "verify": "Verifying llama-server version and help contracts",
        "activate": "Activating the verified managed engine",
    }
    return messages[event.stage]


def _plain_line(event: InstallProgressEvent) -> str:
    """Build one durable phase line for redirected output."""
    if event.stage == "download" and event.is_cached:
        return f"Using verified cached asset {_position(event)}{event.detail}."
    message = _phase_message(event)
    if event.stage == "compile":
        message += "; this can take several minutes"
    return f"{message}."


class EngineInstallProgress:
    """Show one live phase task while keeping redirected logs line-oriented."""

    def __init__(self, console: Console, get_time: Callable[[], float] = monotonic) -> None:
        """Bind progress to the command console and a testable monotonic clock."""
        self._console = console
        self._get_time = get_time
        self._is_live = console.is_terminal
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("{task.fields[metrics]}"),
            TextColumn("{task.fields[eta]}"),
            console=console,
            refresh_per_second=4,
            transient=True,
            redirect_stdout=False,
            redirect_stderr=False,
            get_time=get_time,
        )
        self._task_id: TaskID | None = None
        self._phase_key: tuple[str, str | None, int | None] | None = None
        self._phase_started_at = 0.0
        self._last_refresh_at = 0.0
        self._last_event: InstallProgressEvent | None = None

    def __enter__(self) -> EngineInstallProgress:
        """Start live refresh only when attached to an interactive terminal."""
        if self._is_live:
            self._progress.start()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop Rich cleanly and retain an honest measured-phase summary."""
        del exception, traceback
        if not self._is_live:
            return
        try:
            self._finish_phase(exception_type is None)
        finally:
            self._progress.stop()

    def __call__(self, event: InstallProgressEvent) -> None:
        """Consume one core event as live or line-oriented presentation."""
        phase_key = (event.stage, event.detail, event.item_index)
        if not self._is_live:
            if phase_key != self._phase_key:
                self._console.print(_plain_line(event))
                self._phase_key = phase_key
            return
        self._update_live(event, phase_key)

    def _update_live(
        self, event: InstallProgressEvent, phase_key: tuple[str, str | None, int | None]
    ) -> None:
        """Create or refresh the single visible installation task."""
        if phase_key != self._phase_key:
            self._finish_phase(True)
            self._phase_key = phase_key
            self._phase_started_at = self._get_time()
            self._last_refresh_at = self._phase_started_at
            self._task_id = self._progress.add_task(
                _phase_message(event), total=event.total_bytes, metrics="", eta=""
            )
        assert self._task_id is not None
        metrics, eta = self._transfer_fields(event)
        now = self._get_time()
        is_complete = bool(
            event.total_bytes is not None
            and event.completed_bytes is not None
            and event.completed_bytes >= event.total_bytes
        )
        should_refresh = is_complete or now - self._last_refresh_at >= 0.25
        self._progress.update(
            self._task_id,
            total=event.total_bytes,
            completed=event.completed_bytes or 0,
            metrics=metrics,
            eta=eta,
            refresh=should_refresh,
        )
        if should_refresh:
            self._last_refresh_at = now
        self._last_event = event

    def _transfer_fields(self, event: InstallProgressEvent) -> tuple[str, str]:
        """Calculate byte count, average rate, and remaining transfer time."""
        if event.completed_bytes is None:
            return "", ""
        completed = event.completed_bytes
        total = event.total_bytes
        amount = _format_bytes(completed)
        if total is not None:
            amount = f"{amount}/{_format_bytes(total)}"
        elapsed = self._get_time() - self._phase_started_at
        if elapsed <= 0 or completed <= 0:
            return amount, "ETA learning…" if total else ""
        rate = completed / elapsed
        metrics = f"{amount} · {_format_bytes(rate)}/s"
        if total is None:
            return metrics, ""
        remaining = max(0, total - completed) / rate
        return metrics, f"ETA ≈ {_format_duration(remaining)}"

    def _finish_phase(self, is_success: bool) -> None:
        """Clear the transient task and retain summaries for measured work."""
        if self._task_id is None:
            return
        self._progress.remove_task(self._task_id)
        event = self._last_event
        if event is not None and event.completed_bytes is not None:
            elapsed = _format_duration(self._get_time() - self._phase_started_at)
            state = "complete" if is_success else "stopped"
            if event.stage == "download" and event.is_cached:
                state = "cached"
            self._progress.console.print(
                f"[cyan]{_phase_message(event)}[/cyan] {state} in {elapsed}."
            )
        self._task_id = None
        self._phase_key = None
        self._last_event = None
