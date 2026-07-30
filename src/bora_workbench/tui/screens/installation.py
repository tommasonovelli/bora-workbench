"""Offer update and removal beside this installation's version and managed roots."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Input, Static

from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.actions import (
    CommandSpec,
    compose_uninstall,
    compose_update,
    compose_update_check,
)
from bora_workbench.tui.choices import Choice, ChoiceList
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section

_PHRASE = "remove"
CHOICES: tuple[Choice, ...] = (
    Choice(
        "check for a published release",
        lambda flags: compose_update_check(),
        description="Query GitHub Releases without installing or replacing anything.",
    ),
    Choice(
        "update this installation",
        lambda flags: compose_update(),
        description="Verify the newest wheel and schedule uv replacement after exit.",
    ),
    Choice(
        "uninstall Bora Workbench",
        lambda flags: compose_uninstall(),
        description="Review four managed roots before the real independent confirmations.",
    ),
)


def render_installation(snapshot: WorkbenchSnapshot) -> str:
    """Render installation identity and removal scope without probing published releases."""
    doctor = snapshot.doctor
    paths = doctor.paths
    lines = (
        "Installed release",
        f"version       {doctor.version} installed; the published version is not queried.",
        "",
        "Managed roots",
        f"config        {paths.config}",
        f"data          {paths.data}",
        f"cache         {paths.cache}",
        f"state         {paths.state}",
        "",
        "Removal boundary",
        "- `bora uninstall` removes these roots, including the managed model store.",
        "- The Python tool is removed only when uv owns this installation.",
        "- Pinned Hugging Face copies require a second, separate confirmation.",
        "- uv, pi, and user-managed model paths remain outside the boundary.",
        "- Typing `remove` only leaves this workbench; the real CLI still asks.",
    )
    return "\n".join(lines)


class InstallationView(Section):
    """Show this package and its managed roots without running update or uninstall."""

    def __init__(self, palette: Palette) -> None:
        """Create installation actions with the removal confirmation initially inactive."""
        super().__init__("This installation", ChoiceList(CHOICES), palette)
        self._is_confirming = False

    def compose(self) -> ComposeResult:
        """Yield the shared section chrome plus the typed friction that guards removal."""
        yield from super().compose()
        phrase = Input(placeholder=f"Type {_PHRASE} to continue", id="removal-phrase")
        phrase.display = False
        yield Static("", id="removal-message", markup=False)
        yield phrase

    def move(self, offset: int) -> None:
        """Keep the marker still while the typed removal confirmation owns the keyboard."""
        if not self._is_confirming:
            super().move(offset)

    def _begin_confirmation(self) -> None:
        """Reveal and focus the typed phrase without satisfying the real CLI prompts."""
        self._is_confirming = True
        phrase = self.query_one("#removal-phrase", Input)
        phrase.display = True
        phrase.focus()
        message = f"Type {_PHRASE} exactly, then press Enter; Esc returns to the menu."
        self.query_one("#removal-message", Static).update(message)

    def is_confirming_removal(self) -> bool:
        """Report whether the phrase input currently owns every printable key."""
        return self._is_confirming

    def cancel_confirmation(self) -> None:
        """Hide the typed friction again when the reader leaves this section."""
        self._is_confirming = False
        self.query_one("#removal-phrase", Input).display = False
        self.query_one("#removal-message", Static).update("")

    def activate(self) -> CommandSpec | None:
        """Require exact typed friction before returning the terminal uninstall command."""
        command = super().activate()
        if command != compose_uninstall():
            return command
        if not self._is_confirming:
            self._begin_confirmation()
            return None
        if self.query_one("#removal-phrase", Input).value != _PHRASE:
            self.query_one("#removal-message", Static).update(
                f"Phrase does not match; type {_PHRASE} exactly or press Esc."
            )
            return None
        return command

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with version, roots, and precise exclusions."""
        self.show_body(render_installation(snapshot))
