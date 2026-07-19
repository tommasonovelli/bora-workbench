"""Read aggregate NVIDIA memory, optional telemetry, and process contexts for calibration."""

from __future__ import annotations

import csv
import subprocess
from dataclasses import dataclass
from io import StringIO

from qwen_launcher._gpu_process_identity import GpuProcessIdentity, identify_gpu_processes
from qwen_launcher.hardware import HardwareError, mib_to_gib

_TIMEOUT_SECONDS = 5
_BASE_FIELDS = "memory.total,memory.free,driver_version,driver_model.current"
_TELEMETRY_FIELDS = (
    "utilization.gpu,temperature.gpu,clocks.current.sm,power.draw,clocks_event_reasons.active"
)
_UNAVAILABLE = {"", "n/a", "[n/a]", "not supported", "[not supported]"}


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


def _run(arguments: list[str]) -> str:
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
    output = _run(
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


def _memory(index: int) -> tuple[float, float, str, bool, GpuTelemetry | None]:
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
    output = _run(
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
    total_gib, free_gib, driver, is_wddm, telemetry = _memory(index)
    pids = _compute_pids(index)
    contexts = identify_gpu_processes(pids)
    return GpuSnapshot(total_gib, free_gib, driver, pids, is_wddm, telemetry, contexts)
