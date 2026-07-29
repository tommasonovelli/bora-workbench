"""Run the read-only Textual shell over the shared synchronous workbench snapshot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from bora_workbench.snapshot import (
    SnapshotFailure,
    WorkbenchCollectionError,
    WorkbenchSnapshot,
    collect_workbench_snapshot,
)
from bora_workbench.tui.palette import stylesheet
from bora_workbench.tui.screens.calibration import CalibrationView
from bora_workbench.tui.screens.installation import InstallationView
from bora_workbench.tui.screens.modes import ModesView
from bora_workbench.tui.screens.overview import OverviewView, render_failure
from bora_workbench.tui.screens.pi import PiView
from bora_workbench.tui.screens.settings import SettingsView
from bora_workbench.tui.screens.setup import SetupView
from bora_workbench.tui.terminal import TerminalMode

SnapshotCollector = Callable[[str], WorkbenchSnapshot]
ReadOnlyView = (
    OverviewView
    | ModesView
    | CalibrationView
    | SetupView
    | PiView
    | SettingsView
    | InstallationView
)
_VIEW_TYPES: tuple[type[ReadOnlyView], ...] = (
    OverviewView,
    ModesView,
    CalibrationView,
    SetupView,
    PiView,
    SettingsView,
    InstallationView,
)
_VIEW_LABELS = ("Overview", "Modes", "Calibration", "Setup", "Pi", "Settings", "This installation")


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
    """Present seven read-only views while serializing one snapshot worker."""

    CSS = (
        stylesheet()
        + """
#selected-view { height: 1fr; background: transparent; }
#views { width: 1fr; height: 1fr; }
#content { height: auto; }
#overview { height: auto; }
.section-view { width: 100%; height: auto; padding: 1 2; }
.section-title { height: 2; text-style: bold; }
.section-body { height: auto; }
"""
    )
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("up,k,left", "previous_view", "Previous", priority=True),
        Binding("down,j,right", "next_view", "Next", priority=True),
        Binding("question_mark", "toggle_help", "Help", priority=True),
        Binding("pageup", "scroll_detail_up", "Scroll up", priority=True, show=False),
        Binding("pagedown", "scroll_detail_down", "Scroll down", priority=True, show=False),
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
        self._selected_index = 0
        self._is_help_visible = False
        self._status_text = "Waiting to inspect this machine."

    def compose(self) -> ComposeResult:
        """Paint complete static chrome and all read-only views before collection starts."""
        display_class = "plain" if self._terminal_mode.is_plain else "normal"
        mode_label = " [plain]" if self._terminal_mode.is_plain else ""
        yield Vertical(
            Static(f"BORA WORKBENCH{mode_label}", id="brand", markup=False),
            Horizontal(
                Vertical(
                    Static("WORKBENCH", id="rail-label", markup=False),
                    Static(self._rail_text(), id="selected-view", markup=False),
                    id="rail",
                ),
                VerticalScroll(
                    OverviewView(),
                    ModesView(),
                    CalibrationView(),
                    SetupView(),
                    PiView(),
                    SettingsView(),
                    InstallationView(),
                    id="views",
                ),
                id="body",
            ),
            Static(self._keybar_text(), id="keybar", markup=False),
            id="shell",
            classes=display_class,
        )

    def on_mount(self) -> None:
        """Select Overview and delay collection until after the initial refresh."""
        self._show_selected_view()
        self.call_after_refresh(self._request_snapshot)

    def _views(self) -> tuple[ReadOnlyView, ...]:
        """Return the seven mounted views in persistent rail order."""
        return tuple(self.query_one(view_type) for view_type in _VIEW_TYPES)

    def _rail_text(self) -> str:
        """Mark the selected label in text so selection never depends on colour."""
        return "\n".join(
            f"{'>' if index == self._selected_index else ' '} {label}"
            for index, label in enumerate(_VIEW_LABELS)
        )

    def _keybar_text(self) -> str:
        """Render compact or expanded key help beside the current collection state."""
        if self._is_help_visible:
            keys = "Arrows/j/k Navigate | PgUp/PgDn Scroll | r Refresh | q/Esc Quit | ? Close help"
        else:
            keys = "Arrows/j/k Navigate | r Refresh | ? Help | q Quit"
        return f"{keys}\n{self._status_text}"

    def _show_selected_view(self) -> None:
        """Switch visible detail without discarding any collected screen text."""
        for index, view in enumerate(self._views()):
            view.display = index == self._selected_index
        self.query_one("#selected-view", Static).update(self._rail_text())
        self.query_one("#views", VerticalScroll).scroll_home(animate=False)

    def _set_status(self, text: str) -> None:
        """Update Overview and the global keybar with the same collection truth."""
        self._status_text = text
        self.query_one(OverviewView).update_status(text)
        self.query_one("#keybar", Static).update(self._keybar_text())

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
            content = render_failure(event.result.failure, event.result.unexpected_detail)
            for view in self._views()[1:]:
                view.query_one(".section-body", Static).update(content)
        else:
            self._set_status("Local snapshot ready.")
            for view in self._views():
                view.show_snapshot(event.result.snapshot)
        if self._is_refresh_pending:
            self._is_refresh_pending = False
            self.call_after_refresh(self._request_snapshot)

    def _move_selection(self, offset: int) -> None:
        """Move through the fixed rail with wraparound and no snapshot recollection."""
        self._selected_index = (self._selected_index + offset) % len(_VIEW_LABELS)
        self._show_selected_view()

    def action_previous_view(self) -> None:
        """Select the previous read-only screen from arrows or k."""
        self._move_selection(-1)

    def action_next_view(self) -> None:
        """Select the next read-only screen from arrows or j."""
        self._move_selection(1)

    def action_toggle_help(self) -> None:
        """Toggle expanded text key help without opening another modal surface."""
        self._is_help_visible = not self._is_help_visible
        self.query_one("#keybar", Static).update(self._keybar_text())

    def action_scroll_detail_up(self) -> None:
        """Scroll a long selected view by one page in small terminals."""
        self.query_one("#views", VerticalScroll).scroll_page_up(animate=False)

    def action_scroll_detail_down(self) -> None:
        """Scroll a long selected view by one page in small terminals."""
        self.query_one("#views", VerticalScroll).scroll_page_down(animate=False)

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
