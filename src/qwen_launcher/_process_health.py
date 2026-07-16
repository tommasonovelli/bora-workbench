"""Poll the exact locked llama-server health response with bounded retries."""

from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx

from qwen_launcher.engine import JsonObject

_REQUEST_TIMEOUT_SECONDS = 2.0
_POLL_INTERVAL_SECONDS = 1.0
_LOAD_TIMEOUT_SECONDS = 15 * 60.0


def port_is_available(port: int) -> bool:
    """Check localhost binding so occupied ports fail before model loading."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        return False
    return True


class HealthError(RuntimeError):
    """Report process death, readiness timeout, or an incompatible health response."""


@dataclass(frozen=True, slots=True)
class HealthTarget:
    """Group health URL, machine contract, and actionable process log path."""

    url: str
    contract: JsonObject
    log_path: Path


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


def wait_for_health(process: subprocess.Popen[str], target: HealthTarget) -> None:
    """Wait up to 15 minutes, failing immediately on death or incompatible responses."""
    deadline = time.monotonic() + _LOAD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise HealthError(f"llama-server exited during startup; inspect {target.log_path}")
        try:
            response = httpx.get(target.url, timeout=_REQUEST_TIMEOUT_SECONDS)
        except (httpx.ConnectError, httpx.TimeoutException):
            response = None
        if response is not None:
            if _ready(response, target.contract):
                return
            if not _is_transient(response, target.contract):
                raise HealthError(
                    f"health returned incompatible HTTP {response.status_code}; "
                    f"inspect {target.log_path}"
                )
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise HealthError(
        f"llama-server did not become ready within 15 minutes; inspect {target.log_path}"
    )
