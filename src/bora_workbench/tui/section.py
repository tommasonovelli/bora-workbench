"""Lay out one centred section with actions, an exact command, and styled local facts."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.tui.actions import CommandSpec
from bora_workbench.tui.choices import ChoiceList
from bora_workbench.tui.palette import Palette

_WAITING = "Waiting for the local snapshot..."
# A body line opening with this marker is rendered as an alert instead of ordinary prose.
_ALERT_MARKER = "! "


def _column_parts(line: str) -> tuple[str, str, str] | None:
    """Split a deliberately aligned label and value while retaining their spacing."""
    for index in range(1, len(line) - 1):
        if line[index : index + 2] != "  ":
            continue
        end = index + 2
        while end < len(line) and line[end] == " ":
            end += 1
        label, value = line[:index].rstrip(), line[end:]
        if label and value:
            return label, line[len(label) : end], value
    return None


def _is_heading(line: str) -> bool:
    """Recognize short prose headings without interpreting dynamic values as markup."""
    punctuation = ".:,;=/\\()[]"
    return bool(line and len(line) <= 36 and not any(item in line for item in punctuation))


def _append_inline(text: Text, value: str, palette: Palette) -> None:
    """Accent literal backtick-delimited commands while keeping every value safe."""
    parts = value.split("`")
    for index, part in enumerate(parts):
        style = palette.command_style if index % 2 else palette.body_style
        text.append(part, style=style)


def _append_detail_line(text: Text, line: str, palette: Palette) -> None:
    """Style one alert, heading, bullet, aligned fact, or explanation with explicit contrast.

    The alert marker is tested first, and its `!` is kept, so a screen reader and a colourless
    terminal read the same warning that colour carries elsewhere (D-097).
    """
    if not line:
        return
    if line.startswith(_ALERT_MARKER):
        text.append(line, style=palette.alert_style)
        return
    if _is_heading(line):
        text.append(line, style=palette.accent_style)
        return
    if line.startswith("- "):
        text.append("- ", style=palette.accent_style)
        _append_inline(text, line[2:], palette)
        return
    columns = _column_parts(line)
    if columns is None:
        _append_inline(text, line, palette)
        return
    label, spacing, value = columns
    text.append(label, style=palette.accent_style)
    text.append(spacing)
    _append_inline(text, value, palette)


def styled_details(content: str, palette: Palette) -> Text:
    """Turn literal screen text into blue labels, white prose, and bold inline commands."""
    text = Text()
    lines = content.splitlines()
    for index, line in enumerate(lines):
        _append_detail_line(text, line, palette)
        if index < len(lines) - 1:
            text.append("\n")
    return text


class Section(Vertical):
    """Own the wider shared section chrome so screens supply only actions and facts."""

    def __init__(self, title: str, choices: ChoiceList, palette: Palette) -> None:
        """Create one hidden-until-opened section around an already-built action list."""
        super().__init__(classes="section-view")
        self._title = title
        self._choices = choices
        self._palette = palette

    def shows_actions(self) -> bool:
        """Report whether this section paints action rows; the wizard supplies its own."""
        return not self._choices.is_empty

    def compose(self) -> ComposeResult:
        """Yield a centred title and bordered action, command, and local-state panels."""
        yield Static(self._title, classes="section-title", markup=False)
        if self.shows_actions():
            yield Static(self._action_text(), classes="section-actions")
            yield Static(self._preview_text(), classes="section-preview")
        yield Static(styled_details(_WAITING, self._palette), classes="section-body")

    def _action_text(self) -> Text:
        """Render actions, guidance, and toggles with text-visible selection."""
        text = Text()
        rows = self._choices.rows()
        for position, (label, is_marked) in enumerate(rows):
            marker = f"{self._palette.marker} " if is_marked else "  "
            style = self._palette.selected_style if is_marked else self._palette.body_style
            text.append(f"{marker}{label}", style=style)
            if position < len(rows) - 1:
                text.append("\n")
        self._append_action_guidance(text)
        return text

    def _append_action_guidance(self, text: Text) -> None:
        """Add concise help and current flag states beneath the selectable rows."""
        description = self._choices.description()
        flags = self._choices.flag_row()
        if description:
            text.append("\n\nAbout  ", style=self._palette.accent_style)
            text.append(description, style=self._palette.body_style)
        if flags:
            text.append("\nFlags  ", style=self._palette.accent_style)
            text.append(flags, style=self._palette.muted_style)

    def _preview_text(self) -> Text:
        """Render the exact command in blue with a high-contrast panel label."""
        text = Text("Command  ", style=self._palette.accent_style)
        text.append(self._choices.command().display, style=self._palette.command_style)
        return text

    def refresh_actions(self) -> None:
        """Repaint action and command panels after a move or flag toggle."""
        if not self.shows_actions():
            return
        self.query_one(".section-actions", Static).update(self._action_text())
        self.query_one(".section-preview", Static).update(self._preview_text())

    def move(self, offset: int) -> None:
        """Move this section's marker without dispatching anything."""
        self._choices.move(offset)
        self.refresh_actions()

    def toggle(self, key: str) -> bool:
        """Switch one marked-action flag and report whether the key belonged here."""
        if not self._choices.toggle(key):
            return False
        self.refresh_actions()
        return True

    def activate(self) -> CommandSpec | None:
        """Return the exact command already visible beside the marker."""
        return None if self._choices.is_empty else self._choices.command()

    def show_body(self, content: str) -> None:
        """Replace the local-state panel with safely styled already-collected facts."""
        self.query_one(".section-body", Static).update(styled_details(content, self._palette))
