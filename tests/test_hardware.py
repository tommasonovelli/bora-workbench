"""Deterministic hardware tests: discovery, GPU monitoring, and opaque process identity.

Every NVIDIA fact is served by a fake `subprocess.run`, so the suite never touches a real GPU.
"""

from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import bora_workbench.hardware as hardware
from bora_workbench.hardware import identify_gpu_process

_GIB = 1024**3


def patch_host(monkeypatch, *, total: int = 32 * _GIB, available: int = 24 * _GIB) -> None:
    """Replace host RAM, CPU, and platform probes with deterministic values."""
    memory = SimpleNamespace(total=total, available=available)
    monkeypatch.setattr(hardware.psutil, "virtual_memory", lambda: memory)
    monkeypatch.setattr(hardware.psutil, "cpu_count", lambda logical: 12)
    monkeypatch.setattr(hardware.platform, "processor", lambda: "Test CPU")
    monkeypatch.setattr(hardware.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hardware.platform, "version", lambda: "test-version")


class _Process:
    """Expose deterministic psutil process lifecycle and executable facts."""

    def __init__(self, pid: int) -> None:
        """Retain the PID so separate instances receive separate create times."""
        self.pid = pid

    def create_time(self) -> float:
        """Return one positive instance timestamp."""
        return float(self.pid)

    def exe(self) -> str:
        """Return an unpersisted fake path whose stat identity drives matching."""
        return "C:/Program Files/Test/app.exe"


def test_binary_memory_conversions() -> None:
    """Convert bytes and MiB with binary rather than decimal units."""
    assert hardware.bytes_to_gib(3 * _GIB) == 3
    assert hardware.mib_to_gib(8192) == 8


def test_missing_nvidia_smi_uses_cpu_with_warning(monkeypatch) -> None:
    """Treat an absent NVIDIA utility as a diagnosed CPU backend."""
    patch_host(monkeypatch)
    run = Mock(side_effect=FileNotFoundError)
    monkeypatch.setattr(hardware.subprocess, "run", run)

    info = hardware.detect_hardware()

    assert info.backend == "cpu"
    assert info.ram_total_gib == 32
    assert info.ram_available_gib == 24
    assert info.gpu_count == 0
    assert info.gpu_index is None
    assert "not found" in info.warnings[-1]


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.TimeoutExpired("nvidia-smi", 5),
        subprocess.CalledProcessError(9, "nvidia-smi"),
    ],
)
def test_failed_nvidia_query_uses_cpu(monkeypatch, failure) -> None:
    """Map timeout and non-zero exit to actionable CPU diagnostics."""
    patch_host(monkeypatch)
    monkeypatch.setattr(hardware.subprocess, "run", Mock(side_effect=failure))

    info = hardware.detect_hardware()

    assert info.backend == "cpu"
    assert info.warnings


@pytest.mark.parametrize(
    "output",
    [
        "",
        "zero, GPU, 8192, 7000\n",
        "0, GPU, invalid, 7000\n",
        "0, GPU, 8192\n",
        "0, GPU, 8192, 9000\n",
        "0, GPU, inf, 7000\n",
        "0, GPU, 8192, inf\n",
        "0, GPU A, 8192, 7000\n0, GPU B, 8192, 6000\n",
    ],
)
def test_malformed_nvidia_output_uses_cpu(monkeypatch, output) -> None:
    """Reject incomplete, invalid, impossible, or duplicate GPU rows."""
    patch_host(monkeypatch)
    result = SimpleNamespace(stdout=output)
    monkeypatch.setattr(hardware.subprocess, "run", Mock(return_value=result))

    info = hardware.detect_hardware()

    assert info.backend == "cpu"
    assert "malformed" in info.warnings[-1]


def test_gpu_selection_prefers_total_vram_then_index(monkeypatch) -> None:
    """Select maximum total VRAM and lowest index on an exact tie."""
    patch_host(monkeypatch)
    output = "2, GPU Two, 12288, 9000\n1, GPU One, 12288, 8000\n0, Small, 8192, 7000\n"
    run = Mock(return_value=SimpleNamespace(stdout=output))
    monkeypatch.setattr(hardware.subprocess, "run", run)

    info = hardware.detect_hardware()

    assert info.backend == "cuda"
    assert info.gpu_count == 3
    assert info.gpu_index == 1
    assert info.gpu_name == "GPU One"
    assert info.vram_total_gib == 12
    assert info.vram_free_gib == 8000 / 1024
    assert "Multiple NVIDIA GPUs" in info.warnings[-1]
    _, kwargs = run.call_args
    assert kwargs["timeout"] == 5
    assert "shell" not in kwargs


