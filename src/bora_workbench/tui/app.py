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
    record_display_label,
)
from bora_workbench.tui.palette import stylesheet
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


def _engine_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize engine activation without hiding an incompatible installation."""
    engine = snapshot.doctor.engine
    if engine.is_compatible:
        return f"compatible {engine.release or 'managed release'} ({engine.backend or 'unknown'})"
    if engine.is_active:
        return "active but incompatible"
    return "not active"


def _model_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize model receipt state without reading or hashing model payloads."""
    model = snapshot.model
    if model is None:
        return "unavailable"
    if model.is_verified:
        return "receipt verified"
    if not model.is_managed:
        return "user managed"
    present = sum(artifact.status != "absent" for artifact in model.artifacts)
    return f"not verified ({present}/{len(model.artifacts)} copies present)"


def _record_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize every packaged mode record using the shared canonical vocabulary."""
    records = snapshot.doctor.records
    if not records:
        return "unavailable"
    labels = [f"{item.mode_id}: {record_display_label(item.evaluation.status)}" for item in records]
    return ", ".join(labels)


def _validation_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize installed-resource validation without treating warnings as errors."""
    validation = snapshot.doctor.validation
    if validation.errors:
        return f"{len(validation.errors)} error(s)"
    return f"valid with {len(validation.warnings)} warning(s)"


def _render_snapshot(snapshot: WorkbenchSnapshot) -> str:
    """Render a compact useful overview from immutable snapshot fields only."""
    doctor = snapshot.doctor
    hardware = doctor.hardware
    pi_state = "installed" if snapshot.pi_installation.is_installed else "not found on PATH"
    context = (
        "unavailable" if snapshot.pi_context is None else f"{snapshot.pi_context.tokens} tokens"
    )
    lines = (
        f"Version: {doctor.version}",
        f"Hardware: {hardware.cpu_name} / {hardware.ram_total_gib:.2f} GiB RAM",
        f"Selected backend: {hardware.backend}",
        f"Engine: {_engine_label(snapshot)}",
        f"Services: {len(snapshot.services)} running",
        f"Model: {_model_label(snapshot)}",
        f"Calibration: {_record_label(snapshot)}",
        f"pi: {pi_state}; context: {context}",
        f"Packaged content: {_validation_label(snapshot)}",
    )
    return "\n".join(lines)


def _render_failure(result: _CollectionResult) -> str:
    """Render collection failure as truth rather than retaining stale success details."""
    if result.failure is not None:
        heading = f"{result.failure.category.replace('-', ' ').title()} error"
        detail = result.failure.detail
    else:
        heading = "Snapshot collection error"
        detail = result.unexpected_detail or "unknown failure"
    return f"Snapshot unavailable\n\n{heading}\n{detail}\n\nNo local state was changed."


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
                Vertical(
                    Static("Overview", id="view-title", markup=False),
                    Static(
                        "Waiting to inspect this machine...", id="snapshot-status", markup=False
                    ),
                    Static("Local facts will appear here.", id="overview", markup=False),
                    id="content",
                ),
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
        self.query_one("#snapshot-status", Static).update(text)

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
        if event.result.snapshot is None:
            self._set_status("Inspection failed; details are current for this attempt.")
            content = _render_failure(event.result)
        else:
            self._set_status("Local snapshot ready.")
            content = _render_snapshot(event.result.snapshot)
        self.query_one("#overview", Static).update(content)
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
