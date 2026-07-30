"""Present `bora pi`: point the pi coding agent at this machine's bora service, or take it back.

The command is presentation and consent only. It shows the exact provider entry it would write,
asks once, and hands the merge and the atomic write to `pi_link.py` (specification section 4.1).
Installing pi is never implicit: without `--install` an absent pi is reported with the vendor's own
instructions for the two supported platforms.

`pi launch` delegates to pi's documented provider/model flags with inherited terminal I/O; it starts
neither the local service nor another integration. `pi remove` and `pi uninstall` are the inverses
of the two writes, and they stay separate questions: the provider entry lives in a file that belongs
to pi, while the package belongs to npm, so consenting to one is not consenting to the other
(D-082/D-090, applying the rule D-079 established for the shared model cache).

The context window handed over is the one this machine actually serves, and the output always says
where the number came from. A managed service already listening on the configured port knows its
own window and is asked first: record reuse weighs free memory that the running service is itself
holding, so consulting the record while it runs would report the baseline for a machine that is
serving far more than that (D-082).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import typer
from rich.console import Console

from bora_workbench._calibration_reuse import ReuseQuery, evaluate_record
from bora_workbench._cli_services import across_service_roots
from bora_workbench._cli_theme import (
    print_error,
    print_heading,
    print_note,
    print_success,
    print_warning,
)
from bora_workbench.config import Config, ConfigError, load_config
from bora_workbench.engine import EngineError, JsonObject, load_engine_lock
from bora_workbench.hardware import HardwareError, detect_hardware
from bora_workbench.models import display_name
from bora_workbench.pi_link import (
    PACKAGE_NAME,
    PROVIDER_NAME,
    ContextWindow,
    ContextWindowQuery,
    PiInstallation,
    current_entry,
    document_without_provider,
    inspect_pi,
    install_command,
    launch_command,
    merged_document,
    provider_entry,
    read_document,
    render,
    resolve_context_window,
    uninstall_command,
    write_document,
)
from bora_workbench.process import ProcessError, status_services
from bora_workbench.profiles import PlanError, load_catalog

# Both lines stay ASCII and short enough not to wrap: a wrapped install command cannot be copied,
# and a legacy Windows code page cannot encode the punctuation that would join them (D-071).
_UBUNTU_HINT = "npm install -g --ignore-scripts @earendil-works/pi-coding-agent"
_WINDOWS_HINT = 'powershell -c "irm https://pi.dev/install.ps1 | iex"'


@dataclass(frozen=True, slots=True)
class PiOptions:
    """Group whether `bora pi` may write and whether it may install pi first."""

    print_only: bool = False
    install: bool = False


def validate_pi_options(options: PiOptions, subcommand: str | None) -> None:
    """Reject group options that would be contradictory or silently ignored."""
    if subcommand is not None and (options.print_only or options.install):
        raise typer.BadParameter("--print and --install cannot be used with a pi subcommand")
    if options.print_only and options.install:
        raise typer.BadParameter("--print and --install are mutually exclusive")


def _context_query(config: Config, lock: JsonObject) -> ContextWindowQuery:
    """Collect the CLI facts consumed by the shared D-082 selection rule."""
    services = across_service_roots(status_services).services
    if any(service.port == config.llama_port for service in services):
        return ContextWindowQuery(config.llama_port, services, None)
    mode = load_catalog().mode("coding")
    if mode is None:
        raise EngineError("the packaged mode catalog has no coding mode")
    evaluation = evaluate_record(ReuseQuery(config, mode, detect_hardware(), lock))
    return ContextWindowQuery(config.llama_port, services, evaluation)


def _context_window(config: Config, lock: JsonObject) -> ContextWindow:
    """Resolve the pi window through the shared structured selection service."""
    return resolve_context_window(_context_query(config, lock))


def _show_window(window: ContextWindow, stdout: Console) -> None:
    """Report the window with its origin, so a number smaller than expected explains itself."""
    print_note(stdout, "Context window", f"{window.tokens} tokens, from the {window.source}")
    for diagnostic in window.diagnostics:
        print_warning(stdout, diagnostic)


def _run_npm(command: tuple[str, ...]) -> None:
    """Run one already shown and confirmed npm command without a shell."""
    try:
        completed = subprocess.run(command, check=False, shell=False)
    except OSError as error:
        raise EngineError(f"cannot run npm; install Node.js first: {error}") from error
    if completed.returncode != 0:
        raise EngineError(f"npm exited with code {completed.returncode}")


def _install_pi(stdout: Console) -> None:
    """Run the vendor's installation command after showing it and asking for consent."""
    command = install_command()
    print_note(stdout, "Install command", " ".join(command))
    stdout.print("This installs from the npm registry; bora-workbench pins no digest for it.")
    if not typer.confirm("Install pi now?", default=False):
        raise EngineError("pi was not installed; rerun without --install once it is on PATH")
    _run_npm(command)


