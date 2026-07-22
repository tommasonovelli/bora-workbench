"""Serialize measured calibration/v4 evidence into calibration-record/v3 documents."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from qwen_launcher._calibration_metadata import launcher_version
from qwen_launcher._calibration_record_evidence import (
    finalist_entry,
    probe_trial_entry,
    selected_benchmark_entry,
    vram_needed,
)
from qwen_launcher._calibration_v4_types import (
    CALIBRATION_V4_PROTOCOL,
    CONFIRM_ROUNDS,
    CONTEXT_SCALE,
    MODE_PROBE_CAP,
    OBJECTIVE,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    ModeCalibration,
)
from qwen_launcher._gpu_process_identity import GPU_CONTEXT_IDENTITY_MODEL
from qwen_launcher.calibration import CalibrationTarget

JsonObject = dict[str, object]


def _hardware_identity(target: CalibrationTarget, gpu_driver: str | None) -> JsonObject:
    """Build the stable hardware identity required for local reuse."""
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


def _observed_entry(calibration: ModeCalibration) -> JsonObject:
    """Serialize selected minima and conservative needs used by launch-time headroom."""
    selected = calibration.selected
    if selected.ram is None:
        raise ValueError("selected finalist requires measured RAM evidence")
    return {
        "ram_needed_gib": selected.ram.needed_gib,
        "minimum_ram_available_gib": selected.ram.minimum_available_gib,
        "vram_needed_gib": vram_needed(selected),
        "minimum_vram_free_gib": (
            None if selected.vram is None else selected.vram.minimum_free_gib
        ),
    }


def _probe_entry(probe: object) -> JsonObject:
    """Serialize one typed probe without broadening the public record builder interface."""
    from qwen_launcher._calibration_v4_types import ProbeRecord

    if not isinstance(probe, ProbeRecord):
        raise TypeError("calibration probe has an invalid runtime type")
    return {
        "ctx": probe.ctx,
        "n_cpu_moe": probe.n_cpu_moe,
        "is_feasible": probe.is_feasible,
        "reason": probe.reason,
        "trial": probe_trial_entry(probe.trial),
    }


def _search_entry(calibration: ModeCalibration, is_cuda: bool) -> JsonObject:
    """Serialize constants, context identity, screening, sessions, drift, and winners."""
    return {
        "context_scale": list(CONTEXT_SCALE),
        "context_identity_model": GPU_CONTEXT_IDENTITY_MODEL if is_cuda else None,
        "target_ctx": calibration.target_ctx,
        "probe_cap": MODE_PROBE_CAP,
        "vram_reserve_gib": VRAM_RESERVE_GIB,
        "ram_reserve_gib": RAM_RESERVE_GIB,
        "release_tolerance_gib": RELEASE_TOLERANCE_GIB,
        "confirm_rounds": CONFIRM_ROUNDS,
        "did_degrade": calibration.did_degrade,
        "baseline_drift_gib": calibration.baseline_drift_gib,
        "round_winners": list(calibration.round_winners),
        "probes": [_probe_entry(probe) for probe in calibration.probes],
        "finalists": [
            finalist_entry(finalist, finalist is calibration.selected)
            for finalist in calibration.finalists
        ],
    }


def build_record_document(
    target: CalibrationTarget, calibration: ModeCalibration, evidence_run_id: str
) -> JsonObject:
    """Build one complete calibration-record/v3 candidate document."""
    from qwen_launcher._calibration_record import command_contract_sha256

    selected = calibration.selected
    artifact = cast(JsonObject, target.lock["default_model_artifact"])
    gpu_driver = None if selected.vram is None else selected.vram.driver_version
    return {
        "schema": "calibration-record/v3",
        "mode": calibration.mode.id,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "launcher_version": launcher_version(),
        "calibration_protocol": CALIBRATION_V4_PROTOCOL,
        "benchmark_protocol": "benchmark/v1",
        "objective": OBJECTIVE,
        "evidence_run_id": evidence_run_id,
        "model": target.config.model,
        "model_sha256": artifact["sha256"],
        "engine_release": target.lock["release"],
        "engine_source_commit": target.lock["source_commit"],
        "command_contract_sha256": command_contract_sha256(target.lock),
        "os_name": target.hardware.os_name,
        "backend": target.hardware.backend,
        "hardware": _hardware_identity(target, gpu_driver),
        "envelope": {"ctx": calibration.ctx, "n_cpu_moe": selected.n_cpu_moe},
        "observed": _observed_entry(calibration),
        "benchmark": selected_benchmark_entry(selected),
        "search": _search_entry(calibration, target.hardware.backend == "cuda"),
        "selection_rule": calibration.selection_rule,
    }
