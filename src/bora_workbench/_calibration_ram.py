"""Sample available RAM around one calibration trial for every backend.

Calibration must observe and reserve available RAM during load, workload, and benchmark on CPU
and CUDA alike (D-038/D-042). The sampling interval is the same 250 ms
protocol interval used for VRAM, so the two evidence streams stay comparable.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import psutil

from bora_workbench._calibration_vram import GPU_POLL_INTERVAL_MS
from bora_workbench.hardware import bytes_to_gib

_POLL_INTERVAL_SECONDS = GPU_POLL_INTERVAL_MS / 1000


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

    query: Callable[[], float] = query_ram_available_gib
    minimum_free_gib: float | None = None
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
        if (
            self.minimum_free_gib is not None
            and summary.minimum_available_gib < self.minimum_free_gib
        ):
            raise RamReserveError(summary)
        return summary
