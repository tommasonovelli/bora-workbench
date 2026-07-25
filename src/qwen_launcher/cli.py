"""Provide CLI presentation and exit-code mapping without platform branching (sections 4.1/5.11)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

import typer

from qwen_launcher._cli_calibration import (
    CalibrationCliInput,
    CalibrationCliOutput,
    run_calibrate,
)
from qwen_launcher._cli_calibration_options import parse_calibration_options
from qwen_launcher._cli_control import run_stop, show_status
from qwen_launcher._cli_doctor import run_doctor
from qwen_launcher._cli_engine import run_engine_install, show_engine_status
from qwen_launcher._cli_services import run_coding, run_studio, run_vstudio
from qwen_launcher._cli_theme import create_console, print_error
from qwen_launcher._cli_uninstall import run_uninstall
from qwen_launcher._cli_validation import run_validate
from qwen_launcher.calibration import CalibrationError

app = typer.Typer(
    name="qwen-launcher",
    help="Launch and manage the calibrated local Qwen distribution.",
    no_args_is_help=True,
)
engine_app = typer.Typer(help="Install and inspect the pinned managed llama.cpp engine.")
app.add_typer(engine_app, name="engine")
_stdout = create_console()
_stderr = create_console(stderr=True)
_MEMORY_GATE_HELP = "Bypass only the default-model total and available RAM gate."
_CALIBRATION_EPILOG = (
    "Extras: --no-activate keeps the measured candidates without replacing the active records; "
    "--activate promotes candidates measured earlier without measuring again; --target-ctx N "
    "searches only one of 131072, 98304, 65536, 49152, 32768, 16384, 8192. "
    "Extras are parsed strictly after Typer's common options."
)


def package_version() -> str:
    """Read the installed distribution version with a source-checkout fallback."""
    try:
        return version("qwen-launcher")
    except PackageNotFoundError:
        return "0.1.5"


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
def validate_command() -> None:
    """Validate the installed modes, policy, and reference calibration content."""
    run_validate(_stdout, _stderr)


@app.command()
def doctor() -> None:
    """Describe configuration, hardware, content, records, and paths without modifying anything."""
    run_doctor(package_version(), _stdout, _stderr)


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


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    epilog=_CALIBRATION_EPILOG,
)
def calibrate(
    context: typer.Context,
    mode: Annotated[str, typer.Option("--mode", help="Packaged mode id or 'all'.")],
    preference: Annotated[
        str | None,
        typer.Option(
            "--preference",
            help="Launch envelope written to the record: fast, balanced (default), max-context.",
        ),
    ] = None,
) -> None:
    """Measure the launch envelopes of one packaged mode or of all of them."""
    try:
        parsed = parse_calibration_options(context.args)
    except CalibrationError as error:
        print_error(_stderr, "Calibration input error", str(error))
        raise typer.Exit(code=2) from error
    options = CalibrationCliInput(
        mode,
        parsed.no_activate,
        parsed.activate,
        parsed.target_ctx,
        preference,
    )
    run_calibrate(options, CalibrationCliOutput(_stdout, _stderr))


@app.command()
def status() -> None:
    """Show live managed services and clean stale state idempotently."""
    show_status(_stdout, _stderr)


@app.command()
def stop() -> None:
    """Stop only identity-verified managed services and remain idempotent when none exist."""
    run_stop(_stdout, _stderr)


@app.command()
def uninstall() -> None:
    """Remove managed roots and the current uv-managed Python tool after one confirmation."""
    run_uninstall(_stdout, _stderr)


if __name__ == "__main__":
    app()
