"""Define calibration VRAM thresholds, summaries, and failure categories."""

from __future__ import annotations

from dataclasses import dataclass

from qwen_launcher._calibration_gpu_evidence import GpuTelemetrySummary


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
    monitor, driver, and capacity failures. The subclass keeps calibration/v1 behavior compatible
    while letting calibration preserve that distinction.
    """
