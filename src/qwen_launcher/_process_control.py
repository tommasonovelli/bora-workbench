"""Implement idempotent status and identity-safe stop without platform branching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psutil

from qwen_launcher._process_state import (
    ServiceState,
    StateError,
    clean_state,
    find_verified_process,
    write_state,
)


class ControlError(RuntimeError):
    """Report an expected status or stop failure."""


@dataclass(frozen=True, slots=True)
class ServiceReport:
    """Return status or stop results without coupling lifecycle code to CLI presentation."""

    services: tuple[ServiceState, ...]
    warnings: tuple[str, ...] = ()
    stopped: tuple[str, ...] = ()


def status_at(root: Path) -> ServiceReport:
    """Return verified live services, cleaning dead and PID-reused records idempotently."""
    try:
        snapshot = clean_state(root)
    except StateError as error:
        raise ControlError(str(error)) from error
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
            raise ControlError(
                f"PID {service.pid} did not stop after terminate and kill"
            ) from error
    return True


def stop_at(root: Path) -> ServiceReport:
    """Stop every verified managed service and atomically clear their state."""
    report = status_at(root)
    stopped: list[str] = []
    warnings = list(report.warnings)
    try:
        for service in report.services:
            if _terminate_service(service):
                stopped.append(service.label)
            else:
                warnings.append(f"Skipped stale process identity for PID {service.pid}.")
        if report.services:
            write_state(root, ())
    except (psutil.Error, OSError, StateError) as error:
        raise ControlError(f"cannot stop managed service: {error}") from error
    return ServiceReport((), tuple(warnings), tuple(stopped))
