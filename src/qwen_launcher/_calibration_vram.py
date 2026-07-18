"""Sample aggregate VRAM and verify tolerant, stabilized release after each trial."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from qwen_launcher._hardware_monitoring import GpuSnapshot, query_gpu_snapshot

GPU_POLL_INTERVAL_MS = 250
GPU_RELEASE_STABILIZATION_MS = 10_000
_POLL_INTERVAL_SECONDS = GPU_POLL_INTERVAL_MS / 1000
_RELEASE_STABILIZATION_SECONDS = GPU_RELEASE_STABILIZATION_MS / 1000


@dataclass(frozen=True, slots=True)
class VramThresholds:
    """Hold explicit CUDA reserve and post-stop release tolerance values."""

    minimum_free_gib: float
    release_tolerance_gib: float


@dataclass(frozen=True, slots=True)
class VramSummary:
    """Hold aggregate baseline, peak, reserve, release, and driver evidence."""

    baseline_used_gib: float
    peak_used_gib: float
    minimum_free_gib: float
    release_used_gib: float
    driver_version: str


class VramError(RuntimeError):
    """Report invalid VRAM evidence while retaining measurable discarded-run values."""

    def __init__(self, message: str, summary: VramSummary | None = None) -> None:
        """Attach an optional measured summary to an invalid-run diagnosis."""
        super().__init__(message)
        self.summary = summary


class VramEnvironmentError(VramError):
    """Mark evidence invalidated by the environment rather than by the candidate.

    Specification section 5.6 separates candidate-level failures (reserve or release violations,
    which discard one candidate) from run-level failures (concurrent compute workloads, monitor
    faults, or changed capacity, which invalidate the whole run). calibration/v1 treats both as one
    ``VramError``; calibration/v2 needs the distinction, so the subclass keeps v1 behavior intact.
    """


@dataclass(slots=True)
class VramMonitor:
    """Collect fixed-interval selected-GPU snapshots around one fresh server process."""

    gpu_index: int
    thresholds: VramThresholds
    query: Callable[[int], GpuSnapshot] = query_gpu_snapshot
    _baseline: GpuSnapshot | None = field(default=None, init=False)
    _samples: list[GpuSnapshot] = field(default_factory=list, init=False)
    _error: Exception | None = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def _query_snapshot(self) -> GpuSnapshot:
        """Read one snapshot or classify the monitor failure as run-invalidating."""
        try:
            return self.query(self.gpu_index)
        except VramEnvironmentError:
            raise
        except Exception as error:
            raise VramEnvironmentError(f"GPU monitoring failed: {error}") from error

    def start(self) -> None:
        """Capture an uncontaminated baseline and begin 250 ms aggregate polling."""
        baseline = self._query_snapshot()
        if baseline.compute_pids:
            raise VramEnvironmentError(
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
                self._samples.append(self._query_snapshot())
            except Exception as error:  # The owning thread re-raises with calibration context.
                self._error = error
                return
            self._stop_event.wait(max(0.0, deadline - time.monotonic()))

    def finish(self, managed_pid: int | None) -> VramSummary:
        """Wait up to ten seconds for post-stop memory to return within tolerance."""
        self._stop_polling()
        baseline = self._require_baseline()
        release = self._wait_for_release(baseline)
        summary = self._summary(baseline, release)
        try:
            self._validate_samples(managed_pid, baseline, release)
        except VramError as error:
            # Re-raise the same class so environment failures stay run-invalidating for v2.
            raise type(error)(str(error), summary) from error
        return summary

    def _stop_polling(self) -> None:
        """Join the polling thread and surface its first query failure."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        if self._error is not None:
            if isinstance(self._error, VramEnvironmentError):
                raise self._error
            raise VramEnvironmentError(f"GPU monitoring failed: {self._error}") from self._error

    def _wait_for_release(self, baseline: GpuSnapshot) -> GpuSnapshot:
        """Sample release on the protocol schedule until tolerance or deadline is reached."""
        baseline_used = self._used_gib(baseline)
        limit = baseline_used + self.thresholds.release_tolerance_gib
        deadline = time.monotonic() + _RELEASE_STABILIZATION_SECONDS
        while True:
            release = self._query_snapshot()
            self._samples.append(release)
            if release.compute_pids or release.vram_total_gib != baseline.vram_total_gib:
                return release
            if self._used_gib(release) <= limit:
                return release
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return release
            time.sleep(min(_POLL_INTERVAL_SECONDS, remaining))

    def _summary(self, baseline: GpuSnapshot, release: GpuSnapshot) -> VramSummary:
        """Aggregate every workload and release sample into reproducible evidence."""
        minimum_free = min(sample.vram_free_gib for sample in self._samples)
        peak_used = max(self._used_gib(sample) for sample in self._samples)
        return VramSummary(
            self._used_gib(baseline),
            peak_used,
            minimum_free,
            self._used_gib(release),
            baseline.driver_version,
        )

    def _require_baseline(self) -> GpuSnapshot:
        """Return the mandatory baseline or diagnose invalid monitor use."""
        if self._baseline is None:
            raise VramError("VRAM monitor was not started")
        return self._baseline

    @staticmethod
    def _used_gib(snapshot: GpuSnapshot) -> float:
        """Return aggregate used memory from one total/free GPU snapshot."""
        return snapshot.vram_total_gib - snapshot.vram_free_gib

    def _validate_samples(
        self, managed_pid: int | None, baseline: GpuSnapshot, release: GpuSnapshot
    ) -> None:
        """Reject foreign processes, reserve or capacity violations, and retained VRAM."""
        allowed = set() if managed_pid is None else {managed_pid}
        foreign = set().union(*(set(sample.compute_pids) for sample in self._samples)) - allowed
        if foreign or release.compute_pids:
            raise VramEnvironmentError(
                "concurrent GPU compute workload contaminated calibration; stop it"
            )
        if any(sample.vram_total_gib != baseline.vram_total_gib for sample in self._samples):
            raise VramEnvironmentError("reported total VRAM changed during calibration")
        if any(sample.driver_version != baseline.driver_version for sample in self._samples):
            raise VramEnvironmentError("GPU driver version changed during calibration")
        if any(sample.vram_free_gib < self.thresholds.minimum_free_gib for sample in self._samples):
            raise VramError("minimum free VRAM reserve was violated")
        release_limit = self._used_gib(baseline) + self.thresholds.release_tolerance_gib
        if self._used_gib(release) > release_limit:
            raise VramError("GPU memory did not stabilize within release tolerance after stop")
