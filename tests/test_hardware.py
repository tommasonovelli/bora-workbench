"""Deterministic tests for hardware discovery without real GPU or host dependencies."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import qwen_launcher.hardware as hardware

_GIB = 1024**3


def patch_host(monkeypatch, *, total: int = 32 * _GIB, available: int = 24 * _GIB) -> None:
    """Replace host RAM, CPU, and platform probes with deterministic values."""
    memory = SimpleNamespace(total=total, available=available)
    monkeypatch.setattr(hardware.psutil, "virtual_memory", lambda: memory)
    monkeypatch.setattr(hardware.psutil, "cpu_count", lambda logical: 12)
    monkeypatch.setattr(hardware.platform, "processor", lambda: "Test CPU")
    monkeypatch.setattr(hardware.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hardware.platform, "version", lambda: "test-version")


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
        hardware.subprocess.TimeoutExpired("nvidia-smi", 5),
        hardware.subprocess.CalledProcessError(9, "nvidia-smi"),
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
    """Leave CUDA_VISIBLE_DEVICES untouched because only Step 3 builds child environments."""
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
