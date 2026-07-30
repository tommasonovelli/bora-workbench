"""Provide CLI presentation and exit-code mapping without platform branching (sections 4.1/5.11)."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Annotated

import typer
from typer.main import get_command

from bora_workbench._cli_calibration import CalibrationCliInput, run_calibrate
from bora_workbench._cli_diagnostics import (
    EngineInstallOptions,
    run_doctor,
    run_engine_install,
    run_validate,
    show_engine_status,
)
from bora_workbench._cli_models import RemoveOptions, run_pull, run_remove_model
from bora_workbench._cli_pi import (
    PiOptions,
    run_pi,
    run_pi_launch,
    run_pi_removal,
    run_pi_uninstall,
    validate_pi_options,
)
from bora_workbench._cli_services import (
    run_coding,
    run_stop,
    run_studio,
    run_uninstall,
    run_vstudio,
    show_status,
)
from bora_workbench._cli_theme import create_console, print_note
from bora_workbench._cli_update import UpdateOptions, run_update
from bora_workbench._cli_webui import run_webui_install, run_webui_removal, show_webui_status

if TYPE_CHECKING:
    from bora_workbench.tui.terminal import TerminalMode

app = typer.Typer(
    name="bora-workbench",
    help="Open the workbench, or launch and manage the calibrated local Qwen distribution.",
    invoke_without_command=True,
    no_args_is_help=False,
)
engine_app = typer.Typer(help="Install and inspect the pinned managed llama.cpp engine.")
app.add_typer(engine_app, name="engine")
webui_app = typer.Typer(help="Install and inspect the managed Open WebUI interface.")
app.add_typer(webui_app, name="webui")
# `bora pi` keeps connecting when it is called with no subcommand, so the two ways of undoing that
# connection can be commands of their own instead of a fifth flag on one overloaded command.
pi_app = typer.Typer(
    help="Connect or launch pi with this machine's bora service, or take it back.",
    invoke_without_command=True,
)
app.add_typer(pi_app, name="pi")
_stdout = create_console()
_stderr = create_console(stderr=True)
_MEMORY_GATE_HELP = "Bypass only the default-model total and available RAM gate."
_MODEL_HELP = "Pinned model to act on. Optional: this distribution pins only 'qwen'."


def package_version() -> str:
    """Read the installed distribution version with a source-checkout fallback."""
    try:
        return version("bora-workbench")
    except PackageNotFoundError:
        return "0.5.1"


def _dispatch_tui_arguments(arguments: tuple[str, ...]) -> int:
    """Invoke one recursively parsed CLI leaf in this process after Textual has stopped."""
    command = get_command(app)
    try:
        result = command.main(args=list(arguments), prog_name="bora", standalone_mode=False)
    except typer.Abort:
        return 130
    return 0 if result is None else int(result)


def _version_callback(value: bool) -> None:
    """Print the version and exit before any command runs."""
    if value:
        typer.echo(package_version())
        raise typer.Exit()


@app.callback()
def main(
    context: typer.Context,
    version_requested: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed package version and exit.",
    ),
    plain: bool = typer.Option(
        False, "--plain", help="Use the reduced monochrome workbench presentation."
    ),
) -> None:
    """Open the workbench when no explicit CLI command was selected."""
    del version_requested
    if context.invoked_subcommand is None:
        _run_workbench(plain)
        return
    if plain:
        raise typer.BadParameter("--plain is available only when opening bare bora")


@app.command("validate")
def validate_command() -> None:
    """Validate the installed modes, policy, and reference calibration content."""
    run_validate(_stdout, _stderr)


@app.command()
def doctor() -> None:
    """Describe configuration, hardware, content, records, and paths without modifying anything."""
    run_doctor(package_version(), _stdout, _stderr)


def _inspect_workbench_terminal(is_plain: bool) -> TerminalMode:
    """Validate workbench presentation capabilities before importing Textual."""
    from bora_workbench.tui.motion import MotionConfigurationError
    from bora_workbench.tui.terminal import inspect_terminal

    try:
        terminal_mode = inspect_terminal(is_plain)
    except MotionConfigurationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    if not terminal_mode.is_interactive:
        typer.echo("bare bora requires interactive stdin and stdout terminals.", err=True)
        raise typer.Exit(2)
    return terminal_mode


def _pause_before_workbench_return() -> None:
    """Keep successful command output visible until an interactive user presses Enter."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return
    try:
        input("Press Enter to return to Bora Workbench. ")
    except (EOFError, KeyboardInterrupt) as error:
        raise typer.Exit(130) from error


