"""Offline tests that a failed start leaves neither a live child nor a registered service."""

from __future__ import annotations

import httpx
import psutil
import pytest

import bora_workbench._process_health as health
import bora_workbench.process as lifecycle
from tests.test_process_lifecycle import fast_health, free_port, request


def test_a_transport_reset_is_read_as_not_ready_not_leaked(tmp_path, monkeypatch) -> None:
    """Treat the connection reset a dying server produces as "not ready", never as an escape.

    A leaked transport error would bypass the caller's cleanup and leave a phantom service.
    """
    fast_health(monkeypatch, timeout=0.05)

    def reset(*args: object, **kwargs: object) -> None:
        raise httpx.ReadError("[Errno 104] Connection reset by peer")

    monkeypatch.setattr(health.httpx, "get", reset)

    with pytest.raises(lifecycle.ProcessError, match="15 minutes"):
        lifecycle.start_service(request(free_port(), "loading"), tmp_path)

    assert lifecycle.status_services(tmp_path).services == ()


def test_an_unexpected_startup_failure_still_stops_the_child_and_clears_state(
    tmp_path, monkeypatch
) -> None:
    """Clean up whatever the readiness wait raises, so no phantom service blocks the next start."""
    fast_health(monkeypatch)
    spawned: list[int] = []
    ready = request(free_port())
    observed = lifecycle.StartRequest(ready.command, ready.plan, ready.lock, spawned.append)

    def unexpected(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unclassified readiness failure")

    monkeypatch.setattr(lifecycle, "wait_for_health", unexpected)

    with pytest.raises(RuntimeError, match="unclassified readiness failure"):
        lifecycle.start_service(observed, tmp_path)

    assert lifecycle.status_services(tmp_path).services == ()
    assert not psutil.pid_exists(spawned[0]) or not psutil.Process(spawned[0]).is_running()


def test_a_startup_failure_reports_the_log_for_later_classification(tmp_path, monkeypatch) -> None:
    """Carry the process log on the error, because it is the only evidence of why it died."""
    fast_health(monkeypatch)

    with pytest.raises(lifecycle.ServerStartupError) as captured:
        lifecycle.start_service(request(free_port(), "crash"), tmp_path)

    assert captured.value.log_path is not None
    assert captured.value.log_path.is_file()
