"""Offline tests for collision-free calibration trial port selection."""

from __future__ import annotations

import socket
from dataclasses import replace

from qwen_launcher._calibration_trial import TrialRunner
from qwen_launcher.config import Config
from tests.record_fixtures import cpu_hardware, record_target


def test_calibration_plans_avoid_an_occupied_configured_port(tmp_path) -> None:
    """Keep calibration usable while another local service already owns llama_port."""
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        target = replace(record_target(cpu_hardware()), config=Config(llama_port=port))
        runner = TrialRunner(target, target.modes[0], tmp_path)
        plan = runner._plan((8192, None))

    assert plan.port != port


def test_calibration_plans_use_the_configured_port_when_it_is_free(tmp_path) -> None:
    """Prefer the configured port so a trial stays observable at the documented address."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    target = replace(record_target(cpu_hardware()), config=Config(llama_port=port))

    plan = TrialRunner(target, target.modes[0], tmp_path)._plan((8192, None))

    assert plan.port == port
