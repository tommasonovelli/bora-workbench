"""Own the monitor and process lifecycle of one calibration trial (spec 5.6).

The trial runner keeps the workload and its classification; this module keeps the parts that must
run even when the workload failed, so cleanup precedence stays in one place (D-058). Monitors use
the calibration reserves (0.5/2.0/0.125 GiB) and the run-scoped GPU context population of D-046.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import psutil

from bora_workbench._calibration_memory import (
    GpuContextBaseline,
    RamMonitor,
    RamSummary,
    VramMonitor,
    VramSummary,
    VramThresholds,
)
from bora_workbench._calibration_trial_control import prefer_cleanup_error
from bora_workbench._calibration_types import (
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
)
from bora_workbench.calibration import CalibrationRunError
from bora_workbench.hardware import GpuProcessIdentity
from bora_workbench.process import RunningService, stop_services


@dataclass(slots=True)
class SpawnRecord:
    """Capture child identity before health readiness can fail."""

    pid: int | None = None
    create_time: float | None = None

    def __call__(self, pid: int) -> None:
        """Record the spawned pid/create-time pair without failing process cleanup."""
        self.pid = pid
        try:
            self.create_time = psutil.Process(pid).create_time()
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            self.create_time = None


def managed_gpu_identity(
    running: RunningService | None, spawned: SpawnRecord
) -> GpuProcessIdentity | None:
    """Return the exact managed process instance even after normal cleanup."""
    if running is not None:
        service = running.state
        return GpuProcessIdentity(service.pid, service.create_time, None)
    if spawned.pid is None:
        return None
    return GpuProcessIdentity(spawned.pid, spawned.create_time, None)


@dataclass(frozen=True, slots=True)
class SessionResources:
    """Group finalized monitor summaries with the highest-precedence cleanup failure."""

    vram: VramSummary | None
    ram: RamSummary | None
    error: BaseException | None


@dataclass(slots=True)
class TrialSession:
    """Track both memory monitors and the process identity of one running trial."""

    vram: VramMonitor | None
    ram: RamMonitor
    spawned: SpawnRecord = field(default_factory=SpawnRecord)
    running: RunningService | None = None

    def start(self) -> None:
        """Begin fixed-interval polling before the server is spawned."""
        if self.vram is not None:
            self.vram.start()
        self.ram.start()

    def _finish_vram(
        self, error: BaseException | None
    ) -> tuple[VramSummary | None, BaseException | None]:
        """Finalize the VRAM monitor, keeping its reserve evidence ahead of the current failure."""
        if self.vram is None:
            return None, error
        try:
            return self.vram.finish(managed_gpu_identity(self.running, self.spawned)), error
        except BaseException as caught:
            return None, prefer_cleanup_error(error, caught)

    def finish(self, root: Path) -> SessionResources:
        """Stop the server and finalize both monitors, preferring run-invalidating evidence."""
        error: BaseException | None = None
        if self.running is not None:
            try:
                stop_services(root)
            except BaseException as caught:
                error = prefer_cleanup_error(error, caught)
        vram, error = self._finish_vram(error)
        ram: RamSummary | None = None
        try:
            ram = self.ram.finish()
        except BaseException as caught:
            error = prefer_cleanup_error(error, caught)
        return SessionResources(vram, ram, error)


def create_session(
    gpu_index: int | None, context_baseline: GpuContextBaseline | None
) -> TrialSession:
    """Create the reserve monitors bound to the immutable run-scoped context population.

    A CUDA trial without that population would fall back to the per-trial legacy contract and could
    attribute another process's memory to this candidate, so it is refused (D-046).
    """
    ram = RamMonitor(minimum_free_gib=RAM_RESERVE_GIB)
    if gpu_index is None:
        return TrialSession(None, ram)
    if context_baseline is None:
        raise CalibrationRunError("CUDA calibration requires a measured GPU context baseline")
    thresholds = VramThresholds(VRAM_RESERVE_GIB, RELEASE_TOLERANCE_GIB)
    return TrialSession(VramMonitor(gpu_index, thresholds, context_baseline=context_baseline), ram)
