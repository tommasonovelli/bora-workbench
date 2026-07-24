"""Sample aggregate VRAM, WDDM context stability, and tolerant release after each trial."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from qwen_launcher._calibration_gpu_contexts import (
    GpuContextBaseline,
    count_context_replacements,
    legacy_foreign_pids,
    validate_gpu_contexts,
)
from qwen_launcher._calibration_gpu_evidence import summarize_telemetry
from qwen_launcher._calibration_vram_types import (
    VramEnvironmentError,
    VramError,
    VramReleaseError,
    VramReserveError,
    VramSummary,
    VramThresholds,
)
from qwen_launcher._gpu_process_identity import GpuProcessIdentity
from qwen_launcher._hardware_monitoring import GpuSnapshot, query_gpu_snapshot

GPU_POLL_INTERVAL_MS = 250
GPU_RELEASE_STABILIZATION_MS = 10_000
_POLL_INTERVAL_SECONDS = GPU_POLL_INTERVAL_MS / 1000
_RELEASE_STABILIZATION_SECONDS = GPU_RELEASE_STABILIZATION_MS / 1000
_ManagedGpu = GpuProcessIdentity | int | None


@dataclass(slots=True)
class VramMonitor:
    """Collect fixed-interval selected-GPU snapshots around one fresh server process."""

    gpu_index: int
    thresholds: VramThresholds
    query: Callable[[int], GpuSnapshot] = query_gpu_snapshot
    context_baseline: GpuContextBaseline | None = None
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
        """Capture an eligible baseline and begin 250 ms aggregate polling."""
        baseline = self._query_snapshot()
        if self.context_baseline is not None:
            validate_gpu_contexts(baseline, self.context_baseline, None)
        elif baseline.compute_pids and not baseline.is_wddm:
            pids = ", ".join(str(pid) for pid in baseline.compute_pids)
            raise VramEnvironmentError(
                f"concurrent GPU compute workload detected before calibration (PIDs {pids}); "
                "stop it and retry"
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

    def finish(self, managed: _ManagedGpu) -> VramSummary:
        """Wait for release and validate resources plus the run-scoped context population."""
        self._stop_polling()
        baseline = self._require_baseline()
        release, release_duration = self._wait_for_release(baseline, managed)
        summary = self._summary(baseline, release, release_duration)
        try:
            replacements = self._validate_samples(managed, baseline, release)
        except VramError as error:
            # Preserve the class so environment failures stay run-invalidating for v5.
            raise type(error)(str(error), summary) from error
        return replace(summary, context_replacement_count=replacements)

    def _stop_polling(self) -> None:
        """Join the polling thread and surface its first query failure."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        if self._error is not None:
            if isinstance(self._error, VramEnvironmentError):
                raise self._error
            raise VramEnvironmentError(f"GPU monitoring failed: {self._error}") from self._error

    def _has_context_change(
        self, snapshot: GpuSnapshot, baseline: GpuSnapshot, managed: _ManagedGpu
    ) -> bool:
        """Detect a context violation early while preserving v1's exact-PID behavior."""
        if self.context_baseline is None:
            return bool(legacy_foreign_pids([snapshot], baseline, managed))
        identity = managed if isinstance(managed, GpuProcessIdentity) else None
        try:
            validate_gpu_contexts(snapshot, self.context_baseline, identity)
        except VramEnvironmentError:
            return True
        return False

    def _wait_for_release(
        self, baseline: GpuSnapshot, managed: _ManagedGpu
    ) -> tuple[GpuSnapshot, float]:
        """Sample release until tolerance or deadline and measure stabilization duration."""
        limit = self._used_gib(baseline) + self.thresholds.release_tolerance_gib
        started = time.monotonic()
        deadline = started + _RELEASE_STABILIZATION_SECONDS
        while True:
            release = self._query_snapshot()
            self._samples.append(release)
            has_changed_context = self._has_context_change(release, baseline, managed)
            has_changed_capacity = release.vram_total_gib != baseline.vram_total_gib
            is_released = self._used_gib(release) <= limit
            remaining = deadline - time.monotonic()
            if has_changed_context or has_changed_capacity or is_released or remaining <= 0:
                return release, time.monotonic() - started
            time.sleep(min(_POLL_INTERVAL_SECONDS, remaining))

    def _summary(
        self, baseline: GpuSnapshot, release: GpuSnapshot, release_duration: float
    ) -> VramSummary:
        """Aggregate workload, release, WDDM-context, and optional telemetry evidence."""
        minimum_free = min(sample.vram_free_gib for sample in self._samples)
        peak_used = max(self._used_gib(sample) for sample in self._samples)
        return VramSummary(
            self._used_gib(baseline),
            peak_used,
            minimum_free,
            self._used_gib(release),
            baseline.driver_version,
            release_duration,
            len(baseline.compute_pids) if baseline.is_wddm else 0,
            summarize_telemetry(self._samples),
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

    def _validate_contexts(self, managed: _ManagedGpu, baseline: GpuSnapshot) -> int:
        """Validate exact v1 PIDs or immutable v5 executable multiplicity."""
        if self.context_baseline is None:
            foreign = legacy_foreign_pids(self._samples, baseline, managed)
            if foreign:
                pids = ", ".join(str(pid) for pid in sorted(foreign))
                message = f"concurrent GPU compute workload contaminated calibration (PIDs {pids})"
                raise VramEnvironmentError(f"{message}; stop it")
            return 0
        identity = managed if isinstance(managed, GpuProcessIdentity) else None
        return count_context_replacements(self._samples, self.context_baseline, identity)

    def _validate_samples(
        self, managed: _ManagedGpu, baseline: GpuSnapshot, release: GpuSnapshot
    ) -> int:
        """Reject context, reserve, capacity, driver, and retained-memory violations."""
        replacements = self._validate_contexts(managed, baseline)
        if any(sample.vram_total_gib != baseline.vram_total_gib for sample in self._samples):
            raise VramEnvironmentError("reported total VRAM changed during calibration")
        if any(sample.driver_version != baseline.driver_version for sample in self._samples):
            raise VramEnvironmentError("GPU driver version changed during calibration")
        if any(sample.is_wddm != baseline.is_wddm for sample in self._samples):
            raise VramEnvironmentError("GPU driver model changed during calibration")
        if any(sample.vram_free_gib < self.thresholds.minimum_free_gib for sample in self._samples):
            raise VramReserveError("minimum free VRAM reserve was violated")
        release_limit = self._used_gib(baseline) + self.thresholds.release_tolerance_gib
        if self._used_gib(release) > release_limit:
            raise VramReleaseError(
                "GPU memory did not stabilize within release tolerance after stop"
            )
        return replacements
