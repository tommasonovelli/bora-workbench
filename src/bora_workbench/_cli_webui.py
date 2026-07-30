"""Present the commands that own the managed Open WebUI installation.

Installing it is an explicit act rather than a side effect of `bora studio`, because the dependency
closure runs to gigabytes and a launcher must not spend a user's disk without being asked. Until it
is installed, the UI modes keep opening the integrated llama.cpp interface (D-095).
"""

from __future__ import annotations

import typer
from rich.console import Console

from bora_workbench._cli_services import require_services_stopped
from bora_workbench._cli_theme import print_error, print_heading, print_note, print_success
from bora_workbench.config import ConfigError, load_config
from bora_workbench.webui import (
    OPEN_WEBUI_VERSION,
    WebuiError,
    WebuiStatus,
    environment_dir,
    inspect_webui,
    install_webui,
    interface_data_dir,
)


def _show_status(status: WebuiStatus, stdout: Console) -> None:
    """Describe the installation without ever naming the session key or its contents."""
    installed = f"{OPEN_WEBUI_VERSION} installed" if status.is_installed else "not installed"
    print_note(stdout, "Open WebUI", installed)
    print_note(stdout, "Environment", str(environment_dir(status.root)))
    print_note(stdout, "Interface data", str(interface_data_dir(status.root)))


def show_webui_status(stdout: Console, stderr: Console) -> None:
    """Report whether the pinned interface is installed, and on which port it would listen."""
    try:
        config = load_config()
    except ConfigError as error:
        print_error(stderr, "Configuration error", str(error))
        raise typer.Exit(code=2) from error
    status = inspect_webui()
    print_heading(stdout, "Managed Open WebUI")
    _show_status(status, stdout)
    print_note(stdout, "Port", str(config.webui_port))
    if not status.is_installed:
        stdout.print("Run `bora webui install` to use Open WebUI in studio and vstudio.")


def run_webui_install(force: bool, stdout: Console, stderr: Console) -> None:
    """Install the pinned Open WebUI into its own managed environment, showing uv's progress.

    A running interface holds the environment open, so the installation refuses to replace it
    while any managed service is up rather than corrupting one that is in use.
    """
    require_services_stopped("Install error", stderr)
    current = inspect_webui()
    if current.is_installed and not force:
        print_success(stdout, "Open WebUI", f"{OPEN_WEBUI_VERSION} is already installed")
        _show_status(current, stdout)
        return
    print_heading(stdout, "Installing Open WebUI")
    environment = environment_dir(current.root)
    stdout.print(f"Installing open-webui=={OPEN_WEBUI_VERSION} into {environment}")
    stdout.print("Its dependency closure includes torch, so this downloads several gigabytes.")
    stdout.print("Open WebUI is a separate program; bora starts it and never modifies it.")
    try:
        status = install_webui(force=force)
    except WebuiError as error:
        print_error(stderr, "Install error", str(error))
        raise typer.Exit(code=1) from error
    print_success(stdout, "Open WebUI", f"{OPEN_WEBUI_VERSION} installed")
    _show_status(status, stdout)