def _require_pi(options: PiOptions, stdout: Console) -> PiInstallation:
    """Return a usable pi installation, installing it only when explicitly asked to."""
    installation = inspect_pi()
    if installation.is_installed:
        return installation
    if not options.install:
        print_note(stdout, "Ubuntu", _UBUNTU_HINT)
        print_note(stdout, "Windows", _WINDOWS_HINT)
        raise EngineError("pi is not on PATH; install it, or rerun with --install")
    _install_pi(stdout)
    return inspect_pi()


def _as_document(entry: JsonObject) -> JsonObject:
    """Return one provider entry under its provider name, so it renders as pi would store it."""
    return {PROVIDER_NAME: entry}


def _show_change(installation: PiInstallation, entry: JsonObject, stdout: Console) -> JsonObject:
    """Show what the write would change and return the document it would be merged into."""
    document = read_document(installation.models_file)
    existing = current_entry(document)
    print_heading(stdout, f"Provider {PROVIDER_NAME!r} in {installation.models_file}")
    if existing == entry:
        print_note(stdout, "Unchanged", "this provider is already configured exactly this way")
        return document
    if existing is not None:
        print_note(stdout, "Replacing", "the entry currently stored under this name")
        stdout.print(render(_as_document(existing)), markup=False, soft_wrap=True)
        print_note(stdout, "With", "this entry")
    stdout.print(render(_as_document(entry)), markup=False, soft_wrap=True)
    return document


def _connect(options: PiOptions, stdout: Console) -> None:
    """Build the entry, show it, and write it once the user confirms."""
    config = load_config()
    lock = load_engine_lock()
    window = _context_window(config, lock)
    _show_window(window, stdout)
    entry = provider_entry(lock, config.llama_port, window.tokens)
    if options.print_only:
        print_heading(stdout, "Add this to pi's models.json")
        stdout.print(render({"providers": _as_document(entry)}), markup=False, soft_wrap=True)
        return
    installation = _require_pi(options, stdout)
    document = _show_change(installation, entry, stdout)
    if not typer.confirm(f"Write this provider into {installation.models_file}?", default=False):
        stdout.print("Cancelled; pi's configuration was not changed.")
        return
    write_document(installation.models_file, merged_document(document, entry))
    print_success(stdout, "Connected", f"pi provider {PROVIDER_NAME!r}")
    usage = f'bora coding, then: pi --provider bora --model "{display_name(lock)}"'
    print_note(stdout, "Use", usage)


def _launch_pi(stdout: Console) -> None:
    """Run pi with bora's provider and locked model alias through inherited terminal I/O."""
    installation = inspect_pi()
    if installation.executable is None:
        raise EngineError("pi is not on PATH; run bora pi --install first")
    lock = load_engine_lock()
    command = launch_command(installation.executable, lock)
    display = f'pi --provider {PROVIDER_NAME} --model "{display_name(lock)}"'
    print_note(stdout, "Launch command", display)
    try:
        completed = subprocess.run(command, check=False, shell=False)
    except OSError as error:
        raise EngineError(f"cannot launch pi: {error}") from error
    if completed.returncode == 0:
        return
    if completed.returncode in (-2, 130):
        raise KeyboardInterrupt
    raise EngineError(f"pi exited with code {completed.returncode}")


