"""Present complete uninstall preview, confirmation, and confined removal.

The command deletes the four managed roots and hands an exact uv-managed installation to a helper
that removes the Python tool after this process exits (specification sections 5.10-5.11).
"""

from __future__ import annotations

import typer
from rich.console import Console

from qwen_launcher._cli_theme import print_error, print_heading, print_warning
from qwen_launcher._tool_uninstall import (
    ToolInstallation,
    ToolUninstallError,
    inspect_tool_installation,
    schedule_tool_removal,
)
from qwen_launcher._uninstall import (
    ManagedRoot,
    RemovalReport,
    UninstallError,
    managed_roots,
    remove_managed_roots,
)
from qwen_launcher.process import ProcessError, status_services


def _show_preview(
    roots: tuple[ManagedRoot, ...], installation: ToolInstallation, stdout: Console
) -> None:
    """Show every managed root, the Python tool disposition, and excluded external data."""
    print_heading(stdout, "Uninstall preview")
    stdout.print("The following managed roots will be deleted after confirmation:")
    for root in roots:
        state = "present" if root.exists else "absent"
        stdout.print(f"  {root.label}: {root.path} ({state})", markup=False, soft_wrap=True)
    tool_state = "will be removed with uv" if installation.is_managed_by_uv else "not uv-managed"
    stdout.print(f"  Python tool: {installation.environment} ({tool_state})", markup=False)
    stdout.print("The Hugging Face cache and uv itself are never touched.")


def _show_report(report: RemovalReport, installation: ToolInstallation, stdout: Console) -> None:
    """Report root deletion and whether the Python tool removal was handed to uv."""
    for path in report.removed:
        stdout.print(f"Removed: {path}", markup=False, soft_wrap=True)
    for path in report.absent:
        stdout.print(f"Already absent: {path}", markup=False, soft_wrap=True)
    if installation.is_managed_by_uv:
        stdout.print("The qwen-launcher Python tool will be removed as this command exits.")
    else:
        stdout.print("Python tool unchanged: this invocation is not managed by uv tool.")


def _require_services_stopped(stderr: Console) -> None:
    """Refuse to orphan a live managed process by deleting its state (section 5.10)."""
    try:
        report = status_services()
    except ProcessError as error:
        print_error(stderr, "Uninstall error", f"cannot inspect managed services: {error}")
        raise typer.Exit(code=1) from error
    for warning in report.warnings:
        print_warning(stderr, warning)
    if report.services:
        detail = "managed services are running; run qwen-launcher stop"
        print_error(stderr, "Uninstall error", detail)
        raise typer.Exit(code=1)


def _inspect_installation(stderr: Console) -> ToolInstallation:
    """Map uv installation inspection failures to the operational CLI boundary."""
    try:
        return inspect_tool_installation()
    except ToolUninstallError as error:
        print_error(stderr, "Uninstall error", str(error))
        raise typer.Exit(code=1) from error


def _remove_everything(
    roots: tuple[ManagedRoot, ...], installation: ToolInstallation
) -> RemovalReport:
    """Delete confirmed roots, then start self-removal only after deletion succeeds."""
    try:
        report = remove_managed_roots(roots)
        schedule_tool_removal(installation)
    except (ToolUninstallError, UninstallError) as error:
        raise UninstallError(str(error)) from error
    return report


def run_uninstall(stdout: Console, stderr: Console) -> None:
    """Confirm once, then remove managed roots and the current uv-managed Python tool."""
    _require_services_stopped(stderr)
    installation = _inspect_installation(stderr)
    roots = managed_roots()
    _show_preview(roots, installation, stdout)
    if not any(root.exists for root in roots) and not installation.is_managed_by_uv:
        stdout.print("No managed installation found; nothing to remove.")
        return
    try:
        if not typer.confirm("Remove qwen-launcher completely?", default=False):
            stdout.print("Uninstall cancelled; nothing was removed.")
            return
        report = _remove_everything(roots, installation)
    except (KeyboardInterrupt, typer.Abort) as error:
        print_warning(stderr, f"Uninstall cancelled: {error}")
        raise typer.Exit(code=130) from error
    except UninstallError as error:
        print_error(stderr, "Uninstall error", str(error))
        raise typer.Exit(code=1) from error
    _show_report(report, installation, stdout)
