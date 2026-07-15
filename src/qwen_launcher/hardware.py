"""Detect CPU, RAM, and NVIDIA GPUs without changing the host environment.

This is one of the four modules allowed to branch on the operating system. NVIDIA discovery uses the
read-only ``nvidia-smi`` query fixed by specification section 5.4; failures select CPU with an
explicit diagnostic instead of crashing or pretending CUDA is available.
"""

from __future__ import annotations

import csv
import platform
import subprocess
from dataclasses import dataclass
from io import StringIO
from typing import Literal

import psutil

_GIB_BYTES = 1024**3
_NVIDIA_QUERY = [
    "nvidia-smi",
    "--query-gpu=index,name,memory.total,memory.free",
    "--format=csv,noheader,nounits",
]


class HardwareError(RuntimeError):
    """Report a blocking failure to obtain required host facts."""


@dataclass(frozen=True, slots=True)
class _GpuInfo:
    """Hold one parsed NVIDIA device before deterministic selection."""

    index: int
    name: str
    vram_total_gib: float
    vram_free_gib: float


@dataclass(frozen=True, slots=True)
class _HostInfo:
    """Hold platform, CPU, and RAM facts shared by CPU and CUDA results."""

    os_name: str
    os_version: str
    cpu_name: str
    cpu_cores: int
    ram_total_gib: float
    ram_available_gib: float
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HardwareInfo:
    """Describe exact detected capacities without assigning nominal hardware classes."""

    os_name: str
    os_version: str
    cpu_name: str
    cpu_cores: int
    ram_total_gib: float
    ram_available_gib: float
    backend: Literal["cuda", "cpu"]
    gpu_count: int
    gpu_index: int | None
    gpu_name: str | None
    vram_total_gib: float | None
    vram_free_gib: float | None
    warnings: tuple[str, ...] = ()


def bytes_to_gib(value: int) -> float:
    """Convert bytes to exact GiB using the binary divisor required by section 5.4."""
    return value / _GIB_BYTES


def mib_to_gib(value: float) -> float:
    """Convert MiB reported by NVIDIA tooling to exact GiB."""
    return value / 1024


def _parse_gpu_row(row: list[str]) -> _GpuInfo:
    """Parse and validate one four-column ``nvidia-smi`` row."""
    if len(row) != 4:
        raise ValueError("expected four columns")
    index_text, name, total_text, free_text = (value.strip() for value in row)
    index = int(index_text)
    total_mib = float(total_text)
    free_mib = float(free_text)
    if index < 0 or not name or total_mib <= 0 or not 0 <= free_mib <= total_mib:
        raise ValueError("GPU values are outside their valid ranges")
    return _GpuInfo(index, name, mib_to_gib(total_mib), mib_to_gib(free_mib))


def _parse_gpus(output: str) -> tuple[_GpuInfo, ...]:
    """Parse complete CSV output and reject empty or duplicate device data."""
    rows = [row for row in csv.reader(StringIO(output)) if any(value.strip() for value in row)]
    if not rows:
        raise ValueError("no GPU rows returned")
    gpus = tuple(_parse_gpu_row(row) for row in rows)
    if len({gpu.index for gpu in gpus}) != len(gpus):
        raise ValueError("duplicate GPU index")
    return gpus


def _query_gpus() -> tuple[tuple[_GpuInfo, ...], tuple[str, ...]]:
    """Run the bounded NVIDIA query and map expected failures to CPU diagnostics."""
    try:
        result = subprocess.run(
            _NVIDIA_QUERY,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except FileNotFoundError:
        return (), ("nvidia-smi was not found; using the CPU backend.",)
    except subprocess.TimeoutExpired:
        return (), ("nvidia-smi timed out after 5 seconds; check the NVIDIA driver.",)
    except subprocess.CalledProcessError as error:
        message = f"nvidia-smi exited with code {error.returncode}; check the NVIDIA driver."
        return (), (message,)
    try:
        return _parse_gpus(result.stdout), ()
    except (TypeError, ValueError):
        return (), ("nvidia-smi returned malformed GPU data; using the CPU backend.",)


def _select_gpu(gpus: tuple[_GpuInfo, ...]) -> _GpuInfo:
    """Choose greatest total VRAM, breaking ties by the lowest numeric index."""
    return max(gpus, key=lambda gpu: (gpu.vram_total_gib, -gpu.index))


def _cpu_name() -> tuple[str, tuple[str, ...]]:
    """Return the platform CPU label and a diagnostic when the OS omits it."""
    name = platform.processor().strip()
    if name:
        return name, ()
    return "unavailable", ("The operating system did not report a CPU model name.",)


def _detect_host() -> _HostInfo:
    """Read required platform, CPU, and RAM facts or raise an actionable error."""
    memory = psutil.virtual_memory()
    cpu_cores = psutil.cpu_count(logical=True)
    if cpu_cores is None or cpu_cores < 1:
        raise HardwareError("cannot determine logical CPU cores; check operating system reporting")
    cpu_name, warnings = _cpu_name()
    return _HostInfo(
        platform.system().lower(),
        platform.version(),
        cpu_name,
        cpu_cores,
        bytes_to_gib(memory.total),
        bytes_to_gib(memory.available),
        warnings,
    )


def detect_hardware() -> HardwareInfo:
    """Detect required host facts without network, files, or parent-environment mutation."""
    host = _detect_host()
    gpus, gpu_warnings = _query_gpus()
    warnings = host.warnings + gpu_warnings
    common = (
        host.os_name,
        host.os_version,
        host.cpu_name,
        host.cpu_cores,
        host.ram_total_gib,
        host.ram_available_gib,
    )
    if not gpus:
        return HardwareInfo(*common, "cpu", 0, None, None, None, None, warnings)
    selected = _select_gpu(gpus)
    if len(gpus) > 1:
        warnings += ("Multiple NVIDIA GPUs detected; CUDA startup remains blocked until Step 3.",)
    return HardwareInfo(
        *common,
        "cuda",
        len(gpus),
        selected.index,
        selected.name,
        selected.vram_total_gib,
        selected.vram_free_gib,
        warnings,
    )
