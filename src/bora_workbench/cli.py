"""Provide CLI presentation and exit-code mapping without platform branching (sections 4.1/5.11)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

import typer

from bora_workbench._cli_calibration import parse_calibration_input, run_calibrate
from bora_workbench._cli_diagnostics import (
    EngineInstallOptions,
    run_doctor,
    run_engine_install,
    run_validate,
    show_engine_status,
)
from bora_workbench._cli_models import RemoveOptions, run_pull, run_remove_model
from bora_workbench._cli_pi import PiOptions, run_pi, run_pi_removal, run_pi_uninstall
from bora_workbench._cli_services import (
    run_coding,
    run_stop,
    run_studio,
    run_uninstall,
    run_vstudio,
    show_status,
)
from bora_workbench._cli_theme import create_console, print_error
from bora_workbench._cli_update import UpdateOptions, run_update
from bora_workbench.calibration import CalibrationError

app = typer.Typer(
    name="bora-workbench",
    help="Launch and manage the calibrated local Qwen distribution.",
    no_args_is_help=True,
)
engine_app = typer.Typer(help="Install and inspect the pinned managed llama.cpp engine.")
app.add_typer(engine_app, name="engine")
# `bora pi` keeps connecting when it is called with no subcommand, so the two ways of undoing that
# connection can be commands of their own instead of a fifth flag on one overloaded command.
pi_app = typer.Typer(
    help="Connect the pi coding agent to this machine's bora service, or take it back.",
    invoke_without_command=True,
)
app.add_typer(pi_app, name="pi")
_stdout = create_console()
_stderr = create_console(stderr=True)
_MEMORY_GATE_HELP = "Bypass only the default-model total and available RAM gate."
_MODEL_HELP = "Pinned model to act on. Optional: this distribution pins only 'qwen'."
_CALIBRATION_EPILOG = (
    "Extras: --no-activate keeps the measured candidates without replacing the active records; "
    "--activate promotes candidates measured earlier without measuring again; --target-ctx N "
    "searches only one of 131072, 98304, 65536, 49152, 32768. "
    "Extras are parsed strictly after Typer's common options."
)


def package_version() -> str:
    """Read the installed distribution version with a source-checkout fallback."""
    try:
        return version("bora-workbench")
    except PackageNotFoundError:
        return "0.3.2"


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
    """bora-workbench command group."""
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
    no_model: bool = typer.Option(
        False, "--no-model", help="Install only the engine, without downloading the weights."
    ),
) -> None:
    """Install the engine for detected hardware and download the pinned model."""
    run_engine_install(EngineInstallOptions(force, not no_model), _stdout, _stderr)


@app.command()
def pull(model: Annotated[str | None, typer.Argument(help=_MODEL_HELP)] = None) -> None:
    """Download the pinned model into the managed store and verify it against engine.lock."""
    run_pull(model, _stdout, _stderr)


@app.command("rm")
def remove_model_command(
    model: Annotated[str | None, typer.Argument(help=_MODEL_HELP)] = None,
    keep_cache: bool = typer.Option(
        False, "--keep-hf", help="Leave copies in the shared Hugging Face cache untouched."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List what would be deleted without deleting anything."
    ),
) -> None:
    """Delete the pinned model from the managed store, and from the cache when confirmed."""
    run_remove_model(RemoveOptions(model, keep_cache, dry_run), _stdout, _stderr)


@pi_app.callback()
def pi(
    context: typer.Context,
    print_only: bool = typer.Option(
        False, "--print", help="Print the provider entry instead of writing it."
    ),
    install: bool = typer.Option(
        False, "--install", help="Install pi with npm when it is not on PATH."
    ),
) -> None:
    """Point the pi coding agent at this machine's bora service."""
    if context.invoked_subcommand is None:
        run_pi(PiOptions(print_only, install), _stdout, _stderr)


@pi_app.command("remove")
def pi_remove_command() -> None:
    """Delete the provider entry `bora pi` writes, leaving pi itself installed."""
    run_pi_removal(_stdout, _stderr)


@pi_app.command("uninstall")
def pi_uninstall_command() -> None:
    """Uninstall pi itself with npm, then ask separately about the provider entry."""
    run_pi_uninstall(_stdout, _stderr)


@engine_app.command("status")
def engine_status_command() -> None:
    """Show active managed-engine compatibility and differences from the lock."""
    show_engine_status(_stdout, _stderr)


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
            help="Optimization rule to measure: fast, balanced (default), max-context.",
        ),
    ] = None,
) -> None:
    """Measure one launch cell for one packaged mode or for all of them."""
    try:
        options = parse_calibration_input(mode, preference, context.args)
    except CalibrationError as error:
        print_error(_stderr, "Calibration input error", str(error))
        raise typer.Exit(code=2) from error
    run_calibrate(options, _stdout, _stderr)


@app.command()
def status() -> None:
    """Show live managed services and clean stale state idempotently."""
    show_status(_stdout, _stderr)


@app.command()
def stop() -> None:
    """Stop only identity-verified managed services and remain idempotent when none exist."""
    run_stop(_stdout, _stderr)


@app.command()
def update(
    check: bool = typer.Option(
        False, "--check", help="Only report whether a newer release is published."
    ),
) -> None:
    """Install the newest published release with uv, leaving the managed engine installed."""
    run_update(UpdateOptions(package_version(), check), _stdout, _stderr)


@app.command()
def uninstall() -> None:
    """Remove managed roots and the current uv-managed Python tool after one confirmation."""
    run_uninstall(_stdout, _stderr)


if __name__ == "__main__":
    app()
