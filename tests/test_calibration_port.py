"""Offline tests for collision-free calibration trial port selection."""

from __future__ import annotations

import socket
from dataclasses import replace
from types import SimpleNamespace

import qwen_launcher._calibration_runner as v1_runner
from qwen_launcher._calibration_v5_plan import build_plan
from qwen_launcher.calibration import Candidate
from qwen_launcher.config import Config
from tests.test_calibration import cpu_target


def test_calibration_plans_avoid_an_occupied_configured_port() -> None:
    """Keep both calibration protocols usable while another local service owns llama_port."""
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        target = replace(cpu_target(), config=Config(llama_port=port))
        v1_plan = v1_runner._plan(target, target.modes[0], Candidate("safe", 8192, None))
        run = SimpleNamespace(target=target, mode=target.modes[0])
        v3_plan = build_plan(run, 8192, None)

    assert v1_plan.port != port
    assert v3_plan.port != port
