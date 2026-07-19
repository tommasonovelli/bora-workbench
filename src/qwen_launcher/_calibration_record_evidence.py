"""Serialize calibration/v3 per-process resource and benchmark evidence for local records."""

from __future__ import annotations

from statistics import median

from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_v3_types import FinalistEvidence, TrialEvidence
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult

JsonObject = dict[str, object]


def benchmark_entry(benchmark: BenchmarkResult) -> JsonObject:
    """Serialize one unchanged benchmark/v1 session and its exact summary."""
    rates = benchmark.tok_s
    return {
        "warmup_tok_s": benchmark.warmup_tok_s,
        "measured_tok_s": list(benchmark.measured_tok_s),
        "tok_s": {"min": rates.minimum, "median": rates.median, "max": rates.maximum},
    }


def ram_entry(summary: RamSummary | None) -> JsonObject | None:
    """Serialize one available-RAM stream without inventing missing evidence."""
    if summary is None:
        return None
    return {
        "baseline_available_gib": summary.baseline_available_gib,
        "minimum_available_gib": summary.minimum_available_gib,
    }


def _telemetry_entry(summary: VramSummary) -> JsonObject | None:
    """Serialize evidence-only telemetry extrema when supported by the driver."""
    telemetry = summary.telemetry
    if telemetry is None:
        return None
    return {
        "maximum_utilization_percent": telemetry.maximum_utilization_percent,
        "minimum_sm_clock_mhz": telemetry.minimum_sm_clock_mhz,
        "maximum_temperature_celsius": telemetry.maximum_temperature_celsius,
        "maximum_power_draw_watts": telemetry.maximum_power_draw_watts,
        "throttle_reasons": (
            None if telemetry.throttle_reasons is None else list(telemetry.throttle_reasons)
        ),
    }


def vram_entry(summary: VramSummary | None) -> JsonObject | None:
    """Serialize aggregate VRAM, release duration, contexts, and optional telemetry."""
    if summary is None:
        return None
    return {
        "baseline_used_gib": summary.baseline_used_gib,
        "peak_used_gib": summary.peak_used_gib,
        "minimum_free_gib": summary.minimum_free_gib,
        "release_used_gib": summary.release_used_gib,
        "release_duration_seconds": summary.release_duration_seconds,
        "driver_version": summary.driver_version,
        "initial_compute_context_count": summary.initial_compute_context_count,
        "context_replacement_count": summary.context_replacement_count,
        "telemetry": _telemetry_entry(summary),
    }


def probe_trial_entry(trial: TrialEvidence) -> JsonObject:
    """Serialize reduced process evidence for one screening probe."""
    return {
        "sequence": trial.order.sequence,
        "started_at": trial.started_at,
        "finished_at": trial.finished_at,
        "log_path": trial.log_path,
        "ram": ram_entry(trial.ram),
        "vram": vram_entry(trial.vram),
    }


def confirmation_session_entry(trial: TrialEvidence) -> JsonObject:
    """Serialize one paired confirmation process including its full benchmark session."""
    return {
        "round": trial.order.round_index,
        "global_position": trial.order.global_position,
        "started_at": trial.started_at,
        "finished_at": trial.finished_at,
        "log_path": trial.log_path,
        "benchmark": None if trial.benchmark is None else benchmark_entry(trial.benchmark),
        "ram": ram_entry(trial.ram),
        "vram": vram_entry(trial.vram),
    }


def vram_needed(finalist: FinalistEvidence) -> float | None:
    """Return conservative incremental VRAM need from combined confirmation evidence."""
    if finalist.vram is None:
        return None
    return finalist.vram.peak_used_gib - finalist.vram.baseline_used_gib


def _round_medians(finalist: FinalistEvidence) -> list[float | None]:
    """Serialize each session median while preserving failed-session null evidence."""
    return [
        None if session.benchmark is None else session.benchmark.tok_s.median
        for session in finalist.sessions
    ]


def finalist_entry(finalist: FinalistEvidence, is_selected: bool) -> JsonObject:
    """Serialize one finalist with paired sessions and conservative aggregates."""
    ram, vram = finalist.ram, finalist.vram
    return {
        "ctx": finalist.ctx,
        "n_cpu_moe": finalist.n_cpu_moe,
        "outcome": finalist.outcome,
        "discard_reason": finalist.discard_reason,
        "sessions": [confirmation_session_entry(item) for item in finalist.sessions],
        "round_medians": _round_medians(finalist),
        "ram_needed_gib": None if ram is None else ram.needed_gib,
        "minimum_ram_available_gib": None if ram is None else ram.minimum_available_gib,
        "vram_needed_gib": vram_needed(finalist),
        "minimum_free_vram_gib": None if vram is None else vram.minimum_free_gib,
        "is_selected": is_selected,
    }


def selected_benchmark_entry(finalist: FinalistEvidence) -> JsonObject:
    """Combine the selected finalist's two benchmark sessions without losing either one."""
    benchmarks = [session.benchmark for session in finalist.sessions]
    if any(item is None for item in benchmarks):
        raise ValueError("selected finalist requires a benchmark in every confirmation round")
    complete = [item for item in benchmarks if item is not None]
    measured = [value for item in complete for value in item.measured_tok_s]
    return {
        "warmup_tok_s": [item.warmup_tok_s for item in complete],
        "measured_tok_s": measured,
        "round_medians": [item.tok_s.median for item in complete],
        "tok_s": {"min": min(measured), "median": median(measured), "max": max(measured)},
    }
