"""Detect CPU, RAM, and NVIDIA devices, and observe the selected GPU during calibration.

This is one of the four modules allowed to branch on the operating system (specification section
4.1). Every NVIDIA fact comes from the read-only ``nvidia-smi`` queries fixed by specification
section 5.4, always invoked without a shell and under a bounded timeout.

Discovery and monitoring answer to different contracts, so they map the same failure differently.
`detect_hardware` runs before any decision and must neither crash nor pretend CUDA is available, so
a failed query selects the CPU backend with an explicit diagnostic. `query_gpu_snapshot` runs while
calibration is already committed to one GPU, so a failed query is a blocking `HardwareError`:
degrading silently there would turn missing evidence into a measurement.
"""

from __future__ import annotations

import csv
import hashlib
import os
import platform
import subprocess
from dataclasses import dataclass
from io import StringIO
from typing import Literal

import psutil

_GIB_BYTES = 1024**3
_TIMEOUT_SECONDS = 5
_NVIDIA_QUERY = [
    "nvidia-smi",
    "--query-gpu=index,name,memory.total,memory.free",
    "--format=csv,noheader,nounits",
]
_BASE_FIELDS = "memory.total,memory.free,driver_version,driver_model.current"
_TELEMETRY_FIELDS = (
    "utilization.gpu,temperature.gpu,clocks.current.sm,power.draw,clocks_event_reasons.active"
)
_UNAVAILABLE = {"", "n/a", "[n/a]", "not supported", "[not supported]"}


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


@dataclass(frozen=True, slots=True)
class GpuProcessIdentity:
    """Identify one process instance and its executable file without exposing a path."""

    pid: int
    create_time: float | None
    executable_id: str | None

    @property
    def is_complete(self) -> bool:
        """Return whether lifecycle and executable identity were both measured."""
        return self.create_time is not None and self.executable_id is not None

    @property
    def instance(self) -> tuple[int, float | None]:
        """Return the process lifecycle key used to prevent PID-reuse exclusions."""
        return self.pid, self.create_time


@dataclass(frozen=True, slots=True)
class GpuTelemetry:
    """Hold best-effort telemetry reported by one selected-GPU query."""

    utilization_percent: float | None
    temperature_celsius: float | None
    sm_clock_mhz: float | None
    power_draw_watts: float | None
    throttle_reasons: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class GpuSnapshot:
    """Record VRAM, driver model, process contexts, and optional telemetry at one instant."""

    vram_total_gib: float
    vram_free_gib: float
    driver_version: str
    compute_pids: tuple[int, ...]
    is_wddm: bool = False
    telemetry: GpuTelemetry | None = None
    compute_contexts: tuple[GpuProcessIdentity, ...] | None = None


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
            timeout=_TIMEOUT_SECONDS,
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


def ensure_launch_supported(hardware: HardwareInfo) -> None:
    """Block unverified CUDA multi-GPU startup as required by Spike 0 evidence."""
    if hardware.backend == "cuda" and hardware.gpu_count > 1:
        message = (
            "CUDA startup on multi-GPU hosts is not verified for llama.cpp b10011; "
            "use a single-GPU host or disable extra GPUs before launching"
        )
        raise HardwareError(message)


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
        warnings += ("Multiple NVIDIA GPUs detected; CUDA startup is blocked in version 0.1.",)
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


