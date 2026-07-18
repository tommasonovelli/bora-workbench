"""Build, atomically write, and load the private local calibration-record/v1 document.

The record is the only artifact the runtime may treat as locally calibrated (D-035/D-038). It
lives in the managed data directory, never in the wheel, and every load revalidates the schema and
reconstructs the selection so a tampered or stale record can never silently steer a launch.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from statistics import median
from typing import cast
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from qwen_launcher._calibration_v2_search import select_candidate_index
from qwen_launcher._calibration_v2_types import ModeCalibration, SelectionCandidate
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


def build_record(target: CalibrationTarget, calibration: ModeCalibration) -> JsonObject:
    """Build one complete calibration-record/v1 document from measured evidence."""
    from qwen_launcher._calibration_record_build import build_record_document

    return build_record_document(target, calibration)


def _validate_record(document: JsonObject, path: Path) -> None:
    """Validate one decoded record's file identity, schema, and semantics."""
    from qwen_launcher._calibration_record_checks import verify_record

    if document.get("mode") != path.stem:
        raise RecordError(f"local calibration record {path} is invalid: mode must match file name")
    schema = cast(JsonObject, read_json("schemas/calibration-record.v1.json"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        raise RecordError(f"local calibration record {path} is invalid: {errors[0].message}")
    verify_record(document, path)


def write_record(document: JsonObject, path: Path) -> Path:
    """Validate and atomically replace one same-directory local record."""
    _validate_record(document, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(document, output, indent=2, ensure_ascii=False, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _reject_nonfinite(value: str) -> object:
    """Reject JavaScript non-finite constants because records are strict JSON."""
    raise ValueError(f"non-finite JSON number {value}")


def load_record(path: Path) -> JsonObject:
    """Load one record, revalidating schema, summary coherence, and the selection."""
    try:
        decoded = json.loads(path.read_bytes().decode("utf-8"), parse_constant=_reject_nonfinite)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RecordError(f"cannot read local calibration record {path}: {error}") from error
    if not isinstance(decoded, dict):
        raise RecordError(f"local calibration record {path} must contain a JSON object")
    document = cast(JsonObject, decoded)
    _validate_record(document, path)
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
