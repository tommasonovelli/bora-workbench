"""Shared terminal presentation: one coherent palette, glyphs, tables, and progress columns.

Every command renders its status lines, tables, and live progress through this module so the
tool reads as a single, deliberate interface rather than a set of independently styled screens.
The shared helpers apply the DRY-after-third-repetition code-quality rule. All styles are built-in
Rich style names, which keeps them correct on any console—including the theme-free
consoles that tests construct—without depending on a registered Rich theme.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from rich.box import ROUNDED
from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, SpinnerColumn, TaskID, TextColumn
from rich.table import Table
from rich.text import Text

from bora_workbench._model_verification import VerifyProgress

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


@contextmanager
def verifying_model(console: Console) -> Iterator[VerifyProgress]:
    """Show how far a full model verification has read, and print nothing when it is skipped.

    A verification with no receipt reads about 22 GiB before any other output appears, which is
    long enough to read as a hung command. The bar is created on the first reported chunk, so a
    receipt hit leaves the terminal exactly as it was (D-076).
    """
    progress = Progress(*progress_columns(metric_column("read")), console=console, transient=True)
    task: TaskID | None = None

    def report(completed: int, total: int) -> None:
        """Start the bar on the first chunk and advance it to the reported position."""
        nonlocal task
        if task is None:
            progress.start()
            task = progress.add_task("Verifying model integrity", total=total, read="")
        progress.update(
            task, completed=completed, total=total, read=_read_fraction(completed, total)
        )

    try:
        yield report
    finally:
        if task is not None:
            progress.stop()


def _read_fraction(completed: int, total: int) -> str:
    """Describe verification position in whole GiB, the only unit these artifacts need."""
    gib = 1024**3
    return f"{completed / gib:.1f}/{total / gib:.1f} GiB"


def print_heading(console: Console, text: str) -> None:
    """Print a section heading without interpreting dynamic text as Rich markup."""
    console.print(Text(text, style=STYLE_HEADING))


def print_success(console: Console, headline: str, detail: str = "") -> None:
    """Print a styled success headline followed by an optional literal detail."""
    line = Text(headline, style=STYLE_SUCCESS)
    if detail:
        line.append(f" {detail}")
    console.print(line)


def print_warning(console: Console, message: str) -> None:
    """Print a warning label and literal message that remain meaningful without colour."""
    console.print(Text.assemble(("warning:", STYLE_WARNING), " ", message))


def print_error(console: Console, category: str, detail: str) -> None:
    """Print an actionable error while preserving literal details (specification section 5.11)."""
    console.print(Text.assemble((f"{category}:", STYLE_ERROR), " ", detail))


def print_note(console: Console, label: str, detail: str) -> None:
    """Print a styled informational label followed by a literal detail."""
    console.print(Text.assemble((f"{label}:", STYLE_ACCENT), " ", detail))
