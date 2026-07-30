"""Lifecycle tests for the second managed service, using the offline fake HTTP surface.

The interface is started with the same fake server the engine tests use, so nothing here installs
Open WebUI, reaches the network beyond loopback, or runs a real interface. What is asserted is the
part that has to hold whatever program sits behind the port: the two roles coexist, only one of
each may run, readiness comes from `/ready`, and stop takes the interface down first.
"""

from __future__ import annotations

import os
import socket
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import bora_workbench.process as lifecycle
from bora_workbench._process_state import ENGINE_ROLE, INTERFACE_ROLE
from bora_workbench.webui import readiness_contract
from tests.test_process_lifecycle import fast_health, free_port, request

_FAKE_SERVER = Path(__file__).parent / "fakes" / "fake_server.py"


# A shortened deadline is an upper bound, not a wait: a fake server that answers reaches READY in
# well under a second and the loop returns immediately, so this only bounds a genuine hang. It is
# generous because a Windows runner spawning a second Python beside a live one is not fast, and a
# tight bound there fails a test that has nothing wrong with it.
_TEST_TIMEOUT_SECONDS = 30.0
_NEVER_READY_TIMEOUT_SECONDS = 0.2


@pytest.fixture(autouse=True)
def stop_managed_services(tmp_path):
    """Stop whatever the test started, including a start that spawned and then failed.

    A start that raises after spawning is cleaned up by the process layer, but a start that
    succeeded earlier in the same test is not, so without this a failing assertion would leave a
    live fake server behind and the next test would inherit it.
    """
    yield
    lifecycle.stop_services(tmp_path)


def interface_request(
    port: int, mode: str = "ready", timeout: float = _TEST_TIMEOUT_SECONDS
) -> lifecycle.InterfaceRequest:
    """Build one fake interface launch carrying the real Open WebUI readiness contract.

    Only the deadline is shortened, and it is shortened on the request rather than on a module
    constant, so every rule the contract states is the one production uses.

    The environment inherits the parent's, exactly as `launch_environment` does. An empty mapping
    would be a fiction: Windows cannot start a process without `SystemRoot`, so the child would die
    immediately for a reason that has nothing to do with what is being tested.
    """
    command = (sys.executable, str(_FAKE_SERVER), "--port", str(port), "--health-mode", mode)
    readiness = replace(readiness_contract(port), timeout_seconds=timeout)
    return lifecycle.InterfaceRequest(command, dict(os.environ), port, "studio", readiness)


def test_the_engine_and_the_interface_run_beside_each_other(tmp_path, monkeypatch) -> None:
    """Admit one managed service per role, because a UI mode needs both at once."""
    fast_health(monkeypatch)
    lifecycle.start_service(request(free_port()), tmp_path)
    lifecycle.start_interface(interface_request(free_port()), tmp_path)

    report = lifecycle.status_services(tmp_path)

    assert sorted(service.role for service in report.services) == [ENGINE_ROLE, INTERFACE_ROLE]


def test_a_second_interface_is_refused_while_one_lives(tmp_path, monkeypatch) -> None:
    """Keep the single-service rule per role rather than dropping it to admit the pair."""
    fast_health(monkeypatch)
    lifecycle.start_interface(interface_request(free_port()), tmp_path)

    with pytest.raises(lifecycle.ProcessError, match="interface is already running"):
        lifecycle.start_interface(interface_request(free_port()), tmp_path)


def test_an_engine_still_refuses_a_second_engine(tmp_path, monkeypatch) -> None:
    """Leave the engine's own invariant exactly as strict as it was before the second role."""
    fast_health(monkeypatch)
    lifecycle.start_service(request(free_port()), tmp_path)

    with pytest.raises(lifecycle.ProcessError, match="engine is already running"):
        lifecycle.start_service(request(free_port()), tmp_path)


def test_liveness_alone_is_never_read_as_readiness(tmp_path, monkeypatch) -> None:
    """Refuse to call an interface ready while `/health` answers 200 and `/ready` answers 503."""
    fast_health(monkeypatch)

    with pytest.raises(lifecycle.ProcessError, match="did not become ready"):
        lifecycle.start_interface(
            interface_request(free_port(), "startup", _NEVER_READY_TIMEOUT_SECONDS), tmp_path
        )

    assert lifecycle.status_services(tmp_path).services == ()


def test_the_production_deadline_is_the_one_the_contract_declares() -> None:
    """Keep the real first-start allowance well above the shortened one the tests use."""
    assert readiness_contract(8081).timeout_seconds >= 5 * 60


def test_an_occupied_interface_port_fails_before_any_process_starts(tmp_path, monkeypatch) -> None:
    """Reject a loopback collision on the interface port the same way the engine port is."""
    fast_health(monkeypatch)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        with pytest.raises(lifecycle.ProcessError, match="already occupied"):
            lifecycle.start_interface(interface_request(port), tmp_path)
    assert not (tmp_path / "logs").exists()


def test_stop_takes_the_interface_down_before_the_engine(tmp_path, monkeypatch) -> None:
    """Never leave a live page talking to a server that is already terminating."""
    fast_health(monkeypatch)
    lifecycle.start_service(request(free_port()), tmp_path)
    lifecycle.start_interface(interface_request(free_port()), tmp_path)
    order: list[str] = []
    original = lifecycle._terminate_service

    def record(service):
        """Note the role each stop reaches, in the order the stop loop reaches it."""
        order.append(service.role)
        return original(service)

    monkeypatch.setattr(lifecycle, "_terminate_service", record)

    lifecycle.stop_services(tmp_path)

    assert order == [INTERFACE_ROLE, ENGINE_ROLE]


def test_stopping_the_interface_leaves_the_engine_running(tmp_path, monkeypatch) -> None:
    """Keep the model serving when only the interface is released, as the fallback requires."""
    fast_health(monkeypatch)
    engine = lifecycle.start_service(request(free_port()), tmp_path)
    interface = lifecycle.start_interface(interface_request(free_port()), tmp_path)

    lifecycle.stop_interface(interface, tmp_path)

    report = lifecycle.status_services(tmp_path)
    assert [service.role for service in report.services] == [ENGINE_ROLE]
    assert engine.process.poll() is None


def test_the_interface_record_claims_no_engine_envelope(tmp_path, monkeypatch) -> None:
    """Store no context window or backend for a process that serves no model."""
    fast_health(monkeypatch)
    running = lifecycle.start_interface(interface_request(free_port()), tmp_path)

    state = running.state
    assert state.role == INTERFACE_ROLE
    assert state.ctx is None
    assert state.backend is None
    assert state.model is None
    assert state.mode == "studio"