def _file_identifier(path: str) -> str | None:
    """Hash the local volume/file identity so aliases and private paths are not retained."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    if status.st_ino <= 0:
        return None
    value = f"{status.st_dev}:{status.st_ino}".encode()
    return hashlib.sha256(value).hexdigest()


def identify_gpu_process(pid: int) -> GpuProcessIdentity:
    """Resolve one PID fail-closed while retaining any trustworthy lifecycle identity."""
    try:
        process = psutil.Process(pid)
        create_time = process.create_time()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
        return GpuProcessIdentity(pid, None, None)
    if create_time <= 0:
        return GpuProcessIdentity(pid, None, None)
    try:
        executable = process.exe()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
        return GpuProcessIdentity(pid, create_time, None)
    executable_id = _file_identifier(executable) if executable else None
    return GpuProcessIdentity(pid, create_time, executable_id)


def _run_monitoring_query(arguments: list[str]) -> str:
    """Run one bounded read-only nvidia-smi query without a shell."""
    try:
        result = subprocess.run(
            arguments,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise HardwareError("nvidia-smi disappeared during calibration") from error
    except subprocess.TimeoutExpired as error:
        raise HardwareError("nvidia-smi timed out during calibration") from error
    except subprocess.CalledProcessError as error:
        message = f"nvidia-smi exited with code {error.returncode} during calibration"
        raise HardwareError(message) from error
    return result.stdout


def _gpu_query(index: int, fields: str) -> list[str]:
    """Read exactly one selected-GPU CSV row for the requested fields."""
    output = _run_monitoring_query(
        [
            "nvidia-smi",
            "--id",
            str(index),
            f"--query-gpu={fields}",
            "--format=csv,noheader,nounits",
        ]
    )
    rows = [row for row in csv.reader(StringIO(output)) if any(field.strip() for field in row)]
    if len(rows) != 1:
        raise HardwareError("nvidia-smi returned malformed calibration GPU data")
    return [field.strip() for field in rows[0]]


def _optional_float(value: str) -> float | None:
    """Parse one optional finite telemetry scalar without making it decision-critical."""
    if value.casefold() in _UNAVAILABLE:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _throttle_reasons(value: str) -> tuple[str, ...] | None:
    """Normalize driver-declared throttle flags while preserving unsupported evidence as null."""
    folded = value.casefold()
    if folded in _UNAVAILABLE:
        return None
    if folded in {"not active", "none"}:
        return ()
    return tuple(part.strip() for part in value.split("|") if part.strip())


def _telemetry(values: list[str]) -> GpuTelemetry | None:
    """Decode optional fields from a full row or return null after the compatibility fallback."""
    if len(values) < 9:
        return None
    return GpuTelemetry(
        _optional_float(values[4]),
        _optional_float(values[5]),
        _optional_float(values[6]),
        _optional_float(values[7]),
        _throttle_reasons(",".join(values[8:])),
    )


def _gpu_memory(index: int) -> tuple[float, float, str, bool, GpuTelemetry | None]:
    """Read mandatory memory and best-effort telemetry in one query when supported."""
    try:
        values = _gpu_query(index, f"{_BASE_FIELDS},{_TELEMETRY_FIELDS}")
    except HardwareError:
        values = _gpu_query(index, _BASE_FIELDS)
    if len(values) < 4:
        raise HardwareError("nvidia-smi returned malformed calibration memory data")
    try:
        total_mib, free_mib = float(values[0]), float(values[1])
    except ValueError as error:
        raise HardwareError("nvidia-smi returned non-numeric calibration memory data") from error
    driver, driver_model = values[2], values[3]
    if total_mib <= 0 or not 0 <= free_mib <= total_mib or not driver or not driver_model:
        raise HardwareError("nvidia-smi returned invalid calibration memory values")
    return (
        mib_to_gib(total_mib),
        mib_to_gib(free_mib),
        driver,
        driver_model.casefold() == "wddm",
        _telemetry(values),
    )


def _compute_pids(index: int) -> tuple[int, ...]:
    """Read compute PIDs so foreign GPU workloads invalidate calibration evidence."""
    output = _run_monitoring_query(
        [
            "nvidia-smi",
            "--id",
            str(index),
            "--query-compute-apps=pid",
            "--format=csv,noheader,nounits",
        ]
    )
    values = [line.strip() for line in output.splitlines() if line.strip()]
    try:
        pids = tuple(sorted({int(value) for value in values}))
    except ValueError as error:
        raise HardwareError("nvidia-smi returned malformed compute-process data") from error
    if any(pid < 1 for pid in pids):
        raise HardwareError("nvidia-smi returned an invalid compute PID")
    return pids


def query_gpu_snapshot(index: int) -> GpuSnapshot:
    """Capture selected-GPU memory, driver model, contexts, and evidence-only telemetry."""
    total_gib, free_gib, driver, is_wddm, telemetry = _gpu_memory(index)
    pids = _compute_pids(index)
    contexts = tuple(identify_gpu_process(pid) for pid in pids)
    return GpuSnapshot(total_gib, free_gib, driver, pids, is_wddm, telemetry, contexts)
