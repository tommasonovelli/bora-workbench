"""Coordinate and present Step 3 lifecycle services for the Typer command boundary."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from qwen_launcher.config import ConfigError, load_config
from qwen_launcher.engine import EngineError, build_command, load_engine_lock, locate, resolve_model
from qwen_launcher.hardware import HardwareError, detect_hardware, ensure_launch_supported
from qwen_launcher.process import (
    ProcessError,
    RunningService,
    StartRequest,
    start_service,
    status_services,
    stop_services,
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


def _prepare_coding(force: bool, stderr: Console) -> tuple[RunningService, LaunchPlan, str]:
    """Prepare and start coding mode, mapping all expected preflight failures."""
    try:
        config = load_config()
        hardware = detect_hardware()
        enforce_memory_gate(config, hardware, force=force)
        ensure_launch_supported(hardware)
        catalog = load_catalog()
        lock = load_engine_lock()
        model = resolve_model(config, lock)
        request = LaunchRequest(config, "coding", model.model_path, model.mmproj_path)
        plan = build_launch_plan(request, catalog, hardware)
        executable = locate(config, hardware.backend, lock)
        command = build_command(executable, plan, lock)
        running = start_service(StartRequest(command, plan, lock))
        api_contract = lock["api_contract"]
        api = api_contract["base_path"]  # type: ignore[index]
        return running, plan, f"http://127.0.0.1:{plan.port}{api}"
    except ConfigError as error:
        stderr.print(f"[red]Configuration error:[/red] {error}")
        raise typer.Exit(code=2) from error
    except (ContentError, EngineError, HardwareError, PlanError, ProcessError) as error:
        stderr.print(f"[red]Launch error:[/red] {error}")
        raise typer.Exit(code=1) from error


def run_coding(force: bool, stdout: Console, stderr: Console) -> None:
    """Run coding in foreground and map normal interruption to contractual exit 130."""
    running, plan, endpoint = _prepare_coding(force, stderr)
    profile = plan.profile_id or "verified non-optimized baseline"
    stdout.print(f"[green]Ready[/green] mode={plan.mode.id} backend={plan.backend}")
    stdout.print(f"Profile: {profile}")
    stdout.print(f"API endpoint: {endpoint}")
    stdout.print(f"Log: {running.state.log_path}")
    for warning in running.warnings:
        stdout.print(f"[yellow]WARNING[/yellow] {warning}")
    for warning in plan.warnings:
        stdout.print(f"[yellow]WARNING[/yellow] {warning}")
    try:
        wait_foreground(running)
    except KeyboardInterrupt as error:
        stdout.print("[yellow]Stopped after Ctrl-C.[/yellow]")
        raise typer.Exit(code=130) from error
    except ProcessError as error:
        stderr.print(f"[red]Process error:[/red] {error}")
        raise typer.Exit(code=1) from error


def _print_warnings(warnings: tuple[str, ...], stdout: Console) -> None:
    """Present state cleanup warnings consistently for status and stop."""
    for warning in warnings:
        stdout.print(f"[yellow]WARNING[/yellow] {warning}")


def show_status(stdout: Console, stderr: Console) -> None:
    """Present live managed services and preserve status idempotence."""
    try:
        report = status_services()
    except ProcessError as error:
        stderr.print(f"[red]Status error:[/red] {error}")
        raise typer.Exit(code=1) from error
    _print_warnings(report.warnings, stdout)
    if not report.services:
        stdout.print("No managed services are running.")
        return
    table = Table("Service", "PID", "Mode", "Backend", "Port", "Log")
    for service in report.services:
        table.add_row(
            service.label,
            str(service.pid),
            service.mode,
            service.backend,
            str(service.port),
            service.log_path,
        )
    stdout.print(table)


def run_stop(stdout: Console, stderr: Console) -> None:
    """Present identity-safe stop results and preserve empty-state idempotence."""
    try:
        report = stop_services()
    except ProcessError as error:
        stderr.print(f"[red]Stop error:[/red] {error}")
        raise typer.Exit(code=1) from error
    _print_warnings(report.warnings, stdout)
    if report.stopped:
        stdout.print(f"Stopped: {', '.join(report.stopped)}")
    else:
        stdout.print("No managed services are running.")
