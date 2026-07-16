"""CLI presentation and exit-code mapping without platform-specific branching.

Commands in this module only read input, call services, and present results. Platform logic stays in
its assigned modules as required by specification sections 4.1 and 5.11.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer
from rich.console import Console

from qwen_launcher._cli_doctor import DoctorData, build_doctor_table
from qwen_launcher._cli_services import run_coding, run_stop, show_status
from qwen_launcher.config import Config, ConfigError, load_config
from qwen_launcher.hardware import HardwareError, HardwareInfo, detect_hardware
from qwen_launcher.paths import cache_dir, config_dir, data_dir, state_dir
from qwen_launcher.profiles import load_catalog
from qwen_launcher.validation import ValidationIssue, ValidationResult, validate_resources

app = typer.Typer(
    name="qwen-launcher",
    help="Launch and manage the calibrated local Qwen distribution.",
    no_args_is_help=True,
)
_stdout = Console()
_stderr = Console(stderr=True)


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


def _print_issue(item: ValidationIssue) -> None:
    """Print one validation issue to the stream appropriate for its severity."""
    label = f"{item.file}:{item.field_path}: {item.message}"
    if item.severity == "error":
        _stderr.print(f"[red]ERROR[/red] {label}")
    else:
        _stdout.print(f"[yellow]WARNING[/yellow] {label}")


def _print_validation(result: ValidationResult) -> None:
    """Print deterministic validation details and a concise summary."""
    for item in result.issues:
        _print_issue(item)
    if result.errors:
        _stderr.print(f"[red]Validation failed:[/red] {len(result.errors)} error(s)")
    else:
        _stdout.print(f"[green]Validation passed[/green] with {len(result.warnings)} warning(s)")


@app.command("validate")
def validate_command() -> None:
    """Validate installed schemas, content references, evidence, and engine compatibility."""
    result = validate_resources()
    _print_validation(result)
    if result.errors:
        raise typer.Exit(code=1)


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
    compatible_profiles = 0
    if not validation.errors:
        catalog = load_catalog()
        compatible_profiles = sum(profile.is_engine_compatible for profile in catalog.profiles)
    directories = (config_dir(), data_dir(), cache_dir(), state_dir())
    data = DoctorData(config, hardware, compatible_profiles, package_version(), directories)
    _stdout.print(build_doctor_table(data))
    for warning in hardware.warnings:
        _stdout.print(f"[yellow]WARNING[/yellow] {warning}")
    if compatible_profiles == 0:
        message = "No calibrated profile is installed; this is expected before Step 5B."
        _stdout.print(f"[yellow]WARNING[/yellow] {message}")
    _print_validation(validation)
    if validation.errors:
        raise typer.Exit(code=1)


@app.command()
def coding(
    force: bool = typer.Option(
        False, "--force", help="Bypass only the default-model total and available RAM gate."
    ),
) -> None:
    """Launch API-first coding mode in foreground with UI and vision explicitly disabled."""
    run_coding(force, _stdout, _stderr)


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
