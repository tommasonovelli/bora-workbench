"""Present identity-safe status and stop operations at the CLI boundary."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from qwen_launcher.process import ProcessError, status_services, stop_services


def _print_warnings(warnings: tuple[str, ...], stdout: Console) -> None:
    """Present state cleanup warnings consistently for status and stop."""
    for warning in warnings:
        stdout.print(f"[yellow]WARNING[/yellow] {warning}")


def show_status(stdout: Console, stderr: Console) -> None:
    """Present live managed services and preserve status idempotence."""
    try:
        report = status_services()
    except ProcessError as error:
        stderr.print(f"[red]Status error:[/red] {error}")
        raise typer.Exit(code=1) from error
    _print_warnings(report.warnings, stdout)
    if not report.services:
        stdout.print("No managed services are running.")
        return
    table = Table("Service", "PID", "Mode", "Backend", "Port", "Log")
    for service in report.services:
        table.add_row(
            service.label,
            str(service.pid),
            service.mode,
            service.backend,
            str(service.port),
            service.log_path,
        )
    stdout.print(table)


def run_stop(stdout: Console, stderr: Console) -> None:
    """Present identity-safe stop results and preserve empty-state idempotence."""
    try:
        report = stop_services()
    except ProcessError as error:
        stderr.print(f"[red]Stop error:[/red] {error}")
        raise typer.Exit(code=1) from error
    _print_warnings(report.warnings, stdout)
    if report.stopped:
        stdout.print(f"Stopped: {', '.join(report.stopped)}")
    else:
        stdout.print("No managed services are running.")
