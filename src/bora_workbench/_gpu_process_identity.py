"""Resolve opaque GPU process identities without retaining executable paths."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import psutil

GPU_CONTEXT_IDENTITY_MODEL = "executable-file-id/v1"


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


def identify_gpu_processes(pids: tuple[int, ...]) -> tuple[GpuProcessIdentity, ...]:
    """Resolve a complete, order-preserving identity tuple for one NVIDIA PID snapshot."""
    return tuple(identify_gpu_process(pid) for pid in pids)
