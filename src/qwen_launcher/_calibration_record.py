"""Build, atomically write, and load the private local calibration-record/v1 document.

The record is the only artifact the runtime may treat as locally calibrated (D-035/D-038). It
lives in the managed data directory, never in the wheel, and every load revalidates the schema and
reconstructs the selection so a tampered or stale record can never silently steer a launch.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import cast
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from qwen_launcher._calibration_metadata import launcher_version
from qwen_launcher._calibration_v2_search import select_candidate_index
from qwen_launcher._calibration_v2_types import (
    CALIBRATION_V2_PROTOCOL,
    CONTEXT_SCALE,
    MODE_PROBE_CAP,
    RELEASE_TOLERANCE_GIB,
    STABLE_START_RUNS,
    VRAM_RESERVE_GIB,
    ModeCalibration,
    SelectionCandidate,
)
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.paths import data_dir
from qwen_launcher.resources import read_json

JsonObject = dict[str, object]


class RecordError(RuntimeError):
    """Report a local record that cannot be trusted for launch reuse."""


def records_directory() -> Path:
    """Return the managed per-mode record directory without creating it."""
    return data_dir() / "calibration" / "records"


def record_path(mode_id: str) -> Path:
    """Return the path of one mode's local record without creating anything."""
    return records_directory() / f"{mode_id}.json"


def command_contract_sha256(lock: JsonObject) -> str:
    """Digest the lock's command contract so record identity detects contract changes."""
    canonical = json.dumps(lock["command_contract"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hardware_identity(target: CalibrationTarget, gpu_driver: str | None) -> JsonObject:
    """Build the stable hardware identity fields fixed by design section 3, step 5."""
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


def _finalist_entries(calibration: ModeCalibration) -> list[JsonObject]:
    """Serialize every finalist with the exact fields selection reconstruction reads."""
    entries: list[JsonObject] = []
    for finalist in calibration.finalists:
        benchmark = finalist.benchmark
        entries.append(
            {
                "n_cpu_moe": finalist.n_cpu_moe,
                "outcome": finalist.outcome,
                "discard_reason": finalist.discard_reason,
                "measured_tok_s": None if benchmark is None else list(benchmark.measured_tok_s),
                "minimum_free_vram_gib": None
                if finalist.vram is None
                else finalist.vram.minimum_free_gib,
                "is_selected": finalist is calibration.selected,
            }
        )
    return entries


def build_record(target: CalibrationTarget, calibration: ModeCalibration) -> JsonObject:
    """Build one complete calibration-record/v1 document from measured evidence."""
    selected = calibration.selected
    benchmark, vram, ram = selected.benchmark, selected.vram, selected.ram
    assert benchmark is not None and ram is not None
    artifact = cast(JsonObject, target.lock["default_model_artifact"])
    rates = benchmark.tok_s
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
        "hardware": _hardware_identity(target, None if vram is None else vram.driver_version),
        "envelope": {"ctx": calibration.ctx, "n_cpu_moe": selected.n_cpu_moe},
        "observed": {
            "ram_needed_gib": ram.needed_gib,
            "minimum_ram_available_gib": ram.minimum_available_gib,
            "vram_needed_gib": None
            if vram is None
            else vram.peak_used_gib - vram.baseline_used_gib,
            "minimum_vram_free_gib": None if vram is None else vram.minimum_free_gib,
        },
        "benchmark": {
            "warmup_tok_s": benchmark.warmup_tok_s,
            "measured_tok_s": list(benchmark.measured_tok_s),
            "tok_s": {"min": rates.minimum, "median": rates.median, "max": rates.maximum},
        },
        "search": {
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
                }
                for probe in calibration.probes
            ],
            "finalists": _finalist_entries(calibration),
        },
        "selection_rule": calibration.selection_rule,
    }


def write_record(document: JsonObject, path: Path) -> Path:
    """Write one record through a flushed same-directory temporary file, then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(document, output, indent=2, ensure_ascii=False)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)
    return path


def load_record(path: Path) -> JsonObject:
    """Load one record, revalidating schema, summary coherence, and the selection."""
    from qwen_launcher._calibration_record_checks import verify_record

    try:
        decoded = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecordError(f"cannot read local calibration record {path}: {error}") from error
    if not isinstance(decoded, dict):
        raise RecordError(f"local calibration record {path} must contain a JSON object")
    document = cast(JsonObject, decoded)
    schema = cast(JsonObject, read_json("schemas/calibration-record.v1.json"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        raise RecordError(f"local calibration record {path} is invalid: {errors[0].message}")
    verify_record(document, path)
    return document


def reconstruct_selection(finalists: list[JsonObject]) -> tuple[int, str]:
    """Recompute the winning valid finalist and rule from serialized evidence."""
    candidates = []
    for entry in finalists:
        if entry["outcome"] != "valid":
            continue
        measured = [float(value) for value in cast(list[float], entry["measured_tok_s"])]
        free = cast(float | None, entry["minimum_free_vram_gib"])
        moe = cast(int | None, entry["n_cpu_moe"])
        candidates.append(SelectionCandidate(median(measured), max(measured), free, moe))
    if not candidates:
        raise RecordError("local calibration record has no valid finalist")
    return select_candidate_index(tuple(candidates))
