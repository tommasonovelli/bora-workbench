"""Render pi installation and shared context-window selection without reading its provider file."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.actions import CommandSpec, pi_commands, render_command_menu

_ACTIONS = pi_commands()
_HEADING = "Pi actions (Tab selects; Enter closes the TUI before running)"


def render_pi(snapshot: WorkbenchSnapshot) -> str:
    """Render only pi facts already carried by the shared non-mutating snapshot."""
    installation = snapshot.pi_installation
    executable = installation.executable or "not found on PATH"
    lines = [
        f"Available: {'yes' if installation.is_installed else 'no'}",
        f"Executable: {executable}",
        f"Provider file: {installation.models_file}",
        "Provider-file contents are not changed or inferred by this screen.",
        "Print-only and install are separate choices; contradictory flags are unreachable.",
        "Existing npm, file, backup, and confirmation behavior begins only after the TUI closes.",
    ]
    context = snapshot.pi_context
    if context is None:
        lines.extend(("", "Context window: unavailable", "Source: unavailable"))
    else:
        lines.extend(("", f"Context window: {context.tokens} tokens", f"Source: {context.source}"))
        lines.extend(f"Diagnostic: {item}" for item in context.diagnostics)
    return "\n".join(lines)


class PiView(Vertical):
    """Show the one supported pi integration without adding another agent or provider."""

    def __init__(self) -> None:
        """Create the hidden-until-selected pi region."""
        super().__init__(classes="section-view")
        self._action_index = 0

    def compose(self) -> ComposeResult:
        """Yield the title, exact valid pi commands, and literal detail body."""
        yield Static("Pi", classes="section-title", markup=False)
        yield Static(
            render_command_menu(_ACTIONS, self._action_index, _HEADING),
            classes="section-actions",
            markup=False,
        )
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def move_action(self, offset: int) -> None:
        """Move the text marker only through valid pi command forms."""
        self._action_index = (self._action_index + offset) % len(_ACTIONS)
        content = render_command_menu(_ACTIONS, self._action_index, _HEADING)
        self.query_one(".section-actions", Static).update(content)

    def selected_action(self) -> CommandSpec:
        """Return the exact valid pi command currently marked in visible text."""
        return _ACTIONS[self._action_index]

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with installation and context-source details."""
        self.query_one(".section-body", Static).update(render_pi(snapshot))
