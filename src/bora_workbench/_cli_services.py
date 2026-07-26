"""Present the commands that own managed services: launch, status, stop, and uninstall.

Every command here goes through the process layer: `coding`, `studio` and `vstudio` create a
managed service, `status` and `stop` inspect and end one, and `uninstall` refuses to delete the
state of a service that is still running (specification sections 5.10-5.11).
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import typer
from rich.console import Console
from rich.text import Text

from bora_workbench._cli_theme import (
    print_error,
    print_heading,
    print_note,
    print_success,
    print_warning,
    status_table,
)
from bora_workbench.calibration import service_roots
from bora_workbench.config import ConfigError, load_config
from bora_workbench.engine import (
    EngineError,
    JsonObject,
    build_command,
    load_engine_lock,
    locate,
    resolve_model,
)
from bora_workbench.hardware import HardwareError, detect_hardware, ensure_launch_supported
from bora_workbench.process import (
    ProcessError,
    RunningService,
    ServiceReport,
    ServiceState,
    StartRequest,
    start_service,
    status_services,
    stop_services,
    wait_foreground,
)
from bora_workbench.profiles import (
    ContentError,
    LaunchPlan,
    LaunchRequest,
    PlanError,
    build_launch_plan,
    enforce_memory_gate,
    load_catalog,
)
from bora_workbench.uninstall import (
    ManagedRoot,
    RemovalReport,
    ToolInstallation,
    ToolUninstallError,
    UninstallError,
    inspect_tool_installation,
    managed_roots,
    remove_managed_roots,
    schedule_tool_removal,
)


@dataclass(frozen=True, slots=True)
class PreparedMode:
    """Hold one ready managed mode and its user-facing local endpoints."""

    running: RunningService
    plan: LaunchPlan
    api_url: str
    ui_url: str | None
    is_browser_enabled: bool


@dataclass(frozen=True, slots=True)
class ServiceOutput:
    """Group the two CLI streams passed through shared mode presentation."""

    stdout: Console
    stderr: Console


def _mode_urls(plan: LaunchPlan, lock: JsonObject) -> tuple[str, str | None]:
    """Build loopback API and optional UI URLs from the verified lock paths."""
    contract = cast(JsonObject, lock["api_contract"])
    base = f"http://127.0.0.1:{plan.port}"
    api_url = f"{base}{contract['base_path']}"
    if not plan.mode.services.ui:
        return api_url, None
    ui_path = contract.get("ui_path")
    if not isinstance(ui_path, str):
        raise EngineError("engine.lock does not provide the integrated UI path")
    return api_url, f"{base}{ui_path}"


def _prepare_mode(mode_id: str, force: bool, stderr: Console) -> PreparedMode:
    """Prepare and start one packaged mode, including its required model artifacts."""
    try:
        config = load_config()
        hardware = detect_hardware()
        enforce_memory_gate(config, hardware, force=force)
        ensure_launch_supported(hardware)
        catalog = load_catalog()
        mode = catalog.mode(mode_id)
        if mode is None:
            valid = ", ".join(item.id for item in catalog.modes)
            raise PlanError(f"unknown mode {mode_id!r}; valid modes: {valid}")
        lock = load_engine_lock()
        model = resolve_model(config, lock, require_vision=mode.services.vision)
        request = LaunchRequest(config, mode_id, model.model_path, model.mmproj_path)
        plan = build_launch_plan(request, catalog, hardware)
        executable = locate(config, hardware.backend, lock)
        command = build_command(executable, plan, lock)
        api_url, ui_url = _mode_urls(plan, lock)
        running = start_service(StartRequest(command, plan, lock))
        return PreparedMode(running, plan, api_url, ui_url, config.open_browser)
    except ConfigError as error:
        print_error(stderr, "Configuration error", str(error))
        raise typer.Exit(code=2) from error
    except (ContentError, EngineError, HardwareError, PlanError, ProcessError) as error:
        print_error(stderr, "Launch error", str(error))
        raise typer.Exit(code=1) from error


def _show_ready(session: PreparedMode, stdout: Console) -> None:
    """Present the ready mode, endpoints, active envelope, and operational warnings."""
    plan = session.plan
    profile = plan.profile_id or "verified non-optimized baseline"
    print_success(stdout, "Ready", f"mode={plan.mode.id} backend={plan.backend}")
    print_note(stdout, "Profile", profile)
    print_note(stdout, "API endpoint", session.api_url)
    if session.ui_url is not None:
        print_note(stdout, "UI", session.ui_url)
        stdout.print("Interface: essential integrated llama.cpp UI; Open WebUI is not included.")
    print_note(stdout, "Log", str(session.running.state.log_path))
    for warning in (*session.running.warnings, *plan.warnings):
        print_warning(stdout, warning)


def _open_ui(session: PreparedMode, stdout: Console) -> None:
    """Open the ready integrated UI when configured, retaining its URL on failure."""
    if session.ui_url is None or not session.is_browser_enabled:
        return
    try:
        is_opened = webbrowser.open(session.ui_url, new=2)
    except (OSError, webbrowser.Error) as error:
        print_warning(stdout, f"Could not open the browser: {error}")
        return
    if not is_opened:
        print_warning(stdout, "Could not open the browser; use the UI URL above.")


def _wait_for_mode(session: PreparedMode, output: ServiceOutput) -> None:
    """Keep one ready mode in foreground with contractual cleanup exit mapping."""
    try:
        wait_foreground(session.running)
    except KeyboardInterrupt as error:
        print_warning(output.stdout, "Stopped after Ctrl-C.")
        raise typer.Exit(code=130) from error
    except ProcessError as error:
        print_error(output.stderr, "Process error", str(error))
        raise typer.Exit(code=1) from error


def _run_mode(mode_id: str, force: bool, output: ServiceOutput) -> None:
    """Prepare, present, optionally open, and foreground one packaged mode."""
    session = _prepare_mode(mode_id, force, output.stderr)
    _show_ready(session, output.stdout)
    _open_ui(session, output.stdout)
    _wait_for_mode(session, output)


def run_coding(force: bool, stdout: Console, stderr: Console) -> None:
    """Run API-first coding mode with UI and vision disabled by its packaged contract."""
    _run_mode("coding", force, ServiceOutput(stdout, stderr))


def run_studio(force: bool, stdout: Console, stderr: Console) -> None:
    """Run text studio mode with the integrated UI enabled after readiness."""
    _run_mode("studio", force, ServiceOutput(stdout, stderr))


def run_vstudio(force: bool, stdout: Console, stderr: Console) -> None:
    """Run multimodal studio mode with the pinned mmproj and integrated UI enabled."""
    _run_mode("vstudio", force, ServiceOutput(stdout, stderr))


def _print_warnings(warnings: tuple[str, ...], stdout: Console) -> None:
    """Present state cleanup warnings consistently for status and stop."""
    for warning in warnings:
        print_warning(stdout, warning)


def _across_roots(operation: Callable[[Path], ServiceReport]) -> ServiceReport:
    """Apply one process-layer operation to every service root and merge its reports.

    Composing the roots here keeps the calibration tree layout inside the calibration module and
    the lifecycle rules inside the process module, as specification section 4.1 requires.
    """
    services: list[ServiceState] = []
    warnings: list[str] = []
    stopped: list[str] = []
    for root in service_roots():
        report = operation(root)
        services.extend(report.services)
        warnings.extend(report.warnings)
        stopped.extend(report.stopped)
    return ServiceReport(tuple(services), tuple(warnings), tuple(stopped))


def show_status(stdout: Console, stderr: Console) -> None:
    """Present live managed services and preserve status idempotence."""
    try:
        report = _across_roots(status_services)
    except ProcessError as error:
        print_error(stderr, "Status error", str(error))
        raise typer.Exit(code=1) from error
    _print_warnings(report.warnings, stdout)
    if not report.services:
        stdout.print("No managed services are running.")
        return
    table = status_table()
    for header in ("Service", "PID", "Mode", "Backend", "Port", "Log"):
        table.add_column(header)
    for service in report.services:
        table.add_row(
            Text(service.label),
            str(service.pid),
            Text(service.mode),
            Text(service.backend),
            str(service.port),
            Text(service.log_path),
        )
    stdout.print(table)


def run_stop(stdout: Console, stderr: Console) -> None:
    """Present identity-safe stop results and preserve empty-state idempotence."""
    try:
        report = _across_roots(stop_services)
    except ProcessError as error:
        print_error(stderr, "Stop error", str(error))
        raise typer.Exit(code=1) from error
    _print_warnings(report.warnings, stdout)
    if report.stopped:
        stdout.print(f"Stopped: {', '.join(report.stopped)}")
    else:
        stdout.print("No managed services are running.")


def _show_preview(
    roots: tuple[ManagedRoot, ...], installation: ToolInstallation, stdout: Console
) -> None:
    """Show every managed root, the Python tool disposition, and excluded external data."""
    print_heading(stdout, "Uninstall preview")
    stdout.print("The following managed roots will be deleted after confirmation:")
    for root in roots:
        state = "present" if root.exists else "absent"
        stdout.print(f"  {root.label}: {root.path} ({state})", markup=False, soft_wrap=True)
    tool_state = "will be removed with uv" if installation.is_managed_by_uv else "not uv-managed"
    stdout.print(f"  Python tool: {installation.environment} ({tool_state})", markup=False)
    stdout.print("The Hugging Face cache and uv itself are never touched.")


def _show_report(report: RemovalReport, installation: ToolInstallation, stdout: Console) -> None:
    """Report root deletion and whether the Python tool removal was handed to uv."""
    for path in report.removed:
        stdout.print(f"Removed: {path}", markup=False, soft_wrap=True)
    for path in report.absent:
        stdout.print(f"Already absent: {path}", markup=False, soft_wrap=True)
    if installation.is_managed_by_uv:
        stdout.print("The bora-workbench Python tool will be removed as this command exits.")
    else:
        stdout.print("Python tool unchanged: this invocation is not managed by uv tool.")


def _require_services_stopped(stderr: Console) -> None:
    """Refuse to orphan a live managed process by deleting its state (section 5.10)."""
    try:
        report = _across_roots(status_services)
    except ProcessError as error:
        print_error(stderr, "Uninstall error", f"cannot inspect managed services: {error}")
        raise typer.Exit(code=1) from error
    for warning in report.warnings:
        print_warning(stderr, warning)
    if report.services:
        detail = "managed services are running; run bora stop"
        print_error(stderr, "Uninstall error", detail)
        raise typer.Exit(code=1)


def _inspect_installation(stderr: Console) -> ToolInstallation:
    """Map uv installation inspection failures to the operational CLI boundary."""
    try:
        return inspect_tool_installation()
    except ToolUninstallError as error:
        print_error(stderr, "Uninstall error", str(error))
        raise typer.Exit(code=1) from error


def _remove_everything(
    roots: tuple[ManagedRoot, ...], installation: ToolInstallation
) -> RemovalReport:
    """Delete confirmed roots, then start self-removal only after deletion succeeds."""
    try:
        report = remove_managed_roots(roots)
        schedule_tool_removal(installation)
    except (ToolUninstallError, UninstallError) as error:
        raise UninstallError(str(error)) from error
    return report


def run_uninstall(stdout: Console, stderr: Console) -> None:
    """Confirm once, then remove managed roots and the current uv-managed Python tool."""
    _require_services_stopped(stderr)
    installation = _inspect_installation(stderr)
    roots = managed_roots()
    _show_preview(roots, installation, stdout)
    if not any(root.exists for root in roots) and not installation.is_managed_by_uv:
        stdout.print("No managed installation found; nothing to remove.")
        return
    try:
        if not typer.confirm("Remove bora-workbench completely?", default=False):
            stdout.print("Uninstall cancelled; nothing was removed.")
            return
        _require_services_stopped(stderr)
        report = _remove_everything(roots, installation)
    except (KeyboardInterrupt, typer.Abort) as error:
        print_warning(stderr, f"Uninstall cancelled: {error}")
        raise typer.Exit(code=130) from error
    except UninstallError as error:
        print_error(stderr, "Uninstall error", str(error))
        raise typer.Exit(code=1) from error
    _show_report(report, installation, stdout)