def _run_workbench(is_plain: bool) -> None:
    """Run TUI lifetimes and dispatch selected callbacks after each complete teardown."""
    terminal_mode = _inspect_workbench_terminal(is_plain)
    # Textual stays outside non-TTY and ordinary CLI startup paths by design (D-086).
    from bora_workbench.tui.app import run_tui

    comparison_snapshot = None
    while True:
        result = run_tui(package_version(), terminal_mode, comparison_snapshot)
        if result.command is None:
            return
        print_note(_stdout, "Command", result.command.display)
        exit_code = _dispatch_tui_arguments(result.command.cli_arguments)
        if exit_code != 0 or result.command.disposition == "terminal":
            raise typer.Exit(exit_code)
        _pause_before_workbench_return()
        comparison_snapshot = result.snapshot


@engine_app.command("install")
def engine_install_command(
    force: bool = typer.Option(False, "--force", help="Reinstall an already compatible target."),
    no_model: bool = typer.Option(
        False, "--no-model", help="Install only the engine, without downloading the weights."
    ),
    no_webui: bool = typer.Option(
        False, "--no-webui", help="Skip Open WebUI and keep the integrated llama.cpp interface."
    ),
) -> None:
    """Install the engine for detected hardware, the pinned model, and the browser interface."""
    options = EngineInstallOptions(force, not no_model, not no_webui)
    run_engine_install(options, _stdout, _stderr)


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
    options = PiOptions(print_only, install)
    validate_pi_options(options, context.invoked_subcommand)
    if context.invoked_subcommand is None:
        run_pi(options, _stdout, _stderr)


@pi_app.command("launch")
def pi_launch_command() -> None:
    """Launch pi with the bora provider and the exact model alias selected."""
    run_pi_launch(_stdout, _stderr)


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


@webui_app.command("install")
def webui_install_command(
    force: bool = typer.Option(False, "--force", help="Rebuild an already installed environment."),
) -> None:
    """Install the pinned Open WebUI so studio and vstudio open it instead of the built-in UI."""
    run_webui_install(force, _stdout, _stderr)


@webui_app.command("status")
def webui_status_command() -> None:
    """Show whether the managed Open WebUI is installed, and where its data lives."""
    show_webui_status(_stdout, _stderr)


@webui_app.command("remove")
def webui_remove_command() -> None:
    """Remove the managed Open WebUI, asking about its environment and your chats separately."""
    run_webui_removal(_stdout, _stderr)


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
    """Launch text chat mode, opening Open WebUI when installed and the built-in UI otherwise."""
    run_studio(force, _stdout, _stderr)


@app.command()
def vstudio(
    force: bool = typer.Option(False, "--force", help=_MEMORY_GATE_HELP),
) -> None:
    """Launch multimodal chat with the pinned vision projector and the same interface as studio."""
    run_vstudio(force, _stdout, _stderr)


@app.command()
def calibrate(
    mode: Annotated[str, typer.Option("--mode", help="Packaged mode id or 'all'.")],
    preference: Annotated[
        str | None,
        typer.Option(
            "--preference",
            help="Optimization rule to measure: fast, balanced (default), max-context.",
        ),
    ] = None,
    no_activate: Annotated[
        bool,
        typer.Option(
            "--no-activate", help="Keep measured records as candidates without activating them."
        ),
    ] = False,
    activate: Annotated[
        bool,
        typer.Option("--activate", help="Promote existing candidates without measuring again."),
    ] = False,
    target_ctx: Annotated[
        int | None,
        typer.Option("--target-ctx", help="Measure one approved context-window step only."),
    ] = None,
) -> None:
    """Measure one launch cell for one packaged mode or for all of them."""
    options = CalibrationCliInput(
        mode=mode,
        preference=preference,
        no_activate=no_activate,
        activate=activate,
        target_ctx=target_ctx,
    )
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
