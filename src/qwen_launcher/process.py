"""Manage lifecycle with platform process groups and pid/create_time identity (section 5.9)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import psutil

from qwen_launcher._process_control import ControlError, ServiceReport, status_at, stop_at
from qwen_launcher._process_health import (
    HealthError,
    HealthTarget,
    port_is_available,
    wait_for_health,
)
from qwen_launcher._process_lock import StartLockError, acquire_start_lock
from qwen_launcher._process_state import (
    ServiceState,
    StateError,
    clean_state,
    remove_service,
    write_state,
)
from qwen_launcher.engine import JsonObject
from qwen_launcher.paths import state_dir
from qwen_launcher.profiles import LaunchPlan


class ProcessError(RuntimeError):
    """Report an expected lifecycle failure with an actionable remedy."""


@dataclass(frozen=True, slots=True)
class StartRequest:
    """Group launch contracts and an optional immediate PID observer used by calibration."""

    command: tuple[str, ...]
    plan: LaunchPlan
    lock: JsonObject
    on_spawn: Callable[[int], None] | None = None


@dataclass(slots=True)
class RunningService:
    """Keep the child handle and persisted identity together while in foreground."""

    process: subprocess.Popen[str]
    state: ServiceState
    warnings: tuple[str, ...] = ()


def _child_environment(plan: LaunchPlan) -> dict[str, str]:
    """Copy the parent environment and isolate a verified single CUDA GPU only in the child."""
    environment = dict(os.environ)
    if plan.backend == "cuda":
        if plan.gpu_index is None:
            raise ProcessError("CUDA launch plan has no selected GPU index")
        environment["CUDA_VISIBLE_DEVICES"] = str(plan.gpu_index)
    return environment


def _creation_flags() -> int:
    """Start a new process group on Windows and use the portable default elsewhere."""
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0


def _log_path(root: Path) -> Path:
    """Create the managed log directory and return the required timestamped server log path."""
    directory = root / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return directory / f"llama-server-{stamp}.log"


def _service_state(
    process: subprocess.Popen[str], request: StartRequest, log_path: Path
) -> ServiceState:
    """Capture the exact child identity and launch plan for safe later management."""
    try:
        create_time = psutil.Process(process.pid).create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as error:
        message = f"cannot capture llama-server process identity; inspect {log_path}: {error}"
        raise ProcessError(message) from error
    plan = request.plan
    return ServiceState(
        "llama-server",
        process.pid,
        create_time,
        str(Path(request.command[0]).resolve()),
        plan.port,
        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        str(log_path.resolve()),
        plan.mode.id,
        plan.model,
        cast(str, request.lock["release"]),
        plan.profile_id,
        plan.ctx,
        plan.n_cpu_moe,
        plan.backend,
        plan.gpu_index,
    )


def _terminate_popen(process: subprocess.Popen[str]) -> None:
    """Terminate for ten seconds, then kill and wait up to five seconds."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise ProcessError("llama-server did not stop after terminate and kill") from error


def _health_target(request: StartRequest, log_path: Path) -> HealthTarget:
    """Build the loopback health URL exclusively from the locked path and configured port."""
    health = cast(JsonObject, request.lock["health_contract"])
    return HealthTarget(f"http://127.0.0.1:{request.plan.port}{health['path']}", health, log_path)


def start_service(request: StartRequest, root: Path | None = None) -> RunningService:
    """Serialize preflight, spawn shell-free, persist identity, and wait for exact readiness."""
    selected_root = state_dir() if root is None else root
    try:
        with acquire_start_lock(selected_root):
            snapshot = clean_state(selected_root)
            if snapshot.services:
                raise ProcessError("a managed service is already running; run qwen-launcher stop")
            if not port_is_available(request.plan.port):
                raise ProcessError(f"port {request.plan.port} is already occupied")
            log_path = _log_path(selected_root)
            with log_path.open("x", encoding="utf-8") as log:
                process = subprocess.Popen(
                    request.command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=_child_environment(request.plan),
                    text=True,
                    encoding="utf-8",
                    creationflags=_creation_flags(),
                )
            if request.on_spawn is not None:
                request.on_spawn(process.pid)
            service = _service_state(process, request, log_path)
            write_state(selected_root, (service,))
        running = RunningService(process, service, snapshot.warnings)
        wait_for_health(process, _health_target(request, log_path))
        return running
    except (HealthError, OSError, ProcessError, StartLockError, StateError) as error:
        if "process" in locals():
            _terminate_popen(process)
        if "service" in locals():
            remove_service(selected_root, service)
        raise ProcessError(str(error)) from error


def status_services(root: Path | None = None) -> ServiceReport:
    """Return verified services and map state failures to the public lifecycle error."""
    try:
        return status_at(state_dir() if root is None else root)
    except ControlError as error:
        raise ProcessError(str(error)) from error


def stop_services(root: Path | None = None) -> ServiceReport:
    """Stop verified services idempotently and map expected control failures."""
    try:
        return stop_at(state_dir() if root is None else root)
    except ControlError as error:
        raise ProcessError(str(error)) from error


def wait_foreground(running: RunningService, root: Path | None = None) -> None:
    """Remain attached, applying normal stop cleanup on Ctrl-C and natural process exit."""
    selected_root = state_dir() if root is None else root
    try:
        return_code = running.process.wait()
    except KeyboardInterrupt:
        _terminate_popen(running.process)
        remove_service(selected_root, running.state)
        raise
    remove_service(selected_root, running.state)
    if return_code != 0:
        raise ProcessError(
            f"llama-server exited with code {return_code}; inspect {running.state.log_path}"
        )
