"""Measure the memory one calibration trial needs and diagnose what refused it (spec 5.6).

The module owns every memory observation of one trial: the aggregate VRAM monitor with the
run-scoped WDDM compute-context population of D-046, the available-RAM monitor that CPU and CUDA
alike must run (D-038/D-042), and the log-based out-of-memory diagnosis. Both monitors sample on
the same 250 ms protocol interval, so their two evidence streams stay comparable, and both receive
their reserves from the caller instead of reading a constant, so a record can be re-evaluated
later against exactly the margins it was measured with.

An exhausted GPU allocation is invisible to the VRAM monitor: the driver rejects the allocation,
so free VRAM never falls below the monitored reserve and the engine simply exits during model
load. The process log is therefore the only evidence available for the VRAM side, while the RAM
side stays class-based through ``RamReserveError`` (D-059).
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

import psutil

from bora_workbench._calibration_gpu_evidence import GpuTelemetrySummary, summarize_telemetry
from bora_workbench.hardware import (
    GpuProcessIdentity,
    GpuSnapshot,
    bytes_to_gib,
    query_gpu_snapshot,
)

# Both monitors poll on the protocol's 250 ms interval, and a stopped CUDA process gets 10 s to
# return its memory before retained memory is diagnosed as a release failure.
_POLL_INTERVAL_SECONDS = 0.25
_RELEASE_STABILIZATION_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class VramThresholds:
    """Hold explicit CUDA reserve and post-stop release tolerance values."""

    minimum_free_gib: float
    release_tolerance_gib: float


@dataclass(frozen=True, slots=True)
class VramSummary:
    """Hold aggregate VRAM, release duration, WDDM contexts, and optional telemetry."""

    baseline_used_gib: float
    peak_used_gib: float
    minimum_free_gib: float
    release_used_gib: float
    driver_version: str
    release_duration_seconds: float = 0.0
    initial_compute_context_count: int = 0
    telemetry: GpuTelemetrySummary | None = None
    context_replacement_count: int = 0


class VramError(RuntimeError):
    """Report invalid VRAM evidence while retaining measurable discarded-run values."""

    def __init__(self, message: str, summary: VramSummary | None = None) -> None:
        """Attach an optional measured summary to an invalid-run diagnosis."""
        super().__init__(message)
        self.summary = summary


class VramReserveError(VramError):
    """Report a minimum-free reserve violation for one infeasible candidate."""


class VramReleaseError(VramError):
    """Report retained memory after stop without implying a monotone boundary."""


class VramEnvironmentError(VramError):
    """Mark monitor or environmental evidence that invalidates the whole run.

    Specification section 5.6 separates reserve/release candidate failures from concurrent compute,
    monitor, driver, and capacity failures; this subclass is what carries that distinction to the
    caller, which discards the whole run instead of only the current candidate.
    """


@dataclass(frozen=True, slots=True)
class GpuContextBaseline:
    """Hold the complete compute-process population captured once for one run."""

    is_wddm: bool
    contexts: tuple[GpuProcessIdentity, ...]


def _aligned_contexts(snapshot: GpuSnapshot) -> tuple[GpuProcessIdentity, ...]:
    """Return process identities aligned exactly with one NVIDIA PID snapshot."""
    contexts = snapshot.compute_contexts
    if contexts is None or len(contexts) != len(snapshot.compute_pids):
        raise VramEnvironmentError("GPU compute-process identity monitoring is unavailable")
    return contexts


def _require_complete(
    contexts: tuple[GpuProcessIdentity, ...],
) -> tuple[GpuProcessIdentity, ...]:
    """Reject every non-managed context whose executable identity is unavailable."""
    unknown = [item.pid for item in contexts if not item.is_complete]
    if unknown:
        pids = ", ".join(str(pid) for pid in unknown)
        raise VramEnvironmentError(f"cannot identify GPU compute context PIDs {pids}")
    return contexts


def capture_gpu_context_baseline(index: int) -> GpuContextBaseline:
    """Capture one immutable pre-run context baseline and reject unreadable identities early."""
    snapshot = query_gpu_snapshot(index)
    contexts = _require_complete(_aligned_contexts(snapshot))
    if contexts and not snapshot.is_wddm:
        pids = ", ".join(str(item.pid) for item in contexts)
        raise VramEnvironmentError(
            f"concurrent GPU compute workload detected before calibration (PIDs {pids}); stop it"
        )
    return GpuContextBaseline(snapshot.is_wddm, contexts)


def _visible_contexts(
    snapshot: GpuSnapshot, managed: GpuProcessIdentity | None
) -> tuple[GpuProcessIdentity, ...]:
    """Remove the exact managed instance before requiring complete foreign identities."""
    contexts = _aligned_contexts(snapshot)
    if managed is not None and managed.create_time is not None:
        contexts = tuple(item for item in contexts if item.instance != managed.instance)
    return _require_complete(contexts)


def _identity_counts(contexts: tuple[GpuProcessIdentity, ...]) -> Counter[str]:
    """Count complete executable identities without serializing their opaque values."""
    return Counter(item.executable_id for item in contexts if item.executable_id is not None)


def _reject_excess(current: tuple[GpuProcessIdentity, ...], baseline: GpuContextBaseline) -> None:
    """Reject new executable files or multiplicity above the immutable run baseline."""
    allowed = _identity_counts(baseline.contexts)
    observed = _identity_counts(current)
    excess = observed - allowed
    if not excess:
        return
    pids = [item.pid for item in current if item.executable_id in excess]
    values = ", ".join(str(pid) for pid in sorted(pids))
    raise VramEnvironmentError(
        f"concurrent GPU compute workload contaminated calibration (PIDs {values}); stop it"
    )


def validate_gpu_contexts(
    snapshot: GpuSnapshot,
    baseline: GpuContextBaseline,
    managed: GpuProcessIdentity | None,
) -> set[tuple[int, float | None]]:
    """Validate one sample and return admitted baseline-executable replacement instances."""
    if snapshot.is_wddm != baseline.is_wddm:
        raise VramEnvironmentError("GPU driver model changed during calibration")
    current = _visible_contexts(snapshot, managed)
    if current and not baseline.is_wddm:
        pids = ", ".join(str(item.pid) for item in current)
        raise VramEnvironmentError(
            f"concurrent GPU compute workload contaminated calibration (PIDs {pids}); stop it"
        )
    _reject_excess(current, baseline)
    original = {item.instance for item in baseline.contexts}
    return {item.instance for item in current if item.instance not in original}


def count_context_replacements(
    snapshots: list[GpuSnapshot],
    baseline: GpuContextBaseline,
    managed: GpuProcessIdentity | None,
) -> int:
    """Validate every trial sample and count unique admitted process replacements."""
    replacements: set[tuple[int, float | None]] = set()
    for snapshot in snapshots:
        replacements |= validate_gpu_contexts(snapshot, baseline, managed)
    return len(replacements)


@dataclass(slots=True)
class VramMonitor:
    """Collect fixed-interval selected-GPU snapshots around one fresh server process."""

    gpu_index: int
    thresholds: VramThresholds
    context_baseline: GpuContextBaseline
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
        """Capture an eligible baseline and begin 250 ms aggregate polling."""
        baseline = self._query_snapshot()
        validate_gpu_contexts(baseline, self.context_baseline, None)
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

    def finish(self, managed: GpuProcessIdentity | None) -> VramSummary:
        """Wait for release and validate resources plus the run-scoped context population."""
        self._stop_polling()
        if self._baseline is None:
            raise VramError("VRAM monitor was not started")
        baseline = self._baseline
        release, release_duration = self._wait_for_release(baseline, managed)
        summary = self._summary(baseline, release, release_duration)
        try:
            replacements = self._validate_samples(managed, baseline, release)
        except VramError as error:
            # Preserve the class so environment failures stay run-invalidating.
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
        self, snapshot: GpuSnapshot, managed: GpuProcessIdentity | None
    ) -> bool:
        """Detect a context violation early so release sampling stops instead of waiting it out."""
        try:
            validate_gpu_contexts(snapshot, self.context_baseline, managed)
        except VramEnvironmentError:
            return True
        return False

    def _wait_for_release(
        self, baseline: GpuSnapshot, managed: GpuProcessIdentity | None
    ) -> tuple[GpuSnapshot, float]:
        """Sample release until tolerance or deadline and measure stabilization duration."""
        limit = self._used_gib(baseline) + self.thresholds.release_tolerance_gib
        started = time.monotonic()
        deadline = started + _RELEASE_STABILIZATION_SECONDS
        while True:
            release = self._query_snapshot()
            self._samples.append(release)
            has_changed_context = self._has_context_change(release, managed)
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

    @staticmethod
    def _used_gib(snapshot: GpuSnapshot) -> float:
        """Return aggregate used memory from one total/free GPU snapshot."""
        return snapshot.vram_total_gib - snapshot.vram_free_gib

    def _validate_samples(
        self, managed: GpuProcessIdentity | None, baseline: GpuSnapshot, release: GpuSnapshot
    ) -> int:
        """Reject context, reserve, capacity, driver, and retained-memory violations."""
        replacements = count_context_replacements(self._samples, self.context_baseline, managed)
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


class RamError(RuntimeError):
    """Report RAM evidence that cannot be trusted, invalidating the current run."""


class RamReserveError(RuntimeError):
    """Report a measured reserve violation that makes only the current trial infeasible."""

    def __init__(self, summary: RamSummary) -> None:
        """Retain the measured summary for candidate evidence and diagnostics."""
        super().__init__("minimum available RAM reserve was violated")
        self.summary = summary


@dataclass(frozen=True, slots=True)
class RamSummary:
    """Hold the pre-trial baseline and the minimum available RAM observed during a trial."""

    baseline_available_gib: float
    minimum_available_gib: float

    @property
    def needed_gib(self) -> float:
        """Return the measured RAM consumption used by the record headroom check (spec 5.5)."""
        return max(0.0, self.baseline_available_gib - self.minimum_available_gib)


def query_ram_available_gib() -> float:
    """Read currently available RAM in exact GiB via the section 5.4 conversion."""
    return bytes_to_gib(psutil.virtual_memory().available)


@dataclass(slots=True)
class RamMonitor:
    """Collect fixed-interval available-RAM samples around one fresh server process."""

    minimum_free_gib: float
    query: Callable[[], float] = query_ram_available_gib
    _baseline_gib: float | None = field(default=None, init=False)
    _samples: list[float] = field(default_factory=list, init=False)
    _error: Exception | None = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def _sample(self) -> float:
        """Read one finite non-negative sample or invalidate unreliable monitoring."""
        try:
            available_gib = self.query()
        except RamError:
            raise
        except Exception as error:
            raise RamError(f"RAM monitoring failed: {error}") from error
        if not math.isfinite(available_gib) or available_gib < 0:
            raise RamError("RAM monitoring returned an invalid available-memory value")
        return available_gib

    def start(self) -> None:
        """Capture the pre-trial baseline and begin 250 ms polling."""
        baseline = self._sample()
        self._baseline_gib = baseline
        self._samples.append(baseline)
        self._thread = threading.Thread(target=self._poll, name="qwen-calibration-ram", daemon=True)
        self._thread.start()

    def _poll(self) -> None:
        """Poll on a monotonic schedule and retain the first operational query error."""
        deadline = time.monotonic()
        while not self._stop_event.is_set():
            deadline += _POLL_INTERVAL_SECONDS
            try:
                self._samples.append(self._sample())
            except Exception as error:  # The owning thread re-raises with calibration context.
                self._error = error
                return
            self._stop_event.wait(max(0.0, deadline - time.monotonic()))

    def finish(self) -> RamSummary:
        """Stop polling and aggregate the observed minimum into reproducible evidence."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        if self._error is not None:
            if isinstance(self._error, RamError):
                raise self._error
            raise RamError(f"RAM monitoring failed: {self._error}") from self._error
        if self._baseline_gib is None:
            raise RamError("RAM monitor was not started")
        summary = RamSummary(self._baseline_gib, min(self._samples))
        if summary.minimum_available_gib < self.minimum_free_gib:
            raise RamReserveError(summary)
        return summary


# "oom" must match as a whole word: a bare substring test would classify unrelated log text
# such as "zoom" as an out-of-memory failure.
_OOM_PATTERN = re.compile(r"\boom\b|out of memory")

# The engine names the refusing device on the failing line itself, so the marker is searched per
# line: a CUDA banner elsewhere in the log must not turn a host allocation failure into a GPU one.
_DEVICE_PATTERN = re.compile(r"cuda|cublas|vram|gpu|device")


def read_logs(paths: tuple[Path, ...]) -> str:
    """Concatenate the readable process logs, skipping the ones this run cannot open."""
    parts: list[str] = []
    for path in paths:
        try:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(parts)


def oom_resource(text: str) -> Literal["ram", "vram"] | None:
    """Return the memory resource named by out-of-memory evidence, or None when there is none."""
    failing = [line for line in text.casefold().splitlines() if _OOM_PATTERN.search(line)]
    if not failing:
        return None
    return "vram" if any(_DEVICE_PATTERN.search(line) for line in failing) else "ram"
