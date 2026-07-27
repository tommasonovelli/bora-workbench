"""Present `bora update`: version comparison, verified download, and handoff to uv.

The command reports before it acts, refuses every installation uv does not own, and never touches
the managed engine (specification sections 5.10-5.11, D-073). Because the actual `uv tool install`
runs after this process exits, the exit code reports the *scheduling*, not the installation; the
helper prints uv's own failure on the same terminal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from bora_workbench._cli_services import require_services_stopped
from bora_workbench._cli_theme import print_error, print_note, print_success, print_warning
from bora_workbench._tool_handoff import (
    ToolHandoffError,
    ToolInstallation,
    inspect_tool_installation,
)
from bora_workbench.engine import EngineError, engine_status
from bora_workbench.paths import cache_dir
from bora_workbench.update import (
    UpdateError,
    download_wheel,
    is_newer,
    latest_version,
    pinned_engine_release,
    schedule_tool_update,
)


@dataclass(frozen=True, slots=True)
class UpdateOptions:
    """Group the installed version and the caller's check-only choice."""

    installed_version: str
    is_check_only: bool


def _guard[Result](operation: Callable[[], Result], stderr: Console) -> Result:
    """Run one update step and map its actionable failure to exit code 1 (section 5.11)."""
    try:
        return operation()
    except (UpdateError, ToolHandoffError) as error:
        print_error(stderr, "Update error", str(error))
        raise typer.Exit(code=1) from error


def _require_uv_installation(stderr: Console) -> ToolInstallation:
    """Refuse to replace an installation uv does not own, naming the supported path instead."""
    installation = _guard(inspect_tool_installation, stderr)
    if installation.is_managed_by_uv:
        return installation
    print_error(
        stderr,
        "Update error",
        f"this installation is not managed by `uv tool` ({installation.environment}); "
        "install the new release with the documented installer instead",
    )
    raise typer.Exit(code=1)


def _report_engine(wheel: Path, stdout: Console) -> None:
    """State whether the update also requires reinstalling the managed engine (D-073)."""
    published = pinned_engine_release(wheel)
    try:
        active = engine_status().release
    except EngineError:
        active = None
    if published is None or active is None:
        print_note(stdout, "Engine", "not reinstalled; check `bora engine status` afterwards")
        return
    if published == active:
        print_note(stdout, "Engine", f"unchanged: the new version keeps llama.cpp {published}")
        return
    print_warning(
        stdout,
        f"the new version pins llama.cpp {published} while {active} is active; "
        "run `bora engine install` after the update",
    )


def _install_latest(latest: str, stdout: Console, stderr: Console) -> None:
    """Verify the published wheel and schedule the uv installation that follows this process."""
    installation = _require_uv_installation(stderr)
    require_services_stopped("Update error", stderr)
    wheel = _guard(lambda: download_wheel(latest, cache_dir()), stderr)
    print_note(stdout, "Verified", str(wheel))
    _report_engine(wheel, stdout)
    _guard(lambda: schedule_tool_update(installation, wheel), stderr)
    print_success(stdout, "Scheduled", f"bora-workbench {latest} installs as this command exits.")
    print_note(stdout, "Then run", "bora --version")


def run_update(options: UpdateOptions, stdout: Console, stderr: Console) -> None:
    """Compare the installed version with the newest release and install it unless only checking."""
    installed = options.installed_version
    latest = _guard(latest_version, stderr)
    print_note(stdout, "Installed", installed)
    print_note(stdout, "Published", latest)
    if not _guard(lambda: is_newer(latest, installed), stderr):
        print_success(stdout, "Up to date", "no newer GitHub Release is published.")
        return
    if options.is_check_only:
        print_note(stdout, "Available", f"run `bora update` to install {latest}")
        return
    _install_latest(latest, stdout, stderr)
