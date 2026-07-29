"""Render installed version, managed roots, and the exact current removal boundary."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Static

from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.actions import (
    CommandSpec,
    compose_uninstall,
    installation_commands,
    render_command_menu,
)

_ACTIONS = installation_commands()
_HEADING = "Installation actions (Tab selects; Enter closes the TUI before running)"


def render_installation(snapshot: WorkbenchSnapshot) -> str:
    """Render installation identity and removal scope without probing published releases."""
    doctor = snapshot.doctor
    paths = doctor.paths
    lines = (
        f"Installed version: {doctor.version}",
        "Published version: not queried; bora update --check is the explicit network action.",
        "The TUI closes before update performs network or uv work.",
        "Update and uninstall are terminal; update --check returns on success.",
        "",
        "Managed roots",
        f"Configuration: {paths.config}",
        f"Data: {paths.data}",
        f"Cache: {paths.cache}",
        f"State: {paths.state}",
        "",
        "Removal boundary",
        "bora uninstall confirms these roots and removes the Python tool only when uv-managed.",
        "The data root includes bora's managed model store.",
        "Typing remove only leaves this TUI; the real CLI still asks its root confirmation.",
        "Pinned Hugging Face cache copies require a second, separate confirmation.",
        "uv itself, pi, unrelated cache content, and user-managed model paths stay untouched.",
    )
    return "\n".join(lines)


class InstallationView(Vertical):
    """Show this package and its managed roots without running update or uninstall."""

    def __init__(self) -> None:
        """Create installation actions with uninstall confirmation initially inactive."""
        super().__init__(classes="section-view")
        self._action_index = 0
        self._is_confirming = False

    def compose(self) -> ComposeResult:
        """Yield title, exact commands, typed friction, and literal installation detail."""
        phrase = Input(placeholder="Type remove to continue", id="removal-phrase")
        phrase.display = False
        yield Static("This installation", classes="section-title", markup=False)
        yield Static(
            render_command_menu(_ACTIONS, self._action_index, _HEADING),
            classes="section-actions",
            markup=False,
        )
        yield Static("", id="removal-message", markup=False)
        yield phrase
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def move_action(self, offset: int) -> None:
        """Move through check, update, and uninstall while confirmation is inactive."""
        if self._is_confirming:
            return
        self._action_index = (self._action_index + offset) % len(_ACTIONS)
        content = render_command_menu(_ACTIONS, self._action_index, _HEADING)
        self.query_one(".section-actions", Static).update(content)

    def selected_action(self) -> CommandSpec:
        """Return the exact installation command currently marked in visible text."""
        return _ACTIONS[self._action_index]

    def _begin_uninstall_confirmation(self) -> None:
        """Reveal and focus the typed phrase without satisfying the real CLI prompts."""
        self._is_confirming = True
        phrase = self.query_one("#removal-phrase", Input)
        phrase.display = True
        phrase.focus()
        message = "Type remove exactly, then press Enter; Esc or Ctrl+Q cancels the TUI."
        self.query_one("#removal-message", Static).update(message)

    def review_action(self) -> CommandSpec | None:
        """Require exact typed friction before returning terminal uninstall."""
        command = self.selected_action()
        if command != compose_uninstall():
            return command
        if not self._is_confirming:
            self._begin_uninstall_confirmation()
            return None
        phrase = self.query_one("#removal-phrase", Input).value
        if phrase != "remove":
            self.query_one("#removal-message", Static).update(
                "Phrase does not match; type remove exactly or cancel."
            )
            return None
        return command

    def accept_bound_key(self, key: str) -> bool:
        """Insert r into the focused phrase instead of triggering a snapshot refresh."""
        phrase = self.query_one("#removal-phrase", Input)
        if not self._is_confirming or not phrase.has_focus:
            return False
        phrase.insert_text_at_cursor(key)
        return True

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with version, roots, and precise exclusions."""
        self.query_one(".section-body", Static).update(render_installation(snapshot))
