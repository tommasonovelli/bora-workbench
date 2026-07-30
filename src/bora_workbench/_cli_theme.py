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
from time import monotonic

from rich.box import ROUNDED
from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, SpinnerColumn, TaskID, TextColumn
from rich.table import Table
from rich.text import Text

from bora_workbench._engine_assets import TransferProgress, TransferProgressCallback
from bora_workbench._model_verification import VerifyProgress

# Semantic palette. Built-in Rich style names stay valid on every console, themed or not.
# Blue and white establish the product identity while warning/error labels retain distinct
# semantics. Every label survives when redirected output strips colour.
STYLE_SUCCESS = "bold bright_blue"
STYLE_WARNING = "bold yellow"
STYLE_ERROR = "bold red"
STYLE_HEADING = "bold bright_blue"
STYLE_ACCENT = "bold bright_blue"
STYLE_BODY = "white"
STYLE_MUTED = "dim white"

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
        header_style=f"bold {STYLE_BODY}",
        border_style=STYLE_ACCENT,
        title_justify="left",
        row_styles=(STYLE_BODY,),
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


def format_bytes(size: float) -> str:
    """Format transfer bytes with compact binary units."""
    units = ("B", "KiB", "MiB", "GiB")
    value = max(0.0, size)
    for unit in units[:-1]:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {units[-1]}"


def format_duration(seconds: float) -> str:
    """Format a short transfer estimate without implying subsecond precision."""
    rounded = max(0, round(seconds))
    minutes, remaining_seconds = divmod(rounded, 60)
    if minutes:
        return f"{minutes}m {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


def _transfer_fields(update: TransferProgress, elapsed: float) -> tuple[str, str]:
    """Describe how much has arrived, how fast, and how long the remainder should take."""
    amount = format_bytes(update.completed_bytes)
    if update.total_bytes is not None:
        amount = f"{amount}/{format_bytes(update.total_bytes)}"
    if update.is_cached:
        return f"{amount} · already verified", ""
    if elapsed <= 0 or update.completed_bytes <= 0:
        return amount, "ETA learning…" if update.total_bytes else ""
    rate = update.completed_bytes / elapsed
    metrics = f"{amount} · {format_bytes(rate)}/s"
    if update.total_bytes is None:
        return metrics, ""
    remaining = max(0, update.total_bytes - update.completed_bytes) / rate
    return metrics, f"ETA ~ {format_duration(remaining)}"


@contextmanager
def transferring(console: Console, description: str) -> Iterator[TransferProgressCallback]:
    """Show one transfer's position, rate, and estimate, and stay silent when not on a terminal.

    A multi-gigabyte download has to look alive, but redirected output must not receive thousands
    of refresh lines, so the bar exists only on an interactive console. It is created on the first
    reported chunk, which leaves the terminal untouched when nothing had to be transferred.
    """
    progress = Progress(
        *progress_columns(metric_column("metrics"), metric_column("eta")),
        console=console,
        refresh_per_second=4,
        transient=True,
    )
    started = monotonic()
    task: TaskID | None = None

    def report(update: TransferProgress) -> None:
        """Start the bar on the first reported chunk and advance it to the measured position."""
        nonlocal task
        if not console.is_terminal:
            return
        if task is None:
            progress.start()
            task = progress.add_task(description, total=update.total_bytes, metrics="", eta="")
        metrics, eta = _transfer_fields(update, monotonic() - started)
        progress.update(
            task,
            completed=update.completed_bytes,
            total=update.total_bytes,
            metrics=metrics,
            eta=eta,
        )

    try:
        yield report
    finally:
        if task is not None:
            progress.stop()


def print_heading(console: Console, text: str) -> None:
    """Print a section heading without interpreting dynamic text as Rich markup."""
    console.print(Text(text, style=STYLE_HEADING))


def print_success(console: Console, headline: str, detail: str = "") -> None:
    """Print a styled success headline followed by an optional literal detail."""
    line = Text(headline, style=STYLE_SUCCESS)
    if detail:
        line.append(f" {detail}", style=STYLE_BODY)
    console.print(line)


def print_warning(console: Console, message: str) -> None:
    """Print a warning label and literal message that remain meaningful without colour."""
    console.print(Text.assemble(("warning:", STYLE_WARNING), (f" {message}", STYLE_BODY)))


def print_error(console: Console, category: str, detail: str) -> None:
    """Print an actionable error while preserving literal details (specification section 5.11)."""
    console.print(Text.assemble((f"{category}:", STYLE_ERROR), (f" {detail}", STYLE_BODY)))


def print_note(console: Console, label: str, detail: str) -> None:
    """Print a blue informational label followed by literal high-contrast detail."""
    console.print(Text.assemble((f"{label}:", STYLE_ACCENT), (f" {detail}", STYLE_BODY)))
