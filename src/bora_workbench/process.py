"""Run the managed llama-server lifecycle: preflight, spawn, readiness, status, and stop.

This is one of the four modules allowed to branch on the operating system (specification section
4.1) and the branch is confined to `_creation_flags`, which needs a new Windows process group so a
console signal cannot reach the child. Every decision about a live process uses the mandatory
pid/create_time identity of specification section 5.9, read through `_process_state`, so a signal is
never sent to a stranger that merely reuses a recorded PID.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast
from uuid import uuid4

import httpx
import psutil

from bora_workbench._process_state import (
    ServiceState,
    StartLockError,
    StateError,
    acquire_start_lock,
    clean_state,
    find_verified_process,
    remove_service,
    write_state,
)
from bora_workbench.engine import JsonObject
from bora_workbench.paths import state_dir
from bora_workbench.profiles import LaunchPlan

_REQUEST_TIMEOUT_SECONDS = 2.0
_POLL_INTERVAL_SECONDS = 1.0
_LOAD_TIMEOUT_SECONDS = 15 * 60.0


class ProcessError(RuntimeError):
    """Report an expected lifecycle failure with an actionable remedy."""


class PortCollisionError(ProcessError):
    """Report a loopback port collision that a calibration retry can avoid."""


class ServerStartupError(ProcessError):
    """Report a server that was spawned but never became healthy, retaining its log.

    Calibration needs this distinction because an exhausted GPU allocation only ever appears as a
    child that dies during model load: the log is the sole evidence separating that infeasible
    candidate from a preflight failure such as an occupied port (spec 5.6, D-059).
    """

    def __init__(self, message: str, log_path: Path | None) -> None:
        """Retain the process log so a later classifier can read the engine's own diagnosis."""
        super().__init__(message)
        self.log_path = log_path


class HealthError(RuntimeError):
    """Report process death, readiness timeout, or an incompatible health response."""


EXPECTED_START_FAILURES = (HealthError, OSError, ProcessError, StartLockError, StateError)


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


@dataclass(slots=True)
class _StartAttempt:
    """Retain partial startup ownership so every escaping failure can clean it."""

    process: subprocess.Popen[str] | None = None
    service: ServiceState | None = None
    log_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ServiceReport:
    """Return status or stop results without coupling lifecycle code to CLI presentation."""

    services: tuple[ServiceState, ...]
    warnings: tuple[str, ...] = ()
    stopped: tuple[str, ...] = ()


