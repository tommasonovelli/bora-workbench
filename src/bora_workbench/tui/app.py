"""Run the read-only Textual shell over the shared synchronous workbench snapshot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import ClassVar

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Static

from bora_workbench.snapshot import (
    SnapshotFailure,
    WorkbenchCollectionError,
    WorkbenchSnapshot,
    collect_workbench_snapshot,
)
from bora_workbench.tui.actions import TuiResult, snapshot_changes
from bora_workbench.tui.home import HomeView, brand_text
from bora_workbench.tui.motion import (
    FRAME_INTERVAL_SECONDS,
    MotionDimensions,
    gust,
    sea,
    supports_motion_size,
)
from bora_workbench.tui.palette import palette_for, stylesheet
from bora_workbench.tui.screens import modes as modes_screen
from bora_workbench.tui.screens import pi as pi_screen
from bora_workbench.tui.screens import setup as setup_screen
from bora_workbench.tui.screens.calibration import CalibrationView
from bora_workbench.tui.screens.installation import InstallationView
from bora_workbench.tui.screens.modes import ModesView
from bora_workbench.tui.screens.overview import OverviewView, render_failure
from bora_workbench.tui.screens.pi import PiView
from bora_workbench.tui.screens.settings import SettingsView
from bora_workbench.tui.screens.setup import SetupView
from bora_workbench.tui.section import Section
from bora_workbench.tui.terminal import TerminalMode

SnapshotCollector = Callable[[str], WorkbenchSnapshot]
# The section order matches the central menu in bora_workbench.tui.menu.
_VIEW_TYPES: tuple[type[Section], ...] = (
    ModesView,
    CalibrationView,
    SetupView,
    OverviewView,
    PiView,
    SettingsView,
    InstallationView,
)
# Flag keys are read back from the screens that declare them, so a new flag cannot be added
# without also gaining the binding that switches it.
_FLAGGED_CHOICES = (*modes_screen.CHOICES, *setup_screen.CHOICES, *pi_screen.CHOICES)
_TOGGLE_KEYS = tuple(
    dict.fromkeys(flag.key for choice in _FLAGGED_CHOICES for flag in choice.flags)
)
_LETTER_ACTIONS = frozenset(("refresh_snapshot", "toggle_help", "quit_workbench", "toggle_flag"))
_HOME_KEYS = "up/down move  enter open  r refresh  ? help  q quit"
_SECTION_KEYS = "up/down move  enter select  esc menu  r refresh  q quit"
_HELP_TEXT = (
    "Enter opens the marked entry and selects the shown command; a bracketed letter "
    "switches that command's flag; Esc leaves a section without running anything."
)


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


class WorkbenchApp(App[TuiResult]):
    """Present one shared identity around a central menu and seven centred sections."""

    CSS = stylesheet()
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("up,k", "move(-1)", "Up", priority=True),
        Binding("down,j", "move(1)", "Down", priority=True),
        Binding("enter,right", "activate", "Open", priority=True),
        Binding("escape,left", "leave_section", "Menu", priority=True),
        Binding("pageup", "scroll_detail(-1)", "Scroll up", priority=True, show=False),
        Binding("pagedown", "scroll_detail(1)", "Scroll down", priority=True, show=False),
        Binding("question_mark", "toggle_help", "Help", priority=True),
        Binding("r", "refresh_snapshot", "Refresh", priority=True),
        Binding("q,ctrl+q", "quit_workbench", "Quit", priority=True),
        *(
            Binding(key, f"toggle_flag('{key}')", "Flag", priority=True, show=False)
            for key in _TOGGLE_KEYS
        ),
    ]

    def __init__(
        self, version: str, terminal_mode: TerminalMode, collector: SnapshotCollector
    ) -> None:
        """Create static presentation state without collecting or mutating machine facts."""
        super().__init__(ansi_color=True)
        self._version = version
        self._terminal_mode = terminal_mode
        self._collector = collector
        self._palette = palette_for(terminal_mode.is_plain)
        self._is_collecting = False
        self._is_refresh_pending = False
        self._open_index: int | None = None
        self._is_help_visible = False
        self._status_text = "Waiting to inspect this machine."
        self._latest_snapshot: WorkbenchSnapshot | None = None
        self._comparison_snapshot: WorkbenchSnapshot | None = None
        self._motion_timer: Timer | None = None
        self._motion_elapsed = 0.0
        self._motion_started_at: float | None = None
        self._has_app_focus = True

    def compose(self) -> ComposeResult:
        """Paint shared wind, title, content, and sea before collection starts."""
        display_class = "plain" if self._terminal_mode.is_plain else "normal"
        yield Vertical(
            Static("", id="wind", markup=False),
            Static(brand_text(self._palette), id="brand", markup=False),
            Vertical(
                HomeView(self._palette),
                VerticalScroll(
                    *(view_type(self._palette) for view_type in _VIEW_TYPES), id="sections"
                ),
                id="content",
            ),
            Static("", id="sea", markup=False),
            Static(self._status_text, id="status", markup=False),
            Static(self._keybar_text(), id="keybar", markup=False),
            id="shell",
            classes=display_class,
        )

    def on_mount(self) -> None:
        """Show the central menu and delay collection until after the initial refresh."""
        self._show_surface()
        self.call_after_refresh(self._request_snapshot)

    def _home(self) -> HomeView:
        """Return the single mounted central-menu surface."""
        return self.query_one(HomeView)

    def _views(self) -> tuple[Section, ...]:
        """Return the seven mounted sections in persistent menu order."""
        return tuple(self.query_one(view_type) for view_type in _VIEW_TYPES)

    def _open_view(self) -> Section | None:
        """Return the section currently filling the window, or None on the menu."""
        return None if self._open_index is None else self._views()[self._open_index]

    def _keybar_text(self) -> str:
        """Render the keys that the currently visible surface actually uses."""
        if self._is_help_visible:
            return _HELP_TEXT
        return _HOME_KEYS if self._open_index is None else _SECTION_KEYS

    def _show_surface(self) -> None:
        """Switch between the central menu and one full-window section."""
        open_index = self._open_index
        self._home().display = open_index is None
        self.query_one("#sections", VerticalScroll).display = open_index is not None
        for index, view in enumerate(self._views()):
            view.display = index == open_index
        self.query_one("#sections", VerticalScroll).scroll_home(animate=False)
        self.query_one("#keybar", Static).update(self._keybar_text())
        self._sync_motion()

    def _motion_dimensions(self) -> MotionDimensions:
        """Return current terminal cells for pure motion rendering and size gating."""
        return MotionDimensions(self.size.width, self.size.height)

    def _can_show_decoration(self) -> bool:
        """Require colour, focus, and enough cells before either static band is visible."""
        return (
            not self._terminal_mode.is_plain
            and self._has_app_focus
            and supports_motion_size(self._motion_dimensions())
        )

    def _can_run_motion(self) -> bool:
        """Animate only on home while keeping the same graphic static in sections."""
        return (
            self._can_show_decoration()
            and self._terminal_mode.is_motion_enabled
            and self._open_index is None
        )

    def _current_motion_elapsed(self) -> float:
        """Return active animation time without counting periods where it was stopped."""
        if self._motion_started_at is None:
            return self._motion_elapsed
        return self._motion_elapsed + monotonic() - self._motion_started_at

    def _stop_motion_timer(self) -> None:
        """Remove periodic wakeups immediately when motion cannot continue."""
        if self._motion_timer is not None:
            self._motion_timer.stop()
            self._motion_timer = None

    def _freeze_motion(self) -> None:
        """Retain elapsed time and stop periodic work while preserving one visible frame."""
        self._motion_elapsed = self._current_motion_elapsed()
        self._motion_started_at = None
        self._stop_motion_timer()
        self._render_motion(self._motion_elapsed)

    def _hide_decoration(self) -> None:
        """Stop periodic work and collapse both bands under a hard capability switch."""
        self._motion_elapsed = self._current_motion_elapsed()
        self._motion_started_at = None
        self._stop_motion_timer()
        for band in ("#wind", "#sea"):
            self.query_one(band, Static).display = False

    def _render_motion(self, elapsed_seconds: float) -> None:
        """Render one deterministic frame whose text carries no operational meaning."""
        dimensions = self._motion_dimensions()
        for band, render in (("#wind", gust), ("#sea", sea)):
            widget = self.query_one(band, Static)
            widget.update(render(elapsed_seconds, dimensions, 41))
            widget.display = True

    def _sync_motion(self) -> None:
        """Animate home or retain the shared static frame without unnecessary wakeups."""
        if not self._can_show_decoration():
            self._hide_decoration()
            return
        if not self._can_run_motion():
            self._freeze_motion()
            return
        if self._motion_started_at is None:
            self._motion_started_at = monotonic()
        self._render_motion(self._current_motion_elapsed())
        if self._motion_timer is None:
            self._motion_timer = self.set_interval(
                FRAME_INTERVAL_SECONDS, self._advance_motion, name="bora-motion"
            )

    def _advance_motion(self) -> None:
        """Render one scheduled frame while every presentation capability remains true."""
        if not self._can_run_motion():
            self._sync_motion()
            return
        self._render_motion(self._current_motion_elapsed())

    def on_app_blur(self, event: events.AppBlur) -> None:
        """Stop animation when Textual reports that its terminal lost focus."""
        self._has_app_focus = False
        self._sync_motion()

    def on_app_focus(self, event: events.AppFocus) -> None:
        """Resume any unfinished animation when Textual reports restored focus."""
        self._has_app_focus = True
        self._sync_motion()

    def on_resize(self, event: events.Resize) -> None:
        """Apply the small-terminal kill switch immediately after a resize."""
        self._sync_motion()

    def on_unmount(self) -> None:
        """Release the frame timer so no scheduled frame can outlive the widget tree."""
        self._stop_motion_timer()

    def _set_status(self, text: str) -> None:
        """Update the single shared collection-state line."""
        self._status_text = text
        self.query_one("#status", Static).update(text)

    def set_comparison_snapshot(self, snapshot: WorkbenchSnapshot | None) -> None:
        """Provide one pre-command snapshot for the next successful collection to compare."""
        self._comparison_snapshot = snapshot

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

    def _show_failure(self, result: _CollectionResult) -> None:
        """Replace every stale surface with the current failed-attempt diagnosis."""
        self._latest_snapshot = None
        self._set_status("Inspection failed; details are current for this attempt.")
        self._home().show_failure(result.failure, result.unexpected_detail)
        self.query_one(OverviewView).show_failure(result.failure, result.unexpected_detail)
        content = render_failure(result.failure, result.unexpected_detail)
        for view in self._views():
            if not isinstance(view, OverviewView):
                view.show_body(content)

    def _show_collected(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace every surface with the facts of one successful collection."""
        self._latest_snapshot = snapshot
        changes: tuple[str, ...] = ()
        if self._comparison_snapshot is not None:
            changes = snapshot_changes(self._comparison_snapshot, snapshot)
            self.query_one(OverviewView).show_changes(changes)
            self._comparison_snapshot = None
        self._home().show_snapshot(snapshot)
        for view in self._views():
            view.show_snapshot(snapshot)
        ready = "Local snapshot ready."
        self._set_status(
            ready if not changes else f"{ready} {len(changes)} change(s) listed in Diagnostics."
        )

    def on_snapshot_collected(self, event: SnapshotCollected) -> None:
        """Render one worker result and then honor at most one coalesced refresh."""
        self._is_collecting = False
        if event.result.snapshot is None:
            self._show_failure(event.result)
        else:
            self._show_collected(event.result.snapshot)
        if self._is_refresh_pending:
            self._is_refresh_pending = False
            self.call_after_refresh(self._request_snapshot)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Release single-letter bindings while the typed removal phrase owns the keyboard."""
        view = self._open_view()
        is_typing = isinstance(view, InstallationView) and view.is_confirming_removal()
        return not (is_typing and action in _LETTER_ACTIONS)

    def action_move(self, offset: int) -> None:
        """Move the marker of whichever surface is currently visible."""
        view = self._open_view()
        if view is None:
            self._home().move(offset)
            return
        view.move(offset)

    def action_activate(self) -> None:
        """Open the marked menu entry, or select the command the open section shows."""
        if self._open_index is None:
            self._open_index = self._home().selected_index
            self._show_surface()
            return
        self._select_command()

    def _select_command(self) -> None:
        """Stop Textual with a visible action only after a complete current snapshot."""
        view = self._open_view()
        if view is None or not view.shows_actions():
            self._set_status("This read-only screen has no selectable action.")
            return
        if self._is_collecting or self._latest_snapshot is None:
            self._set_status("Wait for a successful local snapshot before selecting an action.")
            return
        command = view.activate()
        if command is not None:
            self.exit(TuiResult(command, self._latest_snapshot))

    def action_leave_section(self) -> None:
        """Return to the central menu, or quit when the menu is already visible."""
        view = self._open_view()
        if view is None:
            self.action_quit_workbench()
            return
        if isinstance(view, InstallationView):
            view.cancel_confirmation()
        self._open_index = None
        self._show_surface()

    def action_toggle_flag(self, key: str) -> None:
        """Switch one flag of the open section's marked action, if it binds that key."""
        view = self._open_view()
        if view is not None and view.toggle(key):
            return
        self._set_status("That key switches no flag on the marked action.")

    def action_toggle_help(self) -> None:
        """Toggle one expanded help line without opening another modal surface."""
        self._is_help_visible = not self._is_help_visible
        self.query_one("#keybar", Static).update(self._keybar_text())

    def action_scroll_detail(self, direction: int) -> None:
        """Scroll a long open section by one page in small terminals."""
        detail = self.query_one("#sections", VerticalScroll)
        if direction < 0:
            detail.scroll_page_up(animate=False)
            return
        detail.scroll_page_down(animate=False)

    def action_refresh_snapshot(self) -> None:
        """Request one serialized refresh of the shared snapshot."""
        self._request_snapshot()

    def action_quit_workbench(self) -> None:
        """Leave the presentation loop without selecting a command."""
        self.exit(TuiResult(None, self._latest_snapshot))


def run_tui(
    version: str,
    terminal_mode: TerminalMode,
    comparison_snapshot: WorkbenchSnapshot | None = None,
) -> TuiResult:
    """Run one UI lifetime and return only after Textual has restored the terminal."""
    application = WorkbenchApp(version, terminal_mode, collect_workbench_snapshot)
    application.set_comparison_snapshot(comparison_snapshot)
    result = application.run()
    return result or TuiResult(None, None)