def _remove_provider(stdout: Console) -> None:
    """Delete only this project's provider from pi's model store, after showing what goes.

    pi does not have to be installed for this to work: an entry written earlier outlives the
    package, and it is exactly then that removing it has to remain possible.
    """
    models_file = inspect_pi().models_file
    document = read_document(models_file)
    existing = current_entry(document)
    if existing is None:
        message = f"No provider named {PROVIDER_NAME!r} in {models_file}; nothing to remove."
        stdout.print(message, markup=False, soft_wrap=True)
        return
    print_heading(stdout, f"Provider {PROVIDER_NAME!r} in {models_file}")
    stdout.print(render(_as_document(existing)), markup=False, soft_wrap=True)
    if not typer.confirm(f"Remove this provider from {models_file}?", default=False):
        stdout.print("Cancelled; pi's configuration was not changed.")
        return
    write_document(models_file, document_without_provider(document))
    print_success(stdout, "Removed", f"pi provider {PROVIDER_NAME!r}")


def _report_removal(stdout: Console) -> None:
    """Report what npm actually removed by looking for pi on PATH once more."""
    remaining = inspect_pi()
    if remaining.executable is None:
        print_success(stdout, "Uninstalled", PACKAGE_NAME)
        return
    print_warning(stdout, f"pi is still on PATH at {remaining.executable}; npm did not own it.")


def _uninstall_pi(stdout: Console) -> None:
    """Hand the package back to npm after showing the command and asking for consent."""
    if not inspect_pi().is_installed:
        stdout.print("pi is not on PATH; no npm package was removed.")
        return
    command = uninstall_command()
    print_note(stdout, "Uninstall command", " ".join(command))
    stdout.print("This removes the global npm package. An installation made another way, such as")
    stdout.print("the vendor's Windows script, has to be removed the way it was installed.")
    if not typer.confirm("Uninstall pi now?", default=False):
        stdout.print("Skipped; pi is still installed.")
        return
    _run_npm(command)
    _report_removal(stdout)


def _uninstall(stdout: Console) -> None:
    """Remove pi itself, then ask separately about the provider entry it leaves behind."""
    _uninstall_pi(stdout)
    _remove_provider(stdout)


def print_pi_hint(ctx: int, stdout: Console) -> None:
    """Point a finished `coding` calibration at the command that hands that window to pi.

    Nothing updates the entry when a record is activated: it is a number stored in somebody else's
    configuration file, so the run that changes what the machine serves names the command that
    applies it (D-082).
    """
    if not inspect_pi().is_installed:
        print_note(stdout, "pi", "not installed; `bora pi --install` installs and connects it")
        return
    print_note(stdout, "pi", f"run `bora pi` to hand it this {ctx}-token context window")


def _run_action(action: Callable[[Console], None], stdout: Console, stderr: Console) -> None:
    """Run one pi action with the contractual failure mapping of section 5.11."""
    try:
        action(stdout)
    except (ConfigError, EngineError, HardwareError, PlanError, ProcessError) as error:
        print_error(stderr, "pi integration error", str(error))
        raise typer.Exit(code=1) from error
    except (KeyboardInterrupt, typer.Abort) as error:
        print_error(stderr, "pi integration error", "cancelled")
        raise typer.Exit(code=130) from error


def run_pi(options: PiOptions, stdout: Console, stderr: Console) -> None:
    """Connect pi to the local service and map expected failures to exit code 1."""
    _run_action(lambda console: _connect(options, console), stdout, stderr)


def run_pi_launch(stdout: Console, stderr: Console) -> None:
    """Launch pi with bora selected and map child failure through the CLI contract."""
    _run_action(_launch_pi, stdout, stderr)


def run_pi_removal(stdout: Console, stderr: Console) -> None:
    """Delete the provider entry `bora pi` writes, leaving pi itself installed."""
    _run_action(_remove_provider, stdout, stderr)


def run_pi_uninstall(stdout: Console, stderr: Console) -> None:
    """Uninstall pi itself, then ask separately about the provider entry."""
    _run_action(_uninstall, stdout, stderr)
