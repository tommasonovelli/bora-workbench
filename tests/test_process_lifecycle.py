"""End-to-end lifecycle tests using the offline fake llama-server health surface."""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from unittest.mock import Mock

import psutil
import pytest

import bora_workbench._process_health as health
import bora_workbench.process as lifecycle
from bora_workbench._process_state import ServiceState, write_state
from bora_workbench.engine import load_engine_lock
from bora_workbench.profiles import LaunchPlan, load_catalog

_FAKE_SERVER = Path(__file__).parent / "fakes" / "fake_server.py"


def free_port() -> int:
    """Reserve and release one loopback port for an immediate fake-server start."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def plan(port: int, backend: str = "cpu") -> LaunchPlan:
    """Build one deterministic coding plan for process-only tests."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    return LaunchPlan(
        mode,
        "owner/model:file",
        Path("/resolved/model.gguf"),
        None,
        port,
        None,
        8192,
        48 if backend == "cuda" else None,
        backend,  # type: ignore[arg-type]
        0 if backend == "cuda" else None,
        (),
    )


def request(port: int, mode: str = "ready") -> lifecycle.StartRequest:
    """Build a fake subprocess request while retaining the real locked health contract."""
    command = (sys.executable, str(_FAKE_SERVER), "--port", str(port), "--health-mode", mode)
    return lifecycle.StartRequest(command, plan(port), load_engine_lock())


def fast_health(monkeypatch, *, timeout: float = 1.0) -> None:
    """Keep fake polling deterministic without weakening production timeout constants."""
    monkeypatch.setattr(health, "_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(health, "_LOAD_TIMEOUT_SECONDS", timeout)


def test_delayed_503_becomes_ready_and_stop_is_clean(tmp_path, monkeypatch) -> None:
    """Retry the observed loading status, persist identity, then stop the exact child."""
    fast_health(monkeypatch)
    port = free_port()
    delayed = lifecycle.StartRequest(
        (
            sys.executable,
            str(_FAKE_SERVER),
            "--port",
            str(port),
            "--health-mode",
            "delayed",
            "--delayed-requests",
            "2",
        ),
        plan(port),
        load_engine_lock(),
    )

    running = lifecycle.start_service(delayed, tmp_path)
    try:
        assert running.process.poll() is None
        assert lifecycle.status_services(tmp_path).services[0].pid == running.process.pid
        assert Path(running.state.log_path).is_file()
    finally:
        report = lifecycle.stop_services(tmp_path)
    assert report.stopped == ("llama-server",)


@pytest.mark.parametrize(
    "mode,match", [("incompatible", "incompatible ready body"), ("crash", None)]
)
def test_incompatible_health_and_crash_fail_with_log(tmp_path, monkeypatch, mode, match) -> None:
    """Fail immediately on incompatible 200 or process death and always expose the log path."""
    fast_health(monkeypatch)

    with pytest.raises(lifecycle.ProcessError, match=match) as captured:
        lifecycle.start_service(request(free_port(), mode), tmp_path)

    assert "log" in str(captured.value).casefold() or tuple((tmp_path / "logs").glob("*.log"))
    assert lifecycle.status_services(tmp_path).services == ()


def test_spawn_callback_exposes_pid_before_readiness_failure(tmp_path, monkeypatch) -> None:
    """Expose candidate identity early enough for VRAM monitoring when startup later crashes."""
    fast_health(monkeypatch)
    pids: list[int] = []
    failed = request(free_port(), "crash")
    observed = lifecycle.StartRequest(failed.command, failed.plan, failed.lock, pids.append)

    with pytest.raises(lifecycle.ProcessError):
        lifecycle.start_service(observed, tmp_path)

    assert len(pids) == 1


def test_loading_timeout_stops_child_and_cleans_state(tmp_path, monkeypatch) -> None:
    """Bound perpetual 503 polling and leave no managed child or live state behind."""
    fast_health(monkeypatch, timeout=0.05)

    with pytest.raises(lifecycle.ProcessError, match="15 minutes"):
        lifecycle.start_service(request(free_port(), "loading"), tmp_path)

    assert lifecycle.status_services(tmp_path).services == ()


def test_occupied_port_fails_before_spawn(tmp_path, monkeypatch) -> None:
    """Reject a loopback collision before opening a process log or loading a model."""
    fast_health(monkeypatch)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        with pytest.raises(lifecycle.ProcessError, match="already occupied"):
            lifecycle.start_service(request(port), tmp_path)
    assert not (tmp_path / "logs").exists()


def test_second_start_rejected_while_managed_service_lives(tmp_path, monkeypatch) -> None:
    """Use persisted process identity to reject a second launch after preflight lock release."""
    fast_health(monkeypatch)
    running = lifecycle.start_service(request(free_port()), tmp_path)
    try:
        with pytest.raises(lifecycle.ProcessError, match="already running"):
            lifecycle.start_service(request(free_port()), tmp_path)
    finally:
        lifecycle.stop_services(tmp_path)
    assert running.process.poll() is not None


def test_cuda_child_environment_does_not_mutate_parent(monkeypatch) -> None:
    """Set the selected concrete GPU only in a copied child environment."""
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "parent")

    child = lifecycle._child_environment(plan(8080, "cuda"))

    assert child["CUDA_VISIBLE_DEVICES"] == "0"
    assert lifecycle.os.environ["CUDA_VISIBLE_DEVICES"] == "parent"


def test_ctrl_c_uses_stop_cleanup_and_preserves_exit_signal(tmp_path) -> None:
    """Remove exact state after foreground interruption and re-raise for CLI exit 130 mapping."""
    current = psutil.Process()
    state = ServiceState(
        "llama-server",
        current.pid,
        current.create_time(),
        sys.executable,
        8080,
        "2026-07-16T00:00:00Z",
        str(tmp_path / "server.log"),
        "coding",
        "owner/model:file",
        "b10011",
        None,
        8192,
        None,
        "cpu",
        None,
    )
    write_state(tmp_path, (state,))
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [KeyboardInterrupt, 0]
    running = lifecycle.RunningService(process, state)

    with pytest.raises(KeyboardInterrupt):
        lifecycle.wait_foreground(running, tmp_path)

    assert lifecycle.status_services(tmp_path).services == ()
    process.terminate.assert_called_once()
