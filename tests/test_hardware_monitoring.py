"""Offline tests for evidence-only NVIDIA telemetry compatibility."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import bora_workbench._hardware_monitoring as monitoring


def test_optional_telemetry_is_parsed_without_becoming_a_threshold(monkeypatch) -> None:
    """Capture extrema inputs and a driver throttle flag from the aggregate memory query."""
    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="8192,7000,610.47,WDDM,75,67,1500,125,Power Brake\n"),
            SimpleNamespace(stdout="42\n"),
        ]
    )
    monkeypatch.setattr(monitoring.subprocess, "run", run)

    snapshot = monitoring.query_gpu_snapshot(0)

    assert snapshot.telemetry is not None
    assert snapshot.telemetry.utilization_percent == 75
    assert snapshot.telemetry.sm_clock_mhz == 1500
    assert snapshot.telemetry.throttle_reasons == ("Power Brake",)


def test_unsupported_telemetry_falls_back_to_mandatory_memory(monkeypatch) -> None:
    """Keep calibration usable when a driver rejects the evidence-only query fields."""
    failure = subprocess.CalledProcessError(1, ["nvidia-smi"])
    run = Mock(
        side_effect=[
            failure,
            SimpleNamespace(stdout="8192,7000,595.71.05,N/A\n"),
            SimpleNamespace(stdout="\n"),
        ]
    )
    monkeypatch.setattr(monitoring.subprocess, "run", run)

    snapshot = monitoring.query_gpu_snapshot(0)

    assert snapshot.telemetry is None
    assert snapshot.vram_free_gib == 7000 / 1024
