"""Present the commands that own the managed Open WebUI installation.

The interface arrives with the engine, because `bora engine install` is already the step where a
first setup spends gigabytes and waits. Removing it is a separate command, and it asks about the
environment and about the user's own chats and uploads as two different questions, because they are
two different kinds of thing (D-096).
"""

from __future__ import annotations

import typer
from rich.console import Console

from bora_workbench._cli_services import require_services_stopped
from bora_workbench._cli_theme import (
    format_bytes,
    print_error,
    print_heading,
    print_note,
    print_success,
    print_warning,
)
from bora_workbench.config import ConfigError, load_config
from bora_workbench.webui import (
    OPEN_WEBUI_VERSION,
    WebuiError,
    WebuiStatus,
    directory_size,
    environment_dir,
    inspect_webui,
    install_webui,
    interface_data_dir,
    remove_environment,
    remove_interface_data,
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


def install_managed_webui(force: bool, stdout: Console) -> WebuiStatus:
    """Install the pinned interface, showing uv's own progress and what the download costs.

    Shared with `engine install`, so the interface arrives the same way and says the same thing
    whether it is acquired with the engine or on its own.
    """
    current = inspect_webui()
    if current.is_installed and not force:
        print_success(stdout, "Open WebUI", f"{OPEN_WEBUI_VERSION} is already installed")
        return current
    print_heading(stdout, "Installing Open WebUI")
    stdout.print(
        f"Installing open-webui=={OPEN_WEBUI_VERSION} into {environment_dir(current.root)}"
    )
    stdout.print("Its dependency closure includes torch, so this downloads several gigabytes.")
    stdout.print("Open WebUI is a separate program; bora starts it and never modifies it.")
    status = install_webui(force=force)
    print_success(stdout, "Open WebUI", f"{OPEN_WEBUI_VERSION} installed")
    return status


def run_webui_install(force: bool, stdout: Console, stderr: Console) -> None:
    """Install the interface on its own, refusing while a service still holds it open."""
    require_services_stopped("Install error", stderr)
    try:
        status = install_managed_webui(force, stdout)
    except WebuiError as error:
        print_error(stderr, "Install error", str(error))
        raise typer.Exit(code=1) from error
    _show_status(status, stdout)


def _offer_environment(status: WebuiStatus, stdout: Console) -> None:
    """Ask about the reinstallable bytes first, naming what the answer frees."""
    environment = environment_dir(status.root)
    if not environment.is_dir():
        stdout.print("No managed Open WebUI environment is present.")
        return
    size = format_bytes(directory_size(environment))
    stdout.print(f"Environment: {environment} ({size})")
    stdout.print("Removing it frees that space; `bora webui install` puts it back.")
    if not typer.confirm("Remove the managed Open WebUI environment?", default=False):
        stdout.print("Environment kept.")
        return
    if remove_environment():
        print_success(stdout, "Removed", f"{size} freed")


def _offer_interface_data(status: WebuiStatus, stdout: Console) -> None:
    """Ask about the user's own content separately, because deleting it is not reversible.

    This is the question D-079 established for weights: content a user made gets its own request
    rather than being swept up in another one.
    """
    data = interface_data_dir(status.root)
    if not data.is_dir():
        return
    size = format_bytes(directory_size(data))
    stdout.print(f"Interface data: {data} ({size})")
    stdout.print("This is your own content: chats, notes, uploads, and settings. It is not backed")
    stdout.print("up anywhere and removing it cannot be undone.")
    if not typer.confirm("Also remove the interface data?", default=False):
        stdout.print("Interface data kept; a later install finds your chats where they were.")
        return
    if remove_interface_data():
        print_success(stdout, "Removed", f"{size} freed")


def run_webui_removal(stdout: Console, stderr: Console) -> None:
    """Remove the managed interface, asking about its environment and its content separately."""
    require_services_stopped("Removal error", stderr)
    status = inspect_webui()
    print_heading(stdout, "Remove Open WebUI")
    try:
        _offer_environment(status, stdout)
        _offer_interface_data(status, stdout)
    except WebuiError as error:
        print_error(stderr, "Removal error", str(error))
        raise typer.Exit(code=1) from error
    except (KeyboardInterrupt, typer.Abort) as error:
        print_warning(stderr, f"Removal cancelled: {error}")
        raise typer.Exit(code=130) from error