def test_multi_gpu_cuda_startup_is_blocked_by_unverified_spike_boundary(monkeypatch) -> None:
    """Refuse to promise physical GPU selection that the single-GPU spike did not prove."""
    patch_host(monkeypatch)
    output = "0, GPU Zero, 8192, 7000\n1, GPU One, 8192, 7000\n"
    monkeypatch.setattr(
        hardware.subprocess, "run", Mock(return_value=SimpleNamespace(stdout=output))
    )
    info = hardware.detect_hardware()

    with pytest.raises(hardware.HardwareError, match="multi-GPU hosts"):
        hardware.ensure_launch_supported(info)


def test_detection_does_not_mutate_parent_cuda_environment(monkeypatch) -> None:
    """Leave CUDA_VISIBLE_DEVICES untouched because only launch mutates child environments."""
    patch_host(monkeypatch)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "parent-value")
    result = SimpleNamespace(stdout="0, Test GPU, 8192, 7000\n")
    monkeypatch.setattr(hardware.subprocess, "run", Mock(return_value=result))

    hardware.detect_hardware()

    assert os.environ["CUDA_VISIBLE_DEVICES"] == "parent-value"


def test_missing_cpu_count_is_blocking(monkeypatch) -> None:
    """Reject a host that cannot report the required logical CPU count."""
    patch_host(monkeypatch)
    monkeypatch.setattr(hardware.psutil, "cpu_count", lambda logical: None)

    with pytest.raises(hardware.HardwareError, match="logical CPU cores"):
        hardware.detect_hardware()


def test_optional_telemetry_is_parsed_without_becoming_a_threshold(monkeypatch) -> None:
    """Capture extrema inputs and a driver throttle flag from the aggregate memory query."""
    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="8192,7000,610.47,WDDM,75,67,1500,125,Power Brake\n"),
            SimpleNamespace(stdout="42\n"),
        ]
    )
    monkeypatch.setattr(hardware.subprocess, "run", run)

    snapshot = hardware.query_gpu_snapshot(0)

    assert snapshot.telemetry is not None
    assert snapshot.telemetry.utilization_percent == 75
    assert snapshot.telemetry.sm_clock_mhz == 1500
    assert snapshot.telemetry.throttle_reasons == ("Power Brake",)


def test_nonfinite_mandatory_memory_is_rejected_and_optional_telemetry_is_ignored(
    monkeypatch,
) -> None:
    """Reject infinite VRAM decisions while degrading non-finite evidence fields to null."""
    invalid = Mock(
        return_value=SimpleNamespace(stdout="inf,7000,610.47,WDDM,inf,67,1500,125,None\n")
    )
    monkeypatch.setattr(hardware.subprocess, "run", invalid)
    with pytest.raises(hardware.HardwareError, match="invalid calibration memory"):
        hardware.query_gpu_snapshot(0)

    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="8192,7000,610.47,WDDM,inf,67,1500,125,None\n"),
            SimpleNamespace(stdout="\n"),
        ]
    )
    monkeypatch.setattr(hardware.subprocess, "run", run)

    snapshot = hardware.query_gpu_snapshot(0)

    assert snapshot.telemetry is not None
    assert snapshot.telemetry.utilization_percent is None


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
    monkeypatch.setattr(hardware.subprocess, "run", run)

    snapshot = hardware.query_gpu_snapshot(0)

    assert snapshot.telemetry is None
    assert snapshot.vram_free_gib == 7000 / 1024


def test_two_process_instances_stay_distinct(monkeypatch) -> None:
    """Keep pid and create time together, because a recycled PID is not the same process."""
    monkeypatch.setattr(hardware.psutil, "Process", _Process)

    first = identify_gpu_process(100)
    replacement = identify_gpu_process(200)

    assert first.instance != replacement.instance
    assert first.create_time is not None and replacement.create_time is not None


@pytest.mark.parametrize("failure", ["process", "create-time"])
def test_identity_resolution_reports_an_unresolved_lifecycle(monkeypatch, failure: str) -> None:
    """Record an absent create time for a process this account cannot open or that vanished.

    A Windows compute context often belongs to a service account, so refusing to resolve it must
    stay a fact the caller can act on rather than a failure that ends a run (D-071).
    """
    if failure == "process":
        monkeypatch.setattr(
            hardware.psutil,
            "Process",
            lambda pid: (_ for _ in ()).throw(hardware.psutil.AccessDenied(pid)),
        )
    else:
        process = _Process(100)
        monkeypatch.setattr(process, "create_time", lambda: 0.0)
        monkeypatch.setattr(hardware.psutil, "Process", lambda pid: process)

    identity = identify_gpu_process(100)

    assert identity.pid == 100
    assert identity.create_time is None
