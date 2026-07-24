"""Serialize calibration/v6-lite results into lean calibration-record/v5 documents (spec 3.6).

Probes, pruned candidates, and logs are not duplicated here; they live in the evidence tree keyed by
``evidence_run_id``. Only the envelopes and the per-round medians that reconstruct the selection are
retained, consistent with the repository norm for reproducible records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from qwen_launcher._calibration_metadata import launcher_version
from qwen_launcher._calibration_record_sessions import fail
from qwen_launcher._calibration_v6_runner import ModeResult
from qwen_launcher._calibration_v6_types import (
    BALANCED_CEILING,
    DEADBAND_PCT,
    MIN_CTX_FAST,
    PREFERENCES,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    EnvelopeResult,
    Preference,
)
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.profiles import Mode

JsonObject = dict[str, object]


@dataclass(frozen=True, slots=True)
class V6RecordContext:
    """Group per-run identity the builder cannot read from the measured samples."""

    target: CalibrationTarget
    evidence_run_id: str
    active_preference: Preference
    gpu_driver: str | None


def mode_policy_sha256(mode: Mode) -> str:
    """Digest the canonical mode/v2 behavior so record identity tracks the used policy."""
    sampling = mode.sampling
    canonical = {
        "id": mode.id,
        "services": {"ui": mode.services.ui, "vision": mode.services.vision},
        "sampling": {
            "temp": sampling.temp,
            "top_p": sampling.top_p,
            "top_k": sampling.top_k,
            "min_p": sampling.min_p,
            "presence_penalty": sampling.presence_penalty,
            "repeat_penalty": sampling.repeat_penalty,
            "reasoning": sampling.reasoning,
        },
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _envelope_entry(result: EnvelopeResult) -> JsonObject:
    """Serialize one gated envelope's identity, quick summary, needs, and minima."""
    sample = result.sample
    return {
        "ctx": sample.ctx,
        "n_cpu_moe": sample.n_cpu_moe,
        "speculative": sample.speculative,
        "quick": {
            "e2e_ms": sample.e2e_ms,
            "prefill_tps": sample.prefill_tps,
            "decode_tps": sample.decode_tps,
        },
        "gate": {
            "smoke": result.gate.smoke,
            "multi_turn": result.gate.multi_turn,
            "vision": result.gate.vision,
        },
        "ram_needed_gib": sample.ram_needed_gib,
        "vram_needed_gib": sample.vram_needed_gib,
        "minima": {
            "minimum_ram_available_gib": sample.ram_min_available_gib,
            "minimum_vram_free_gib": sample.vram_min_free_gib,
        },
    }


def _hardware(target: CalibrationTarget, gpu_driver: str | None) -> JsonObject:
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


def _selection_inputs(result: ModeResult) -> JsonObject:
    """Serialize the per-round finalist medians that reconstruct each confirmation."""
    return {
        preference: {
            "round_medians": [list(pair) for pair in result.selection_inputs.get(preference, ())]
        }
        for preference in PREFERENCES
    }


def build_record_v5(context: V6RecordContext, result: ModeResult) -> JsonObject:
    """Build one complete calibration-record/v5 candidate document."""
    from qwen_launcher._calibration_record import command_contract_sha256

    target = context.target
    artifact = cast(JsonObject, target.lock["default_model_artifact"])
    return {
        "schema": "calibration-record/v5",
        "mode": result.mode.id,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "launcher_version": launcher_version(),
        "calibration_protocol": "calibration/v6-lite",
        "model": target.config.model,
        "model_sha256": artifact["sha256"],
        "engine_release": target.lock["release"],
        "engine_source_commit": target.lock["source_commit"],
        "command_contract_sha256": command_contract_sha256(target.lock),
        "mode_policy_sha256": mode_policy_sha256(result.mode),
        "os_name": target.hardware.os_name,
        "backend": target.hardware.backend,
        "hardware": _hardware(target, context.gpu_driver),
        "evidence_run_id": context.evidence_run_id,
        "active_preference": context.active_preference,
        "thresholds": {
            "deadband_pct": DEADBAND_PCT,
            "balanced_ceiling": BALANCED_CEILING,
            "min_ctx_fast": MIN_CTX_FAST,
        },
        "reserves": {
            "vram_gib": VRAM_RESERVE_GIB,
            "ram_gib": RAM_RESERVE_GIB,
            "release_tolerance_gib": RELEASE_TOLERANCE_GIB,
        },
        "envelopes": {pref: _envelope_entry(result.envelopes[pref]) for pref in PREFERENCES},
        "selection_inputs": _selection_inputs(result),
    }


def verify_record_v5(document: JsonObject, path: Path) -> None:
    """Cross-check v5 fields that JSON Schema cannot: reserves and the active envelope."""
    reserves = cast(JsonObject, document["reserves"])
    expected = {
        "vram_gib": VRAM_RESERVE_GIB,
        "ram_gib": RAM_RESERVE_GIB,
        "release_tolerance_gib": RELEASE_TOLERANCE_GIB,
    }
    if reserves != expected:
        raise fail(path, "v6-lite record reserves do not match the pinned v6 constants")
    envelopes = cast(JsonObject, document["envelopes"])
    if document["active_preference"] not in envelopes:
        raise fail(path, "active preference must name one recorded envelope")
