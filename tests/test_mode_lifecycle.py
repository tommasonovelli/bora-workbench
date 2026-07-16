"""End-to-end fake-server lifecycle tests for the integrated UI modes."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import httpx
import pytest

import qwen_launcher._process_health as health
from qwen_launcher.engine import load_engine_lock
from qwen_launcher.process import StartRequest, start_service, stop_services
from qwen_launcher.profiles import LaunchPlan, load_catalog

_FAKE_SERVER = Path(__file__).parent / "fakes" / "fake_server.py"


def free_port() -> int:
    """Reserve and release one loopback port for an immediate fake-server start."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


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
    )


@pytest.mark.parametrize("mode_id", ["studio", "vstudio"])
def test_ui_mode_reaches_ready_interface_and_cleans_state(tmp_path, monkeypatch, mode_id) -> None:
    """Start each UI mode against the fake, reach its root, and stop without stale state."""
    monkeypatch.setattr(health, "_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(health, "_LOAD_TIMEOUT_SECONDS", 1.0)
    port = free_port()
    plan = ui_plan(mode_id, port)
    command = (sys.executable, str(_FAKE_SERVER), "--port", str(port))

    running = start_service(StartRequest(command, plan, load_engine_lock()), tmp_path)
    try:
        response = httpx.get(f"http://127.0.0.1:{port}/", timeout=2)
        assert response.status_code == 200
        assert running.state.mode == mode_id
        assert plan.mode.services.ui is True
        assert (plan.mmproj_path is not None) is (mode_id == "vstudio")
    finally:
        report = stop_services(tmp_path)

    assert report.stopped == ("llama-server",)
