"""Run the read-only Textual shell over the shared synchronous workbench snapshot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static

from bora_workbench.snapshot import (
    SnapshotFailure,
    WorkbenchCollectionError,
    WorkbenchSnapshot,
    collect_workbench_snapshot,
)
from bora_workbench.tui.palette import stylesheet
from bora_workbench.tui.screens.overview import OverviewView
from bora_workbench.tui.terminal import TerminalMode

SnapshotCollector = Callable[[str], WorkbenchSnapshot]


@dataclass(frozen=True, slots=True)
class _CollectionResult:
    """Carry either collected truth or an explicit presentation-safe failure."""

    snapshot: WorkbenchSnapshot | None
    failure: SnapshotFailure | None = None
    unexpected_detail: str | None = None


class SnapshotCollected(Message):
    """Deliver one synchronous worker result back to Textual's presentation loop."""

    def __init__(self, result: _CollectionResult) -> None:
        """Retain the immutable result while initializing Textual message metadata."""
        super().__init__()
        self.result = result


def _collect(collector: SnapshotCollector, version: str) -> _CollectionResult:
    """Run one snapshot attempt and turn every failure into renderable local state."""
    try:
        return _CollectionResult(collector(version))
    except WorkbenchCollectionError as error:
        return _CollectionResult(None, error.failure)
    except Exception as error:
        return _CollectionResult(None, unexpected_detail=str(error) or type(error).__name__)


class WorkbenchApp(App[None]):
    """Present one overview while serializing refreshes through a single thread worker."""

    CSS = stylesheet()
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "exit_workbench", "Quit", priority=True),
        Binding("ctrl+q", "exit_workbench", "Quit", priority=True, show=False),
        Binding("escape", "exit_workbench", "Quit", priority=True, show=False),
        Binding("r", "refresh_snapshot", "Refresh", priority=True),
    ]

    def __init__(
        self, version: str, terminal_mode: TerminalMode, collector: SnapshotCollector
    ) -> None:
        """Create static presentation state without collecting or mutating machine facts."""
        super().__init__()
        self._version = version
        self._terminal_mode = terminal_mode
        self._collector = collector
        self._is_collecting = False
        self._is_refresh_pending = False

    def compose(self) -> ComposeResult:
        """Paint complete static chrome before the collector worker is scheduled."""
        display_class = "plain" if self._terminal_mode.is_plain else "normal"
        mode_label = " [plain]" if self._terminal_mode.is_plain else ""
        yield Vertical(
            Static(f"BORA WORKBENCH{mode_label}", id="brand", markup=False),
            Horizontal(
                Vertical(
                    Static("WORKBENCH", id="rail-label", markup=False),
                    Static("> Overview", id="selected-view", markup=False),
                    id="rail",
                ),
                OverviewView(),
                id="body",
            ),
            Static("q / Ctrl+Q / Esc  Quit     r  Refresh", id="keybar", markup=False),
            id="shell",
            classes=display_class,
        )

    def on_mount(self) -> None:
        """Delay the first collection until Textual has completed the initial refresh."""
        self.call_after_refresh(self._request_snapshot)

    def _set_status(self, text: str) -> None:
        """Update the bounded collection-state line on the presentation thread."""
        self.query_one(OverviewView).update_status(text)

    def _request_snapshot(self) -> None:
        """Start one worker or coalesce repeated refresh requests behind the active one."""
        if self._is_collecting:
            self._is_refresh_pending = True
            self._set_status("Refresh queued; current inspection is still running.")
            return
        self._is_collecting = True
        self._set_status("Inspecting local state...")
        self._collect_snapshot()

    @work(thread=True, group="snapshot", exit_on_error=False)
    def _collect_snapshot(self) -> None:
        """Run the synchronous core collector in Textual's sole background thread."""
        result = _collect(self._collector, self._version)
        self.post_message(SnapshotCollected(result))

    def on_snapshot_collected(self, event: SnapshotCollected) -> None:
        """Render one worker result and then honor at most one coalesced refresh."""
        self._is_collecting = False
        overview = self.query_one(OverviewView)
        if event.result.snapshot is None:
            self._set_status("Inspection failed; details are current for this attempt.")
            overview.show_failure(event.result.failure, event.result.unexpected_detail)
        else:
            self._set_status("Local snapshot ready.")
            overview.show_snapshot(event.result.snapshot)
        if self._is_refresh_pending:
            self._is_refresh_pending = False
            self.call_after_refresh(self._request_snapshot)

    def action_refresh_snapshot(self) -> None:
        """Request a read-only refresh without allowing overlapping collectors."""
        self._request_snapshot()

    def action_exit_workbench(self) -> None:
        """Leave the presentation loop without waiting for another key sequence."""
        self.exit()


def run_tui(
    version: str,
    terminal_mode: TerminalMode,
    collector: SnapshotCollector = collect_workbench_snapshot,
) -> None:
    """Run the interactive presentation after the CLI has completed capability checks."""
    WorkbenchApp(version, terminal_mode, collector).run()
