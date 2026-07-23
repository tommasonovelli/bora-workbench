"""Present managed-engine installation and status at the Typer command boundary."""

from __future__ import annotations

import typer
from rich.console import Console

from qwen_launcher._cli_engine_progress import EngineInstallProgress
from qwen_launcher._cli_theme import (
    print_error,
    print_note,
    print_success,
    print_warning,
    status_table,
)
from qwen_launcher._engine_types import Backend, EngineStatus, InstallResult
from qwen_launcher.engine import EngineError, engine_status, install_engine
from qwen_launcher.hardware import HardwareError, detect_hardware


def _print_status(status: EngineStatus, stdout: Console) -> None:
    """Render one already inspected managed-engine status."""
    table = status_table("managed llama.cpp engine")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Active", "yes" if status.is_active else "no")
    table.add_row("Release", status.release or "none")
    table.add_row("Backend", status.backend or "none")
    table.add_row("Executable", str(status.executable) if status.executable else "none")
    table.add_row("Compatible", "yes" if status.is_compatible else "no")
    stdout.print(table)
    for difference in status.differences:
        print_warning(stdout, f"Difference: {difference}")


def _install_with_progress(backend: Backend, force: bool, stdout: Console) -> InstallResult:
    """Run installation with live byte progress or durable redirected phase lines."""
    with EngineInstallProgress(stdout) as progress:
        return install_engine(backend, force, progress)


def run_engine_install(force: bool, stdout: Console, stderr: Console) -> None:
    """Detect the target backend, install it, and map expected failures to exit code 1."""
    try:
        hardware = detect_hardware()
        for warning in hardware.warnings:
            print_warning(stdout, warning)
        stdout.print(f"Installing llama.cpp for backend={hardware.backend} from engine.lock.")
        stdout.print("Third-party notices will be retained inside the managed installation.")
        if hardware.backend == "cuda":
            stdout.print("Managed Windows CUDA runtime assets are subject to the NVIDIA CUDA EULA.")
        result = _install_with_progress(hardware.backend, force, stdout)
    except (EngineError, HardwareError) as error:
        print_error(stderr, "Engine installation error", str(error))
        raise typer.Exit(code=1) from error
    action = "Installed and activated" if result.was_installed else "Already active"
    print_success(stdout, action, f"llama.cpp {result.status.release}")
    print_note(stdout, "Backend", result.status.backend or "none")
    print_note(stdout, "Executable", str(result.status.executable))


def show_engine_status(stdout: Console) -> None:
    """Show the active manifest, compatibility, and exact differences from the lock."""
    status = engine_status()
    _print_status(status, stdout)
    is_absent = status.differences == ("not installed",)
    if not status.is_compatible and not is_absent:
        raise typer.Exit(code=1)