def port_is_available(port: int) -> bool:
    """Check localhost binding so occupied ports fail before model loading."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        return False
    return True


def _ready(response: httpx.Response, contract: JsonObject) -> bool:
    """Accept only the exact status and JSON body observed in Spike 0."""
    if response.status_code != contract["ready_status"]:
        return False
    try:
        body = response.json()
    except ValueError as error:
        raise HealthError("health returned ready status with invalid JSON") from error
    if body != contract["ready_json"]:
        raise HealthError(f"health returned incompatible ready body: {body!r}")
    return True


def _is_transient(response: httpx.Response, contract: JsonObject) -> bool:
    """Retry locked loading statuses and server-side failures, but never 4xx responses."""
    statuses = cast(list[int], contract["transient_statuses"])
    return response.status_code in statuses or response.status_code >= 500


def wait_for_health(process: subprocess.Popen[str], request: StartRequest, log_path: Path) -> None:
    """Wait up to 15 minutes, failing immediately on death or incompatible responses.

    The health URL is built exclusively from the locked path and the configured port, so no
    response from an unrelated listener can be mistaken for the managed server.
    """
    contract = cast(JsonObject, request.lock["health_contract"])
    url = f"http://127.0.0.1:{request.plan.port}{contract['path']}"
    deadline = time.monotonic() + _LOAD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise HealthError(f"llama-server exited during startup; inspect {log_path}")
        try:
            response = httpx.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
        except httpx.TransportError:
            # Every transport failure means "not ready yet", including the connection reset a
            # server produces while it is dying: the loop decides on process death or the
            # deadline, so no transport class may escape and bypass the caller's cleanup.
            response = None
        if response is not None:
            if _ready(response, contract):
                return
            if not _is_transient(response, contract):
                raise HealthError(
                    f"health returned incompatible HTTP {response.status_code}; inspect {log_path}"
                )
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise HealthError(f"llama-server did not become ready within 15 minutes; inspect {log_path}")


def terminate_popen(process: subprocess.Popen[str]) -> None:
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


def abandon_start(
    root: Path, process: subprocess.Popen[str] | None, service: ServiceState | None
) -> None:
    """Stop a spawned child and drop its record so a failed start leaves nothing behind."""
    failure: BaseException | None = None
    if process is not None:
        try:
            terminate_popen(process)
        except BaseException as error:
            failure = error
    if service is not None:
        try:
            with acquire_start_lock(root):
                remove_service(root, service)
        except BaseException as error:
            if failure is None:
                failure = error
    if failure is not None:
        raise failure


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
    return directory / f"llama-server-{stamp}-{uuid4().hex}.log"


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


def _spawn_service(request: StartRequest, root: Path, attempt: _StartAttempt) -> RunningService:
    """Spawn and register one child while holding the lifecycle serialization lock."""
    with acquire_start_lock(root):
        snapshot = clean_state(root)
        if snapshot.services:
            raise ProcessError("a managed service is already running; run bora stop")
        if not port_is_available(request.plan.port):
            raise PortCollisionError(f"port {request.plan.port} is already occupied")
        attempt.log_path = _log_path(root)
        with attempt.log_path.open("x", encoding="utf-8") as log:
            attempt.process = subprocess.Popen(
                request.command,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=_child_environment(request.plan),
                text=True,
                encoding="utf-8",
                creationflags=_creation_flags(),
            )
        if request.on_spawn is not None:
            request.on_spawn(attempt.process.pid)
        attempt.service = _service_state(attempt.process, request, attempt.log_path)
        write_state(root, (attempt.service,))
    return RunningService(attempt.process, attempt.service, snapshot.warnings)


def _raise_start_failure(root: Path, attempt: _StartAttempt, error: BaseException) -> NoReturn:
    """Clean every partial start and map only declared operational failures."""
    try:
        abandon_start(root, attempt.process, attempt.service)
    except BaseException as cleanup:
        if not isinstance(error, Exception):
            raise error from cleanup
        raise ProcessError(f"failed start cleanup: {cleanup}") from cleanup
    if not isinstance(error, EXPECTED_START_FAILURES):
        raise error
    if attempt.process is None:
        raise ProcessError(str(error)) from error
    raise ServerStartupError(str(error), attempt.log_path) from error


def start_service(request: StartRequest, root: Path | None = None) -> RunningService:
    """Serialize preflight, spawn shell-free, persist identity, and wait for exact readiness."""
    selected_root = state_dir() if root is None else root
    attempt = _StartAttempt()
    try:
        running = _spawn_service(request, selected_root, attempt)
        assert attempt.process is not None and attempt.log_path is not None
        wait_for_health(attempt.process, request, attempt.log_path)
        return running
    except BaseException as error:
        _raise_start_failure(selected_root, attempt, error)


def status_services(root: Path | None = None) -> ServiceReport:
    """Return verified live services, cleaning dead and PID-reused records idempotently."""
    selected_root = state_dir() if root is None else root
    if not selected_root.exists():
        return ServiceReport(())
    try:
        with acquire_start_lock(selected_root):
            snapshot = clean_state(selected_root)
    except (StartLockError, StateError) as error:
        raise ProcessError(str(error)) from error
    return ServiceReport(snapshot.services, snapshot.warnings)


def _terminate_service(service: ServiceState) -> bool:
    """Stop one service only after rechecking its mandatory process identity."""
    try:
        process = find_verified_process(service.pid, service.create_time)
        if process is None:
            return False
        process.terminate()
    except psutil.NoSuchProcess:
        # The verified process exited between the identity recheck and terminate; treat it
        # like any other already-dead entry so stop stays idempotent.
        return False
    try:
        process.wait(timeout=10)
    except psutil.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired as error:
            raise ProcessError(
                f"PID {service.pid} did not stop after terminate and kill"
            ) from error
    return True


def _stop_locked(root: Path) -> ServiceReport:
    """Stop and clear the verified snapshot while holding the lifecycle lock."""
    stopped: list[str] = []
    with acquire_start_lock(root):
        snapshot = clean_state(root)
        warnings = list(snapshot.warnings)
        for service in snapshot.services:
            if _terminate_service(service):
                stopped.append(service.label)
            else:
                warnings.append(f"Skipped stale process identity for PID {service.pid}.")
        if snapshot.services:
            write_state(root, ())
    return ServiceReport((), tuple(warnings), tuple(stopped))


def stop_services(root: Path | None = None) -> ServiceReport:
    """Stop every verified managed service and atomically clear their state."""
    selected_root = state_dir() if root is None else root
    if not selected_root.exists():
        return ServiceReport(())
    try:
        return _stop_locked(selected_root)
    except (psutil.Error, OSError, StartLockError, StateError) as error:
        raise ProcessError(f"cannot stop managed service: {error}") from error


def _remove_foreground_service(root: Path, service: ServiceState) -> None:
    """Leave cleanup to the concurrent lifecycle operation that owns the lock."""
    try:
        with acquire_start_lock(root):
            remove_service(root, service)
    except StartLockError:
        return


def wait_foreground(running: RunningService, root: Path | None = None) -> None:
    """Remain attached, applying normal stop cleanup on Ctrl-C and natural process exit."""
    selected_root = state_dir() if root is None else root
    try:
        return_code = running.process.wait()
    except KeyboardInterrupt:
        terminate_popen(running.process)
        _remove_foreground_service(selected_root, running.state)
        raise
    _remove_foreground_service(selected_root, running.state)
    if return_code != 0:
        raise ProcessError(
            f"llama-server exited with code {return_code}; inspect {running.state.log_path}"
        )
