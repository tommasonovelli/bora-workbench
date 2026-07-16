"""Coordinate packaged launch modes and present them at the Typer command boundary."""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from typing import cast

import typer
from rich.console import Console

from qwen_launcher.config import ConfigError, load_config
from qwen_launcher.engine import (
    EngineError,
    JsonObject,
    build_command,
    load_engine_lock,
    locate,
    resolve_model,
)
from qwen_launcher.hardware import HardwareError, detect_hardware, ensure_launch_supported
from qwen_launcher.process import (
    ProcessError,
    RunningService,
    StartRequest,
    start_service,
    wait_foreground,
)
from qwen_launcher.profiles import (
    ContentError,
    LaunchPlan,
    LaunchRequest,
    PlanError,
    build_launch_plan,
    enforce_memory_gate,
    load_catalog,
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
        stderr.print(f"[red]Configuration error:[/red] {error}")
        raise typer.Exit(code=2) from error
    except (ContentError, EngineError, HardwareError, PlanError, ProcessError) as error:
        stderr.print(f"[red]Launch error:[/red] {error}")
        raise typer.Exit(code=1) from error


def _show_ready(session: PreparedMode, stdout: Console) -> None:
    """Present the ready mode, endpoints, active envelope, and operational warnings."""
    plan = session.plan
    profile = plan.profile_id or "verified non-optimized baseline"
    stdout.print(f"[green]Ready[/green] mode={plan.mode.id} backend={plan.backend}")
    stdout.print(f"Profile: {profile}")
    stdout.print(f"API endpoint: {session.api_url}")
    if session.ui_url is not None:
        stdout.print(f"UI: {session.ui_url}")
        stdout.print("Interface: essential integrated llama.cpp UI; Open WebUI is not included.")
    stdout.print(f"Log: {session.running.state.log_path}")
    for warning in (*session.running.warnings, *plan.warnings):
        stdout.print(f"[yellow]WARNING[/yellow] {warning}")


def _open_ui(session: PreparedMode, stdout: Console) -> None:
    """Open the ready integrated UI when configured, retaining its URL on failure."""
    if session.ui_url is None or not session.is_browser_enabled:
        return
    try:
        is_opened = webbrowser.open(session.ui_url, new=2)
    except (OSError, webbrowser.Error) as error:
        stdout.print(f"[yellow]WARNING[/yellow] Could not open the browser: {error}")
        return
    if not is_opened:
        stdout.print("[yellow]WARNING[/yellow] Could not open the browser; use the UI URL above.")


def _wait_for_mode(session: PreparedMode, output: ServiceOutput) -> None:
    """Keep one ready mode in foreground with contractual cleanup exit mapping."""
    try:
        wait_foreground(session.running)
    except KeyboardInterrupt as error:
        output.stdout.print("[yellow]Stopped after Ctrl-C.[/yellow]")
        raise typer.Exit(code=130) from error
    except ProcessError as error:
        output.stderr.print(f"[red]Process error:[/red] {error}")
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
