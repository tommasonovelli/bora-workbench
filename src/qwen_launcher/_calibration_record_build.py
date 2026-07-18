"""Serialize measured calibration/v2 evidence into calibration-record/v1 documents."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from qwen_launcher._calibration_metadata import launcher_version
from qwen_launcher._calibration_v2_types import (
    CALIBRATION_V2_PROTOCOL,
    CONTEXT_SCALE,
    MODE_PROBE_CAP,
    RELEASE_TOLERANCE_GIB,
    STABLE_START_RUNS,
    VRAM_RESERVE_GIB,
    FinalistEvidence,
    ModeCalibration,
)
from qwen_launcher.calibration import CalibrationTarget

JsonObject = dict[str, object]


def _hardware_identity(target: CalibrationTarget, gpu_driver: str | None) -> JsonObject:
    """Build the stable hardware identity fixed by design section 3, step 5."""
    hardware = target.hardware
    return {
        "cpu_name": hardware.cpu_name,
        "cpu_cores": hardware.cpu_cores,
        "ram_total_gib": hardware.ram_total_gib,
        "gpu_count": hardware.gpu_count,
        "gpu_name": hardware.gpu_name,
        "gpu_driver": gpu_driver,
        "vram_total_gib": hardware.vram_total_gib,
    }


def _vram_needed(finalist: FinalistEvidence) -> float | None:
    """Return the measured incremental VRAM need when CUDA evidence exists."""
    if finalist.vram is None:
        return None
    return finalist.vram.peak_used_gib - finalist.vram.baseline_used_gib


def _finalist_entry(finalist: FinalistEvidence, is_selected: bool) -> JsonObject:
    """Serialize one finalist with all fields reused by semantic reconstruction."""
    benchmark, vram, ram = finalist.benchmark, finalist.vram, finalist.ram
    return {
        "ctx": finalist.ctx,
        "n_cpu_moe": finalist.n_cpu_moe,
        "outcome": finalist.outcome,
        "discard_reason": finalist.discard_reason,
        "measured_tok_s": None if benchmark is None else list(benchmark.measured_tok_s),
        "ram_needed_gib": None if ram is None else ram.needed_gib,
        "minimum_ram_available_gib": None if ram is None else ram.minimum_available_gib,
        "vram_needed_gib": _vram_needed(finalist),
        "minimum_free_vram_gib": None if vram is None else vram.minimum_free_gib,
        "is_selected": is_selected,
    }


def _finalist_entries(calibration: ModeCalibration) -> list[JsonObject]:
    """Serialize every finalist in its deterministic confirmation order."""
    return [
        _finalist_entry(finalist, finalist is calibration.selected)
        for finalist in calibration.finalists
    ]


def _observed_entry(selected: FinalistEvidence) -> JsonObject:
    """Serialize selected resource minima used by the launch-time headroom check."""
    assert selected.ram is not None
    return {
        "ram_needed_gib": selected.ram.needed_gib,
        "minimum_ram_available_gib": selected.ram.minimum_available_gib,
        "vram_needed_gib": _vram_needed(selected),
        "minimum_vram_free_gib": None if selected.vram is None else selected.vram.minimum_free_gib,
    }


def _benchmark_entry(selected: FinalistEvidence) -> JsonObject:
    """Serialize the selected finalist's complete benchmark/v1 evidence."""
    assert selected.benchmark is not None
    benchmark = selected.benchmark
    rates = benchmark.tok_s
    return {
        "warmup_tok_s": benchmark.warmup_tok_s,
        "measured_tok_s": list(benchmark.measured_tok_s),
        "tok_s": {"min": rates.minimum, "median": rates.median, "max": rates.maximum},
    }


def _search_entry(calibration: ModeCalibration) -> JsonObject:
    """Serialize algorithm constants, screening probes, and finalist evidence."""
    return {
        "context_scale": list(CONTEXT_SCALE),
        "probe_cap": MODE_PROBE_CAP,
        "vram_reserve_gib": VRAM_RESERVE_GIB,
        "release_tolerance_gib": RELEASE_TOLERANCE_GIB,
        "stable_start_runs": STABLE_START_RUNS,
        "did_degrade": calibration.did_degrade,
        "probes": [
            {
                "ctx": probe.ctx,
                "n_cpu_moe": probe.n_cpu_moe,
                "is_feasible": probe.is_feasible,
                "reason": probe.reason,
                "peak_used_gib": probe.peak_used_gib,
            }
            for probe in calibration.probes
        ],
        "finalists": _finalist_entries(calibration),
    }


def build_record_document(target: CalibrationTarget, calibration: ModeCalibration) -> JsonObject:
    """Build one complete calibration-record/v1 document from measured evidence."""
    from qwen_launcher._calibration_record import command_contract_sha256

    selected = calibration.selected
    artifact = cast(JsonObject, target.lock["default_model_artifact"])
    gpu_driver = None if selected.vram is None else selected.vram.driver_version
    return {
        "schema": "calibration-record/v1",
        "mode": calibration.mode.id,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "launcher_version": launcher_version(),
        "calibration_protocol": CALIBRATION_V2_PROTOCOL,
        "benchmark_protocol": "benchmark/v1",
        "model": target.config.model,
        "model_sha256": artifact["sha256"],
        "engine_release": target.lock["release"],
        "engine_source_commit": target.lock["source_commit"],
        "command_contract_sha256": command_contract_sha256(target.lock),
        "os_name": target.hardware.os_name,
        "backend": target.hardware.backend,
        "hardware": _hardware_identity(target, gpu_driver),
        "envelope": {"ctx": calibration.ctx, "n_cpu_moe": selected.n_cpu_moe},
        "observed": _observed_entry(selected),
        "benchmark": _benchmark_entry(selected),
        "search": _search_entry(calibration),
        "selection_rule": calibration.selection_rule,
    }
