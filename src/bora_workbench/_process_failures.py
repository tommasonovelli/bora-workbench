"""Declare managed-process failures and the cleanup a failed start must always perform."""

from __future__ import annotations

import subprocess
from pathlib import Path

from bora_workbench._process_health import HealthError
from bora_workbench._process_lock import StartLockError
from bora_workbench._process_state import ServiceState, StateError, remove_service


class ProcessError(RuntimeError):
    """Report an expected lifecycle failure with an actionable remedy."""


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


EXPECTED_START_FAILURES = (HealthError, OSError, ProcessError, StartLockError, StateError)


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
    if process is not None:
        terminate_popen(process)
    if service is not None:
        remove_service(root, service)
