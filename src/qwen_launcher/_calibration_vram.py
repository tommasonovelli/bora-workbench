"""Sample aggregate VRAM every 250 ms and reject contaminated calibration runs."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from qwen_launcher._hardware_monitoring import GpuSnapshot, query_gpu_snapshot

_POLL_INTERVAL_SECONDS = 0.250


@dataclass(frozen=True, slots=True)
class VramSummary:
    """Hold aggregate baseline, peak use, minimum free memory, and driver evidence."""

    baseline_used_gib: float
    peak_used_gib: float
    minimum_free_gib: float
    driver_version: str


class VramError(RuntimeError):
    """Report invalid VRAM evidence while retaining measurable discarded-run values."""

    def __init__(self, message: str, summary: VramSummary | None = None) -> None:
        """Attach an optional measured summary to an invalid-run diagnosis."""
        super().__init__(message)
        self.summary = summary


@dataclass(slots=True)
class VramMonitor:
    """Collect fixed-interval selected-GPU snapshots around one fresh server process."""

    gpu_index: int
    minimum_free_gib: float
    query: Callable[[int], GpuSnapshot] = query_gpu_snapshot
    _baseline: GpuSnapshot | None = field(default=None, init=False)
    _samples: list[GpuSnapshot] = field(default_factory=list, init=False)
    _error: Exception | None = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def start(self) -> None:
        """Capture an uncontaminated baseline and begin 250 ms aggregate polling."""
        baseline = self.query(self.gpu_index)
        if baseline.compute_pids:
            raise VramError(
                "concurrent GPU compute workload detected before calibration; stop it and retry"
            )
        self._baseline = baseline
        self._samples.append(baseline)
        self._thread = threading.Thread(
            target=self._poll, name="qwen-calibration-vram", daemon=True
        )
        self._thread.start()

    def _poll(self) -> None:
        """Poll on a monotonic schedule and retain the first operational query error."""
        deadline = time.monotonic()
        while not self._stop_event.is_set():
            deadline += _POLL_INTERVAL_SECONDS
            try:
                self._samples.append(self.query(self.gpu_index))
            except Exception as error:  # The owning thread re-raises with calibration context.
                self._error = error
                return
            self._stop_event.wait(max(0.0, deadline - time.monotonic()))

    def finish(self, managed_pid: int | None) -> VramSummary:
        """Stop polling after process cleanup and require full uncontaminated release."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        if self._error is not None:
            raise VramError(f"GPU monitoring failed: {self._error}") from self._error
        release = self.query(self.gpu_index)
        baseline = self._require_baseline()
        minimum_free = min(sample.vram_free_gib for sample in self._samples)
        peak_used = max(sample.vram_total_gib - sample.vram_free_gib for sample in self._samples)
        summary = VramSummary(
            baseline.vram_total_gib - baseline.vram_free_gib,
            peak_used,
            minimum_free,
            baseline.driver_version,
        )
        try:
            self._validate_samples(managed_pid, baseline, release)
        except VramError as error:
            raise VramError(str(error), summary) from error
        return summary

    def _require_baseline(self) -> GpuSnapshot:
        """Return the mandatory baseline or diagnose invalid monitor use."""
        if self._baseline is None:
            raise VramError("VRAM monitor was not started")
        return self._baseline

    def _validate_samples(
        self, managed_pid: int | None, baseline: GpuSnapshot, release: GpuSnapshot
    ) -> None:
        """Reject foreign processes, reserve violations, capacity drift, and retained VRAM."""
        allowed = set() if managed_pid is None else {managed_pid}
        foreign = set().union(*(set(sample.compute_pids) for sample in self._samples)) - allowed
        if foreign or release.compute_pids:
            raise VramError("concurrent GPU compute workload contaminated calibration; stop it")
        if any(sample.vram_total_gib != baseline.vram_total_gib for sample in self._samples):
            raise VramError("reported total VRAM changed during calibration")
        if any(sample.vram_free_gib < self.minimum_free_gib for sample in self._samples):
            raise VramError("minimum free VRAM reserve was violated")
        baseline_used = baseline.vram_total_gib - baseline.vram_free_gib
        release_used = release.vram_total_gib - release.vram_free_gib
        if release_used > baseline_used:
            raise VramError("GPU memory did not return to its pre-run baseline after stop")
