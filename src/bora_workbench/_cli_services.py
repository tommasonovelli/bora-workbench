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

from bora_workbench._cli_models import offer_cache_removal
from bora_workbench._cli_theme import (
    print_error,
    print_heading,
    print_note,
    print_success,
    print_warning,
    status_table,
    verifying_model,
)
from bora_workbench._tool_handoff import (
    ToolHandoffError,
    ToolInstallation,
    inspect_tool_installation,
)
from bora_workbench.calibration import service_roots
from bora_workbench.config import Config, ConfigError, load_config
from bora_workbench.engine import (
    EngineError,
    JsonObject,
    ModelRequest,
    build_command,
    load_engine_lock,
    locate,
    resolve_model,
)
from bora_workbench.hardware import HardwareError, detect_hardware, ensure_launch_supported
from bora_workbench.process import (
    InterfaceRequest,
    ProcessError,
    RunningService,
    ServiceReport,
    ServiceState,
    StartRequest,
    start_interface,
    start_service,
    status_services,
    stop_interface,
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
    UninstallError,
    managed_roots,
    remove_managed_roots,
    schedule_tool_removal,
)
from bora_workbench.webui import (
    LOOPBACK_HOST,
    WebuiError,
    WebuiLaunch,
    WebuiStatus,
    inspect_webui,
    interface_data_dir,
    launch_environment,
    readiness_contract,
    resolve_secret_key,
    serve_command,
)


@dataclass(frozen=True, slots=True)
class PreparedMode:
    """Hold one ready managed mode, its local endpoints, and the interface that fronts it."""

    running: RunningService
    plan: LaunchPlan
    api_url: str
    ui_url: str | None
    is_browser_enabled: bool
    interface: RunningService | None = None
    notes: tuple[str, ...] = ()

    @property
    def interface_name(self) -> str:
        """Name the program whose page is about to open, before it opens."""
        return "Open WebUI" if self.interface is not None else "the integrated llama.cpp interface"


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


def _webui_launch(config: Config, status: WebuiStatus) -> WebuiLaunch:
    """Resolve everything the interface process needs, including its stable session key."""
    assert status.executable is not None
    return WebuiLaunch(
        status.executable,
        config.webui_port,
        config.llama_port,
        interface_data_dir(status.root),
        resolve_secret_key(),
    )


def _start_managed_interface(config: Config, mode_id: str) -> tuple[RunningService | None, str]:
    """Start Open WebUI when it is installed, or explain which interface is used instead.

    A failure here never takes the engine down with it: the model is already serving, and the
    integrated llama.cpp interface is the reduced fallback the mode can still open (D-095).
    """
    status = inspect_webui()
    if not status.is_installed:
        return None, (
            "Open WebUI is not installed, so the integrated llama.cpp interface opens instead. "
            "Run `bora webui install` to use Open WebUI."
        )
    try:
        launch = _webui_launch(config, status)
        request = InterfaceRequest(
            serve_command(launch),
            launch_environment(launch),
            launch.port,
            mode_id,
            readiness_contract(launch.port),
        )
        return start_interface(request), ""
    except (ProcessError, WebuiError) as error:
        return None, f"Open WebUI did not start: {error}. The integrated interface opens instead."


@dataclass(frozen=True, slots=True)
class _StartedMode:
    """Group the already ready engine with everything resolved for the mode that started it."""

    config: Config
    plan: LaunchPlan
    running: RunningService
    api_url: str
    integrated_url: str | None


def _prepared(started: _StartedMode) -> PreparedMode:
    """Start the interface a UI mode asks for, and settle which URL the browser will open.

    Both services are ready by the time this returns, because each start call polls its own
    readiness contract before it comes back. That is what lets the caller open one browser tab
    knowing the page behind it can already answer (D-095).
    """
    config, plan = started.config, started.plan
    if started.integrated_url is None:
        return PreparedMode(started.running, plan, started.api_url, None, config.open_browser)
    interface, note = _start_managed_interface(config, plan.mode.id)
    ui_url = started.integrated_url
    if interface is not None:
        ui_url = f"http://{LOOPBACK_HOST}:{config.webui_port}"
    return PreparedMode(
        started.running,
        plan,
        started.api_url,
        ui_url,
        config.open_browser,
        interface,
        (note,) if note else (),
    )


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
        with verifying_model(stderr) as verifying:
            model = resolve_model(config, lock, ModelRequest(mode.services.vision, verifying))
        request = LaunchRequest(config, mode_id, model.model_path, model.mmproj_path)
        plan = build_launch_plan(request, catalog, hardware)
        executable = locate(config, hardware.backend, lock)
        command = build_command(executable, plan, lock)
        api_url, integrated_url = _mode_urls(plan, lock)
        running = start_service(StartRequest(command, plan, lock))
        return _prepared(_StartedMode(config, plan, running, api_url, integrated_url))
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
        stdout.print(f"Interface: {session.interface_name}.")
    print_note(stdout, "Log", str(session.running.state.log_path))
    if session.interface is not None:
        print_note(stdout, "Open WebUI log", str(session.interface.state.log_path))
    for note in session.notes:
        print_note(stdout, "Interface", note)
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


def _release_interface(session: PreparedMode, stdout: Console) -> None:
    """Take the interface down first, and never let that hide why the mode is exiting."""
    if session.interface is None:
        return
    try:
        stop_interface(session.interface)
    except (OSError, ProcessError) as error:
        print_warning(stdout, f"Could not stop Open WebUI: {error}")


