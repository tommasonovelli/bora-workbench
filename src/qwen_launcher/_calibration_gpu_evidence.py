"""Aggregate evidence-only GPU telemetry without introducing decision thresholds."""

from __future__ import annotations

from dataclasses import dataclass

from qwen_launcher._hardware_monitoring import GpuSnapshot


@dataclass(frozen=True, slots=True)
class GpuTelemetrySummary:
    """Hold optional extrema and driver-declared throttle reasons for one trial."""

    maximum_utilization_percent: float | None
    minimum_sm_clock_mhz: float | None
    maximum_temperature_celsius: float | None
    maximum_power_draw_watts: float | None
    throttle_reasons: tuple[str, ...] | None


def _maximum(values: list[float]) -> float | None:
    """Return an optional maximum without inventing a value for unavailable telemetry."""
    return max(values) if values else None


def _minimum(values: list[float]) -> float | None:
    """Return an optional minimum without inventing a value for unavailable telemetry."""
    return min(values) if values else None


def summarize_telemetry(samples: list[GpuSnapshot]) -> GpuTelemetrySummary | None:
    """Aggregate supported fields while keeping unsupported driver evidence nullable."""
    telemetry = [sample.telemetry for sample in samples if sample.telemetry is not None]
    if not telemetry:
        return None
    utilization = [
        item.utilization_percent for item in telemetry if item.utilization_percent is not None
    ]
    clocks = [item.sm_clock_mhz for item in telemetry if item.sm_clock_mhz is not None]
    temperatures = [
        item.temperature_celsius for item in telemetry if item.temperature_celsius is not None
    ]
    powers = [item.power_draw_watts for item in telemetry if item.power_draw_watts is not None]
    reasons = sorted(
        {
            reason
            for item in telemetry
            if item.throttle_reasons is not None
            for reason in item.throttle_reasons
        }
    )
    has_reasons = any(item.throttle_reasons is not None for item in telemetry)
    return GpuTelemetrySummary(
        _maximum(utilization),
        _minimum(clocks),
        _maximum(temperatures),
        _maximum(powers),
        tuple(reasons) if has_reasons else None,
    )
