"""Present `bora pi`: point the pi coding agent at this machine's bora service.

The command is presentation and consent only. It shows the exact provider entry it would write,
asks once, and hands the merge and the atomic write to `pi_link.py` (specification section 4.1).
Installing pi is never implicit: without `--install` an absent pi is reported with the vendor's own
instructions for the two supported platforms.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import typer
from rich.console import Console

from bora_workbench._calibration_reuse import ReuseQuery, evaluate_record
from bora_workbench._cli_theme import print_error, print_heading, print_note, print_success
from bora_workbench.config import Config, ConfigError, load_config
from bora_workbench.engine import EngineError, JsonObject, load_engine_lock
from bora_workbench.hardware import HardwareError, detect_hardware
from bora_workbench.models import display_name
from bora_workbench.pi_link import (
    PROVIDER_NAME,
    PiInstallation,
    current_entry,
    inspect_pi,
    install_command,
    merged_document,
    provider_entry,
    read_document,
    render,
    write_document,
)
from bora_workbench.profiles import FALLBACK_CTX, PlanError, load_catalog

# Both lines stay ASCII and short enough not to wrap: a wrapped install command cannot be copied,
# and a legacy Windows code page cannot encode the punctuation that would join them (D-071).
_UBUNTU_HINT = "npm install -g --ignore-scripts @earendil-works/pi-coding-agent"
_WINDOWS_HINT = 'powershell -c "irm https://pi.dev/install.ps1 | iex"'


@dataclass(frozen=True, slots=True)
class PiOptions:
    """Group whether `bora pi` may write and whether it may install pi first."""

    print_only: bool
    install: bool


def _context_window(config: Config, lock: JsonObject) -> int:
    """Return the context `coding` would launch with: its local record's, or the baseline.

    pi needs a number, and an invented one would misreport the model. The record is the same
    source the launcher itself uses, so the two agree by construction (specification section 5.5).
    """
    mode = load_catalog().mode("coding")
    if mode is None:
        raise EngineError("the packaged mode catalog has no coding mode")
    evaluation = evaluate_record(ReuseQuery(config, mode, detect_hardware(), lock))
    if evaluation.status == "valid" and evaluation.ctx is not None:
        return int(evaluation.ctx)
    return FALLBACK_CTX


def _install_pi(stdout: Console) -> None:
    """Run the vendor's installation command after showing it and asking for consent."""
    command = install_command()
    print_note(stdout, "Install command", " ".join(command))
    stdout.print("This installs from the npm registry; bora-workbench pins no digest for it.")
    if not typer.confirm("Install pi now?", default=False):
        raise EngineError("pi was not installed; rerun without --install once it is on PATH")
    try:
        completed = subprocess.run(command, check=False, shell=False)
    except OSError as error:
        raise EngineError(f"cannot run npm; install Node.js first: {error}") from error
    if completed.returncode != 0:
        raise EngineError(f"npm exited with code {completed.returncode}")


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
    entry = provider_entry(lock, config.llama_port, _context_window(config, lock))
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


def run_pi(options: PiOptions, stdout: Console, stderr: Console) -> None:
    """Connect pi to the local service and map expected failures to exit code 1."""
    try:
        _connect(options, stdout)
    except (ConfigError, EngineError, HardwareError, PlanError) as error:
        print_error(stderr, "pi integration error", str(error))
        raise typer.Exit(code=1) from error
    except (KeyboardInterrupt, typer.Abort) as error:
        print_error(stderr, "pi integration error", "cancelled")
        raise typer.Exit(code=130) from error
