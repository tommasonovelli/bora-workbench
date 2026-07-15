"""CLI presentation and exit-code mapping without platform-specific branching.

Commands in this module only read input, call services, and present results. Platform logic stays in
its assigned modules as required by specification sections 4.1 and 5.11.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer
from rich.console import Console
from rich.table import Table

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


def _gib(value: float | None) -> str:
    """Format an exact GiB measurement for human diagnostics."""
    return "not applicable" if value is None else f"{value:.2f} GiB"


def _gpu_label(hardware: HardwareInfo) -> str:
    """Describe the selected GPU without implying multi-GPU launch support."""
    if hardware.gpu_index is None:
        return "none"
    return f"{hardware.gpu_name} (index {hardware.gpu_index}, detected {hardware.gpu_count})"


def _doctor_table(config: Config, hardware: HardwareInfo, profiles: int) -> Table:
    """Build the read-only Step 2B diagnostic table."""
    table = Table(title="qwen-launcher — Step 2B diagnostics")
    table.add_column("Item")
    table.add_column("Value")
    rows = [
        ("Version", package_version()),
        ("Configuration", "valid"),
        ("Model", config.model),
        ("llama.cpp port", str(config.llama_port)),
        ("OS", f"{hardware.os_name} — {hardware.os_version}"),
        ("CPU", f"{hardware.cpu_name} ({hardware.cpu_cores} logical cores)"),
        ("RAM total", _gib(hardware.ram_total_gib)),
        ("RAM available", _gib(hardware.ram_available_gib)),
        ("Backend", hardware.backend),
        ("GPU", _gpu_label(hardware)),
        ("VRAM total", _gib(hardware.vram_total_gib)),
        ("VRAM free", _gib(hardware.vram_free_gib)),
        ("Calibrated profiles", str(profiles) if profiles else "none"),
        ("Config directory", str(config_dir())),
        ("Data directory", str(data_dir())),
        ("Cache directory", str(cache_dir())),
        ("State directory", str(state_dir())),
    ]
    for label, value in rows:
        table.add_row(label, value)
    return table


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
    _stdout.print(_doctor_table(config, hardware, compatible_profiles))
    for warning in hardware.warnings:
        _stdout.print(f"[yellow]WARNING[/yellow] {warning}")
    if compatible_profiles == 0:
        message = "No calibrated profile is installed; this is expected before Step 5B."
        _stdout.print(f"[yellow]WARNING[/yellow] {message}")
    _print_validation(validation)
    if validation.errors:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
