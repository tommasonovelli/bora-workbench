"""End-to-end lifecycle tests using the offline fake llama-server health surface.

The fake server replaces llama.cpp entirely, so nothing here loads a model, opens a network
connection beyond loopback, or touches a GPU. The failure tests all assert the same contract from
different angles: a start that does not reach readiness leaves neither a live child nor a
registered service.
"""

from __future__ import annotations

import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import httpx
import psutil
import pytest

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


def ui_plan(mode_id: str, port: int) -> LaunchPlan:
    """Build one deterministic CPU plan for a packaged integrated-UI mode."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    projector = Path("/resolved/mmproj.gguf") if mode.services.vision else None
    return LaunchPlan(
        mode,
        "owner/model:file",
        Path("/resolved/model.gguf"),
        projector,
        port,
        None,
        8192,
        None,
        "cpu",
        None,
        (),
        speculative="disabled" if mode.services.vision else "mtp2",
    )


def request(port: int, mode: str = "ready") -> lifecycle.StartRequest:
    """Build a fake subprocess request while retaining the real locked health contract."""
    command = (sys.executable, str(_FAKE_SERVER), "--port", str(port), "--health-mode", mode)
    return lifecycle.StartRequest(command, plan(port), load_engine_lock())


def fast_health(monkeypatch, *, timeout: float = 1.0) -> None:
    """Keep fake polling deterministic without weakening production timeout constants."""
    monkeypatch.setattr(lifecycle, "_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(lifecycle, "_LOAD_TIMEOUT_SECONDS", timeout)


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


@pytest.mark.parametrize("mode_id", ["studio", "vstudio"])
def test_ui_mode_reaches_ready_interface_and_cleans_state(tmp_path, monkeypatch, mode_id) -> None:
    """Start each UI mode against the fake, reach its root, and stop without stale state."""
    fast_health(monkeypatch)
    port = free_port()
    plan_for_mode = ui_plan(mode_id, port)
    command = (sys.executable, str(_FAKE_SERVER), "--port", str(port))

    running = lifecycle.start_service(
        lifecycle.StartRequest(command, plan_for_mode, load_engine_lock()), tmp_path
    )
    try:
        response = httpx.get(f"http://127.0.0.1:{port}/", timeout=2)
        assert response.status_code == 200
        assert running.state.mode == mode_id
        assert plan_for_mode.mode.services.ui is True
        assert (plan_for_mode.mmproj_path is not None) is (mode_id == "vstudio")
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

    with pytest.raises(lifecycle.ProcessError, match="did not become ready"):
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
        "engine",
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


def test_external_stop_lock_does_not_escape_foreground_as_a_traceback(
    tmp_path, monkeypatch
) -> None:
    """Let the serialized stop own cleanup while mapping the terminated child operationally."""
    state = _cleanup_state(request(8080), tmp_path)
    process = Mock()
    process.wait.return_value = -15
    running = lifecycle.RunningService(process, state)
    monkeypatch.setattr(
        lifecycle,
        "acquire_start_lock",
        lambda root: (_ for _ in ()).throw(lifecycle.StartLockError("stop owns lock")),
    )

    with pytest.raises(lifecycle.ProcessError, match="exited with code -15"):
        lifecycle.wait_foreground(running, tmp_path)


def test_a_transport_reset_is_read_as_not_ready_not_leaked(tmp_path, monkeypatch) -> None:
    """Treat the connection reset a dying server produces as "not ready", never as an escape.

    A leaked transport error would bypass the caller's cleanup and leave a phantom service.
    """
    fast_health(monkeypatch, timeout=0.05)

    def reset(*args: object, **kwargs: object) -> None:
        """Fail every poll the way a dying server's socket does."""
        raise httpx.ReadError("[Errno 104] Connection reset by peer")

    monkeypatch.setattr(lifecycle.httpx, "get", reset)

    with pytest.raises(lifecycle.ProcessError, match="did not become ready"):
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
        """Raise a failure class the start path does not classify as expected."""
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


def _cleanup_state(current: lifecycle.StartRequest, root: Path) -> ServiceState:
    """Build the persisted identity used by the interrupted-cleanup regression."""
    return ServiceState(
        "llama-server",
        123,
        1.0,
        current.command[0],
        current.plan.port,
        "2026-07-26T00:00:00Z",
        str(root / "server.log"),
        "coding",
        "engine",
        current.plan.model,
        "b10011",
        None,
        8192,
        None,
        "cpu",
        None,
    )


def test_failed_start_cleanup_preserves_interrupt_and_attempts_state_removal(
    tmp_path, monkeypatch
) -> None:
    """Try every cleanup action without allowing its failure to replace Ctrl-C."""
    fake_process = Mock(pid=123)
    fake_process.poll.return_value = None
    current = request(free_port())
    state = _cleanup_state(current, tmp_path)
    removed: list[ServiceState] = []
    monkeypatch.setattr(lifecycle.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    monkeypatch.setattr(lifecycle, "_service_state", lambda *args: state)
    monkeypatch.setattr(
        lifecycle,
        "wait_for_health",
        lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        lifecycle,
        "terminate_popen",
        lambda process: (_ for _ in ()).throw(RuntimeError("terminate failed")),
    )
    monkeypatch.setattr(lifecycle, "remove_service", lambda root, service: removed.append(service))

    with pytest.raises(KeyboardInterrupt):
        lifecycle.start_service(current, tmp_path)

    assert removed == [state]


def test_log_paths_are_unique_even_at_the_same_timestamp(tmp_path, monkeypatch) -> None:
    """Prevent a fast retry from colliding with the preceding trial's server log."""

    class _FixedDateTime:
        """Return one instant for every log-path request."""

        @classmethod
        def now(cls, zone):
            """Return the fixed aware timestamp."""
            assert zone is UTC
            return datetime(2026, 7, 26, tzinfo=UTC)

    monkeypatch.setattr(lifecycle, "datetime", _FixedDateTime)

    assert lifecycle._log_path(tmp_path, "llama-server") != lifecycle._log_path(
        tmp_path, "llama-server"
    )
