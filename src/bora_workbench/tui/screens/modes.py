"""Render packaged modes and the active calibration cell or verified baseline each uses."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.profiles import FALLBACK_CTX
from bora_workbench.snapshot import ModeRecordSnapshot, WorkbenchSnapshot, record_display_label
from bora_workbench.tui.actions import CommandSpec, mode_commands, render_command_menu

_ACTIONS = mode_commands()
_HEADING = "Foreground modes (Tab selects; Enter closes the TUI before launch)"


def _cell(record: ModeRecordSnapshot) -> str:
    """Describe an active measured cell or the safe baseline used without one."""
    evaluation = record.evaluation
    if evaluation.status != "valid" or evaluation.ctx is None:
        return f"verified baseline: ctx {FALLBACK_CTX}"
    n_cpu_moe = "not applicable" if evaluation.n_cpu_moe is None else str(evaluation.n_cpu_moe)
    preference = evaluation.preference or "recorded preference"
    return f"active {preference} cell: ctx {evaluation.ctx}, n_cpu_moe {n_cpu_moe}"


def render_modes(snapshot: WorkbenchSnapshot) -> str:
    """Render every packaged mode in snapshot order without constructing a launch plan."""
    records = snapshot.doctor.records
    if not records:
        return "Mode details are unavailable because no trusted packaged records were collected."
    lines = [
        "Each mode uses an active local cell when valid; otherwise the verified baseline "
        "still works.",
        "--force bypasses only the default-model total and available RAM gate.",
        "The selected mode owns the foreground terminal after this TUI closes.",
    ]
    for record in records:
        status = record_display_label(record.evaluation.status)
        lines.extend(("", record.mode_id, f"Record: {status}", f"Launch cell: {_cell(record)}"))
        if record.evaluation.candidate_status == "valid":
            lines.append("Pending candidate: candidate (not active)")
    return "\n".join(lines)


class ModesView(Vertical):
    """Show mode launch facts without invoking profile selection or a mode callback."""

    def __init__(self) -> None:
        """Create the hidden-until-selected read-only mode region."""
        super().__init__(classes="section-view")
        self._action_index = 0

    def compose(self) -> ComposeResult:
        """Yield the title, exact terminal mode commands, and literal detail body."""
        yield Static("Modes", classes="section-title", markup=False)
        yield Static(
            render_command_menu(_ACTIONS, self._action_index, _HEADING),
            classes="section-actions",
            markup=False,
        )
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def move_action(self, offset: int) -> None:
        """Move the text marker through mode and force combinations."""
        self._action_index = (self._action_index + offset) % len(_ACTIONS)
        content = render_command_menu(_ACTIONS, self._action_index, _HEADING)
        self.query_one(".section-actions", Static).update(content)

    def selected_action(self) -> CommandSpec:
        """Return the exact terminal mode command currently marked in text."""
        return _ACTIONS[self._action_index]

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with cells derived only from the shared snapshot."""
        self.query_one(".section-body", Static).update(render_modes(snapshot))
