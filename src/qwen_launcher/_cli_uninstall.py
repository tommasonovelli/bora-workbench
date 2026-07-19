"""Present the uninstall preview, confirmation, and confined removal.

Step 6A requires an exact preview and an explicit confirmation before any managed root is deleted,
a reminder about removing the tool with uv, and contractual exit-code mapping (spec sections 5.11
and Step 6A).
"""

from __future__ import annotations

import typer
from rich.console import Console

from qwen_launcher._uninstall import (
    ManagedRoot,
    RemovalReport,
    UninstallError,
    managed_roots,
    remove_managed_roots,
)
from qwen_launcher.process import ProcessError, status_services

_UV_REMINDER = "To remove the qwen-launcher tool itself, run: uv tool uninstall qwen-launcher"


def _show_preview(roots: tuple[ManagedRoot, ...], stdout: Console) -> None:
    """Show the exact roots that would be deleted and the Hugging Face cache exclusion."""
    stdout.print("[bold]Uninstall preview[/bold]")
    stdout.print("The following managed roots will be deleted after confirmation:")
    for root in roots:
        state = "present" if root.exists else "absent"
        stdout.print(f"  {root.label}: {root.path} ({state})", markup=False, soft_wrap=True)
    stdout.print("The Hugging Face cache is never touched.")


def _show_report(report: RemovalReport, stdout: Console) -> None:
    """Report deleted and already-absent roots, then the tool-removal reminder."""
    for path in report.removed:
        stdout.print(f"Removed: {path}", markup=False, soft_wrap=True)
    for path in report.absent:
        stdout.print(f"Already absent: {path}", markup=False, soft_wrap=True)
    stdout.print(_UV_REMINDER)


def _perform(roots: tuple[ManagedRoot, ...], stdout: Console, stderr: Console) -> None:
    """Confirm, then delete the managed roots with contractual error mapping."""
    if not typer.confirm(
        "Delete all managed data, cache, state, and configuration?", default=False
    ):
        stdout.print("Uninstall cancelled; nothing was removed.")
        stdout.print(_UV_REMINDER)
        return
    try:
        report = remove_managed_roots(roots)
    except UninstallError as error:
        stderr.print(f"[red]Uninstall error:[/red] {error}")
        raise typer.Exit(code=1) from error
    _show_report(report, stdout)


def _require_services_stopped(stderr: Console) -> None:
    """Refuse to orphan a live managed process by deleting its state (Step 6A)."""
    try:
        report = status_services()
    except ProcessError as error:
        stderr.print(f"[red]Uninstall error:[/red] cannot inspect managed services: {error}")
        raise typer.Exit(code=1) from error
    for warning in report.warnings:
        stderr.print(f"[yellow]WARNING[/yellow] {warning}")
    if report.services:
        stderr.print(
            "[red]Uninstall error:[/red] managed services are running; run qwen-launcher stop"
        )
        raise typer.Exit(code=1)


def run_uninstall(stdout: Console, stderr: Console) -> None:
    """Preview managed roots and, after confirmation, delete them; stay idempotent when absent."""
    _require_services_stopped(stderr)
    roots = managed_roots()
    _show_preview(roots, stdout)
    if not any(root.exists for root in roots):
        stdout.print("No managed data found; nothing to remove.")
        stdout.print(_UV_REMINDER)
        return
    try:
        _perform(roots, stdout, stderr)
    except (KeyboardInterrupt, typer.Abort) as error:
        stderr.print(f"[yellow]Uninstall cancelled:[/yellow] {error}")
        raise typer.Exit(code=130) from error
