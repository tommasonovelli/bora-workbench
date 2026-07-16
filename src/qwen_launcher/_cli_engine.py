"""Present managed-engine installation and status at the Typer command boundary."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from qwen_launcher._engine_types import EngineStatus
from qwen_launcher.engine import EngineError, engine_status, install_engine
from qwen_launcher.hardware import HardwareError, detect_hardware


def _print_status(status: EngineStatus, stdout: Console) -> None:
    """Render one already inspected managed-engine status."""
    table = Table(title="managed llama.cpp engine")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Active", "yes" if status.is_active else "no")
    table.add_row("Release", status.release or "none")
    table.add_row("Backend", status.backend or "none")
    table.add_row("Executable", str(status.executable) if status.executable else "none")
    table.add_row("Compatible", "yes" if status.is_compatible else "no")
    stdout.print(table)
    for difference in status.differences:
        stdout.print(f"[yellow]Difference:[/yellow] {difference}")


def run_engine_install(force: bool, stdout: Console, stderr: Console) -> None:
    """Detect the target backend, install it, and map expected failures to exit code 1."""
    try:
        hardware = detect_hardware()
        for warning in hardware.warnings:
            stdout.print(f"[yellow]WARNING[/yellow] {warning}")
        stdout.print(f"Installing llama.cpp for backend={hardware.backend} from engine.lock.")
        stdout.print("Third-party notices will be retained inside the managed installation.")
        if hardware.backend == "cuda":
            stdout.print("Managed Windows CUDA runtime assets are subject to the NVIDIA CUDA EULA.")
        result = install_engine(hardware.backend, force)
    except (EngineError, HardwareError) as error:
        stderr.print(f"[red]Engine installation error:[/red] {error}")
        raise typer.Exit(code=1) from error
    action = "Installed and activated" if result.was_installed else "Already active"
    stdout.print(f"[green]{action}[/green] llama.cpp {result.status.release}")
    stdout.print(f"Backend: {result.status.backend}")
    stdout.print(f"Executable: {result.status.executable}")


def show_engine_status(stdout: Console) -> None:
    """Show the active manifest, compatibility, and exact differences from the lock."""
    status = engine_status()
    _print_status(status, stdout)
    is_absent = status.differences == ("not installed",)
    if not status.is_compatible and not is_absent:
        raise typer.Exit(code=1)
