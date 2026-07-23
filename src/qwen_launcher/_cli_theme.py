"""Shared terminal presentation: one coherent palette, glyphs, tables, and progress columns.

Every command renders its status lines, tables, and live progress through this module so the
tool reads as a single, deliberate interface rather than a set of independently styled screens.
The shared helpers apply the DRY-after-third-repetition code-quality rule. All styles are built-in
Rich style names, which keeps them correct on any console—including the theme-free
consoles that tests construct—without depending on a registered Rich theme.
"""

from __future__ import annotations

from rich.box import ROUNDED
from rich.console import Console
from rich.progress import BarColumn, ProgressColumn, SpinnerColumn, TextColumn
from rich.table import Table

# Semantic palette. Built-in Rich style names stay valid on every console, themed or not.
# Colour never carries meaning alone; a plain-text label survives when colour is stripped
# (redirected output). No decorative glyphs: they widen status lines enough to wrap and split
# tokens. A calm, cargo-style label set reads as a serious tool rather than a novelty.
STYLE_SUCCESS = "bold green"
STYLE_WARNING = "yellow"
STYLE_ERROR = "bold red"
STYLE_HEADING = "bold cyan"
STYLE_ACCENT = "cyan"
STYLE_MUTED = "dim"

# One calm spinner and one bar geometry back every live task so loading always looks the same.
_SPINNER_NAME = "dots"


def phase_result_style(is_success: bool) -> str:
    """Return the shared line style for a finished or interrupted live phase."""
    return STYLE_SUCCESS if is_success else STYLE_WARNING


def create_console(*, stderr: bool = False) -> Console:
    """Build a command console with number auto-highlighting off for a calm, uniform look."""
    return Console(stderr=stderr, highlight=False)


def status_table(title: str | None = None) -> Table:
    """Build a table with the shared box, border, header, and title styling used everywhere."""
    return Table(
        title=title,
        box=ROUNDED,
        title_style=STYLE_HEADING,
        header_style=STYLE_ACCENT,
        border_style=STYLE_MUTED,
        title_justify="left",
    )


def progress_columns(*trailing: ProgressColumn) -> tuple[ProgressColumn, ...]:
    """Build the shared spinner, description, and bar columns plus any trailing metric columns."""
    return (
        SpinnerColumn(spinner_name=_SPINNER_NAME, style=STYLE_ACCENT),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(
            bar_width=None,
            style=STYLE_MUTED,
            complete_style=STYLE_ACCENT,
            finished_style=STYLE_SUCCESS,
            pulse_style=STYLE_ACCENT,
        ),
        *trailing,
    )


def metric_column(field: str) -> TextColumn:
    """Build a muted trailing metric column bound to one named progress field."""
    return TextColumn(f"{{task.fields[{field}]}}", style=STYLE_MUTED)


def print_heading(console: Console, text: str) -> None:
    """Print a section heading in the shared heading style."""
    console.print(f"[{STYLE_HEADING}]{text}[/{STYLE_HEADING}]")


def print_success(console: Console, headline: str, detail: str = "") -> None:
    """Print a success headline in the success style, leaving detail unstyled for readability."""
    tail = f" {detail}" if detail else ""
    console.print(f"[{STYLE_SUCCESS}]{headline}[/{STYLE_SUCCESS}]{tail}")


def print_warning(console: Console, message: str) -> None:
    """Print a warning or cancellation with a text label that survives colour-stripping."""
    console.print(f"[{STYLE_WARNING}]warning:[/{STYLE_WARNING}] {message}")


def print_error(console: Console, category: str, detail: str) -> None:
    """Print an actionable error with a styled category label and unstyled detail (spec 5.11)."""
    console.print(f"[{STYLE_ERROR}]{category}:[/{STYLE_ERROR}] {detail}")


def print_note(console: Console, label: str, detail: str) -> None:
    """Print a labelled informational line with the shared accent on its label only."""
    console.print(f"[{STYLE_ACCENT}]{label}:[/{STYLE_ACCENT}] {detail}")
