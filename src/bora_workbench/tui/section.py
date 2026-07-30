"""Lay out one full-window section with its actions, its exact command, and short facts."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.tui.actions import CommandSpec
from bora_workbench.tui.choices import ChoiceList
from bora_workbench.tui.palette import Palette

_WAITING = "Waiting for the local snapshot..."


class Section(Vertical):
    """Own the chrome every section shares so screens only supply their own facts."""

    def __init__(self, title: str, choices: ChoiceList, palette: Palette) -> None:
        """Create one hidden-until-opened section around its already-built action list."""
        super().__init__(classes="section-view")
        self._title = title
        self._choices = choices
        self._palette = palette

    def shows_actions(self) -> bool:
        """Report whether this section paints action rows; the wizard supplies its own."""
        return not self._choices.is_empty

    def compose(self) -> ComposeResult:
        """Yield the title, the action rows, the exact command, and the literal detail body."""
        yield Static(self._title, classes="section-title", markup=False)
        if self.shows_actions():
            yield Static(self._action_text(), classes="section-actions")
            yield Static(self._preview_text(), classes="section-preview")
        yield Static(_WAITING, classes="section-body", markup=False)

    def _action_text(self) -> Text:
        """Render action rows with a text marker so selection never depends on colour."""
        text = Text()
        rows = self._choices.rows()
        for position, (label, is_marked) in enumerate(rows):
            marker = f"{self._palette.marker} " if is_marked else "  "
            style = self._palette.selected_style if is_marked else ""
            text.append(f"{marker}{label}", style=style)
            if position < len(rows) - 1:
                text.append("\n")
        flags = self._choices.flag_row()
        if flags:
            text.append(f"\n\n  {flags}", style=self._palette.muted_style)
        return text

    def _preview_text(self) -> Text:
        """Render the exact command that Enter would select for the marked action."""
        return Text(f"  {self._choices.command().display}", style=self._palette.accent_style)

    def refresh_actions(self) -> None:
        """Repaint the action rows and the command preview after a move or a toggle."""
        if not self.shows_actions():
            return
        self.query_one(".section-actions", Static).update(self._action_text())
        self.query_one(".section-preview", Static).update(self._preview_text())

    def move(self, offset: int) -> None:
        """Move this section's own marker without dispatching anything."""
        self._choices.move(offset)
        self.refresh_actions()

    def toggle(self, key: str) -> bool:
        """Switch one flag of the marked action and report whether the key belonged here."""
        if not self._choices.toggle(key):
            return False
        self.refresh_actions()
        return True

    def activate(self) -> CommandSpec | None:
        """Return the exact command already visible beside the marker."""
        return None if self._choices.is_empty else self._choices.command()

    def show_body(self, content: str) -> None:
        """Replace the literal detail body with already collected local facts."""
        self.query_one(".section-body", Static).update(content)
