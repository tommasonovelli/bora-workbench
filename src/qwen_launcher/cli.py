"""Provide CLI presentation and exit-code mapping without platform branching (sections 4.1/5.11)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from qwen_launcher._cli_calibration import (
    CalibrationCliInput,
    CalibrationCliOutput,
    run_calibrate,
)
from qwen_launcher._cli_control import run_stop, show_status
from qwen_launcher._cli_doctor import DoctorData, build_doctor_table
from qwen_launcher._cli_engine import run_engine_install, show_engine_status
from qwen_launcher._cli_services import run_coding, run_studio, run_vstudio
from qwen_launcher._cli_validation import run_validate, show_validation
from qwen_launcher.config import Config, ConfigError, load_config
from qwen_launcher.engine import engine_status
from qwen_launcher.hardware import HardwareError, HardwareInfo, detect_hardware
from qwen_launcher.paths import cache_dir, config_dir, data_dir, state_dir
from qwen_launcher.profiles import load_catalog
from qwen_launcher.validation import validate_resources

app = typer.Typer(
    name="qwen-launcher",
    help="Launch and manage the calibrated local Qwen distribution.",
    no_args_is_help=True,
)
engine_app = typer.Typer(help="Install and inspect the pinned managed llama.cpp engine.")
app.add_typer(engine_app, name="engine")
_stdout = Console()
_stderr = Console(stderr=True)
_MEMORY_GATE_HELP = "Bypass only the default-model total and available RAM gate."


def package_version() -> str:
    """Read the installed distribution version with a source-checkout fallback."""
    try:
        return version("qwen-launcher")
    except PackageNotFoundError:
        return "0.1.0.dev0"


def _version_callback(value: bool) -> None:
    """Print the version and exit before any command runs."""
    if value:
        typer.echo(package_version())
        raise typer.Exit()


@app.callback()
def main(
    version_requested: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed package version and exit.",
    ),
) -> None:
    """qwen-launcher command group."""
    del version_requested


@app.command("validate")
def validate_command(
    path: Annotated[
        Path | None, typer.Option("--path", help="Validate a local calibration bundle.")
    ] = None,
) -> None:
    """Validate installed resources or one explicit local calibration bundle."""
    source = validate_resources() if path is None else path
    run_validate(source, _stdout, _stderr)


def _load_doctor_config() -> Config:
    """Load configuration and map expected input errors to CLI exit code 2."""
    try:
        return load_config()
    except ConfigError as error:
        _stderr.print(f"[red]Configuration error:[/red] {error}")
        raise typer.Exit(code=2) from error


def _detect_for_doctor() -> HardwareInfo:
    """Detect hardware and map missing required facts to operational exit code 1."""
    try:
        return detect_hardware()
    except HardwareError as error:
        _stderr.print(f"[red]Hardware error:[/red] {error}")
        raise typer.Exit(code=1) from error


@app.command()
def doctor() -> None:
    """Describe configuration, hardware, content, and paths without modifying the machine."""
    config = _load_doctor_config()
    hardware = _detect_for_doctor()
    validation = validate_resources()
    shared_seeds = 0
    if not validation.errors:
        catalog = load_catalog()
        shared_seeds = sum(profile.is_engine_compatible for profile in catalog.profiles)
    directories = (config_dir(), data_dir(), cache_dir(), state_dir())
    managed_engine = engine_status()
    data = DoctorData(
        config,
        hardware,
        shared_seeds,
        package_version(),
        directories,
        managed_engine,
    )
    _stdout.print(build_doctor_table(data))
    for warning in hardware.warnings:
        _stdout.print(f"[yellow]WARNING[/yellow] {warning}")
    message = "No local calibration record is installed; shared profiles are reference-only."
    _stdout.print(f"[yellow]WARNING[/yellow] {message}")
    for difference in managed_engine.differences:
        _stdout.print(f"[yellow]Engine:[/yellow] {difference}")
    show_validation(validation, _stdout, _stderr)
    if validation.errors:
        raise typer.Exit(code=1)


@engine_app.command("install")
def engine_install_command(
    force: bool = typer.Option(False, "--force", help="Reinstall an already compatible target."),
) -> None:
    """Install and atomically activate the lock-selected engine for detected hardware."""
    run_engine_install(force, _stdout, _stderr)


@engine_app.command("status")
def engine_status_command() -> None:
    """Show active managed-engine compatibility and differences from the lock."""
    show_engine_status(_stdout)


@app.command()
def coding(
    force: bool = typer.Option(False, "--force", help=_MEMORY_GATE_HELP),
) -> None:
    """Launch API-first coding mode in foreground with UI and vision explicitly disabled."""
    run_coding(force, _stdout, _stderr)


@app.command()
def studio(
    force: bool = typer.Option(False, "--force", help=_MEMORY_GATE_HELP),
) -> None:
    """Launch text chat mode with the integrated llama.cpp interface enabled."""
    run_studio(force, _stdout, _stderr)


@app.command()
def vstudio(
    force: bool = typer.Option(False, "--force", help=_MEMORY_GATE_HELP),
) -> None:
    """Launch multimodal chat with the integrated interface and pinned vision projector."""
    run_vstudio(force, _stdout, _stderr)


@app.command()
def calibrate(
    mode: Annotated[str, typer.Option("--mode", help="Packaged mode id or 'all'.")],
    candidate: Annotated[
        list[str] | None,
        typer.Option("--candidate", help="Repeat explicit ID:CTX[:N_CPU_MOE] candidates."),
    ] = None,
    settings: Annotated[
        str | None,
        typer.Option("--settings", help="Explicit RUNS[:MIN_FREE_GIB:RELEASE_TOLERANCE_GIB]."),
    ] = None,
) -> None:
    """Run gate-only calibration/v1 and generate a local unaccepted evidence bundle."""
    options = CalibrationCliInput(mode, tuple(candidate or ()), settings)
    run_calibrate(options, CalibrationCliOutput(_stdout, _stderr))


@app.command()
def status() -> None:
    """Show live managed services and clean stale state idempotently."""
    show_status(_stdout, _stderr)


@app.command()
def stop() -> None:
    """Stop only identity-verified managed services and remain idempotent when none exist."""
    run_stop(_stdout, _stderr)


if __name__ == "__main__":
    app()
