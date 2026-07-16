"""Read calibration-only aggregate NVIDIA memory and compute-process evidence."""

from __future__ import annotations

import csv
import subprocess
from dataclasses import dataclass
from io import StringIO

from qwen_launcher.hardware import HardwareError, mib_to_gib

_TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class GpuSnapshot:
    """Record total/free VRAM, driver, and compute PIDs at one polling instant."""

    vram_total_gib: float
    vram_free_gib: float
    driver_version: str
    compute_pids: tuple[int, ...]


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


def _memory(index: int) -> tuple[float, float, str]:
    """Read selected-GPU aggregate memory and driver version in one query."""
    output = _run(
        [
            "nvidia-smi",
            "--id",
            str(index),
            "--query-gpu=memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    rows = [row for row in csv.reader(StringIO(output)) if any(field.strip() for field in row)]
    if len(rows) != 1 or len(rows[0]) != 3:
        raise HardwareError("nvidia-smi returned malformed calibration memory data")
    try:
        total_mib = float(rows[0][0].strip())
        free_mib = float(rows[0][1].strip())
        driver = rows[0][2].strip()
    except ValueError as error:
        raise HardwareError("nvidia-smi returned non-numeric calibration memory data") from error
    if total_mib <= 0 or not 0 <= free_mib <= total_mib or not driver:
        raise HardwareError("nvidia-smi returned invalid calibration memory values")
    return mib_to_gib(total_mib), mib_to_gib(free_mib), driver


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
    """Capture aggregate selected-GPU memory and concurrent compute-process evidence."""
    total_gib, free_gib, driver = _memory(index)
    return GpuSnapshot(total_gib, free_gib, driver, _compute_pids(index))