def _run_mode(mode_id: str, force: bool, output: ServiceOutput) -> None:
    """Prepare, present, optionally open, and foreground one packaged mode."""
    session = _prepare_mode(mode_id, force, output.stderr)
    try:
        _show_ready(session, output.stdout)
        _open_ui(session, output.stdout)
        _wait_for_mode(session, output)
    finally:
        _release_interface(session, output.stdout)


def run_coding(force: bool, stdout: Console, stderr: Console) -> None:
    """Run API-first coding mode with UI and vision disabled by its packaged contract."""
    _run_mode("coding", force, ServiceOutput(stdout, stderr))


def run_studio(force: bool, stdout: Console, stderr: Console) -> None:
    """Run text studio mode, opening Open WebUI when it is installed, after both are ready."""
    _run_mode("studio", force, ServiceOutput(stdout, stderr))


def run_vstudio(force: bool, stdout: Console, stderr: Console) -> None:
    """Run multimodal studio mode with the pinned mmproj and the same interface as studio."""
    _run_mode("vstudio", force, ServiceOutput(stdout, stderr))


def _print_warnings(warnings: tuple[str, ...], stdout: Console) -> None:
    """Present state cleanup warnings consistently for status and stop."""
    for warning in warnings:
        print_warning(stdout, warning)


def across_service_roots(operation: Callable[[Path], ServiceReport]) -> ServiceReport:
    """Apply one process-layer operation to every service root and merge its reports.

    Composing the roots here keeps the calibration tree layout inside the calibration module and
    the lifecycle rules inside the process module, as specification section 4.1 requires. `bora pi`
    reads the same sweep, because a service already listening on the configured port is the one
    thing that knows the context window it is actually serving (D-082).
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
        report = across_service_roots(status_services)
    except ProcessError as error:
        print_error(stderr, "Status error", str(error))
        raise typer.Exit(code=1) from error
    _print_warnings(report.warnings, stdout)
    if not report.services:
        stdout.print("No managed services are running.")
        return
    table = status_table()
    for header in ("Service", "Role", "PID", "Mode", "Backend", "Port", "Log"):
        table.add_column(header)
    for service in report.services:
        table.add_row(
            Text(service.label),
            Text(service.role),
            str(service.pid),
            Text(service.mode),
            # The interface runs no model, so it has no backend of its own to report.
            Text(service.backend or "not applicable"),
            str(service.port),
            Text(service.log_path),
        )
    stdout.print(table)


def run_stop(stdout: Console, stderr: Console) -> None:
    """Present identity-safe stop results and preserve empty-state idempotence."""
    try:
        report = across_service_roots(stop_services)
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
    stdout.print("The data root contains the model store, so its weights are deleted with it.")
    stdout.print("It also contains the managed Open WebUI, so its environment and your own chats,")
    stdout.print("notes and uploads go with it. `bora webui remove` deletes only that, and asks")
    stdout.print("about the environment and your content as two separate questions.")
    stdout.print("uv itself is never touched. Weights in the Hugging Face cache are asked about")
    stdout.print("separately, after this step.")


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


def require_services_stopped(category: str, stderr: Console) -> None:
    """Refuse to disturb a live managed process, whether by deleting or replacing its launcher.

    `uninstall` would orphan the process by deleting its state (section 5.10) and `update` would
    replace the tool environment the running launcher still holds open, so both refuse here.
    """
    try:
        report = across_service_roots(status_services)
    except ProcessError as error:
        print_error(stderr, category, f"cannot inspect managed services: {error}")
        raise typer.Exit(code=1) from error
    for warning in report.warnings:
        print_warning(stderr, warning)
    if report.services:
        detail = "managed services are running; run bora stop"
        print_error(stderr, category, detail)
        raise typer.Exit(code=1)


def _inspect_installation(stderr: Console) -> ToolInstallation:
    """Map uv installation inspection failures to the operational CLI boundary."""
    try:
        return inspect_tool_installation()
    except ToolHandoffError as error:
        print_error(stderr, "Uninstall error", str(error))
        raise typer.Exit(code=1) from error


def _remove_everything(
    roots: tuple[ManagedRoot, ...], installation: ToolInstallation
) -> RemovalReport:
    """Delete confirmed roots, then start self-removal only after deletion succeeds."""
    try:
        report = remove_managed_roots(roots)
        schedule_tool_removal(installation)
    except (ToolHandoffError, UninstallError) as error:
        raise UninstallError(str(error)) from error
    return report


def run_uninstall(stdout: Console, stderr: Console) -> None:
    """Confirm once, then remove managed roots and the current uv-managed Python tool."""
    require_services_stopped("Uninstall error", stderr)
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
        require_services_stopped("Uninstall error", stderr)
        report = _remove_everything(roots, installation)
    except (KeyboardInterrupt, typer.Abort) as error:
        print_warning(stderr, f"Uninstall cancelled: {error}")
        raise typer.Exit(code=130) from error
    except UninstallError as error:
        print_error(stderr, "Uninstall error", str(error))
        raise typer.Exit(code=1) from error
    _show_report(report, installation, stdout)
    _offer_cached_weights(stdout, stderr)


def _offer_cached_weights(stdout: Console, stderr: Console) -> None:
    """Ask separately about weights that outlive the managed roots in the shared cache.

    A failure here must not turn a completed uninstall into a non-zero exit: the managed roots are
    already gone, and the only thing left to report is that the cache was not touched (D-079).
    """
    try:
        offer_cache_removal(load_engine_lock(), stdout)
    except (EngineError, KeyboardInterrupt, typer.Abort) as error:
        print_warning(stderr, f"Hugging Face cache left unchanged: {error}")
