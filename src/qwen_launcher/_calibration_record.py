"""Build, validate, and atomically manage versioned private calibration records."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import cast
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from qwen_launcher._calibration_v5_types import ModeCalibration
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.paths import data_dir
from qwen_launcher.resources import read_json

JsonObject = dict[str, object]
_RECORD_SCHEMA_FILES = {
    "calibration-record/v2": "calibration-record.v2.json",
    "calibration-record/v3": "calibration-record.v3.json",
    "calibration-record/v4": "calibration-record.v4.json",
    "calibration-record/v5": "calibration-record.v5.json",
}


class RecordError(RuntimeError):
    """Report a local record that cannot be trusted or promoted."""


class RecordSupersededError(RecordError):
    """Report a historical record version that the current launcher cannot reuse."""


def records_directory() -> Path:
    """Return the managed active/candidate/previous record directory without creating it."""
    return data_dir() / "calibration" / "records"


def _root(selected_root: Path | None) -> Path:
    """Resolve an optional test or operation-owned record root."""
    return records_directory() if selected_root is None else selected_root


def record_path(mode_id: str, selected_root: Path | None = None) -> Path:
    """Return one mode's active record path without creating anything."""
    return _root(selected_root) / f"{mode_id}.json"


def candidate_record_path(mode_id: str, selected_root: Path | None = None) -> Path:
    """Return one mode's pending candidate path without creating anything."""
    return _root(selected_root) / f"{mode_id}.candidate.json"


def previous_record_path(mode_id: str, selected_root: Path | None = None) -> Path:
    """Return one mode's single rollback-slot path without creating anything."""
    return _root(selected_root) / f"{mode_id}.previous.json"


def command_contract_sha256(lock: JsonObject) -> str:
    """Digest the lock command contract so identity detects semantic changes."""
    canonical = json.dumps(lock["command_contract"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_record(
    target: CalibrationTarget, calibration: ModeCalibration, evidence_run_id: str
) -> JsonObject:
    """Build one complete calibration-record/v4 candidate document."""
    from qwen_launcher._calibration_record_build import build_record_document

    return build_record_document(target, calibration, evidence_run_id)


def _mode_from_path(path: Path) -> str:
    """Derive mode identity from active, candidate, or previous lifecycle names."""
    name = path.name
    for suffix in (".candidate.json", ".previous.json", ".json"):
        if name.endswith(suffix):
            return name.removesuffix(suffix)
    return path.stem


def _record_schema(document: JsonObject, path: Path) -> JsonObject:
    """Load the exact packaged schema declared by one supported record version."""
    schema_id = document.get("schema")
    schema_name = _RECORD_SCHEMA_FILES.get(schema_id) if isinstance(schema_id, str) else None
    if schema_name is None:
        raise RecordError(f"local calibration record {path} has unsupported schema {schema_id!r}")
    return cast(JsonObject, read_json(f"schemas/{schema_name}"))


def _validate_record(document: JsonObject, path: Path) -> None:
    """Validate one decoded record's file identity, schema, and semantics."""
    from qwen_launcher._calibration_record_checks import verify_record

    if document.get("mode") != _mode_from_path(path):
        raise RecordError(f"local calibration record {path} is invalid: mode must match file name")
    validator = Draft202012Validator(_record_schema(document, path), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        raise RecordError(f"local calibration record {path} is invalid: {errors[0].message}")
    if document.get("schema") == "calibration-record/v5":
        from qwen_launcher._calibration_record_v5 import verify_record_v5

        verify_record_v5(document, path)
    else:
        verify_record(document, path)


def write_record(document: JsonObject, path: Path) -> Path:
    """Validate and atomically replace one same-directory lifecycle record."""
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


def _decode_record(path: Path) -> JsonObject:
    """Decode one strict UTF-8 JSON object without yet assigning schema semantics."""
    try:
        decoded = json.loads(path.read_bytes().decode("utf-8"), parse_constant=_reject_nonfinite)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RecordError(f"cannot read local calibration record {path}: {error}") from error
    if not isinstance(decoded, dict):
        raise RecordError(f"local calibration record {path} must contain a JSON object")
    return cast(JsonObject, decoded)


def load_record(path: Path) -> JsonObject:
    """Load supported v2/v3/v4 records or diagnose historical v1 evidence as superseded."""
    document = _decode_record(path)
    if document.get("schema") == "calibration-record/v1":
        raise RecordSupersededError(
            f"local calibration record {path} uses superseded calibration-record/v1; "
            "rerun `qwen-launcher calibrate`"
        )
    _validate_record(document, path)
    return document


def _preserve_previous(active: Path, previous: Path) -> None:
    """Prepare the rollback slot without moving or weakening the current active record."""
    temporary = previous.with_name(f".{previous.name}.{uuid4().hex}.tmp")
    try:
        with active.open("rb") as source, temporary.open("xb") as output:
            shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(previous)
    finally:
        temporary.unlink(missing_ok=True)


def promote_candidate(mode_id: str, selected_root: Path | None = None) -> Path:
    """Atomically replace active with a validated candidate while retaining one rollback slot."""
    candidate = candidate_record_path(mode_id, selected_root)
    active = record_path(mode_id, selected_root)
    previous = previous_record_path(mode_id, selected_root)
    if not candidate.is_file():
        raise RecordError(f"no pending calibration candidate for mode {mode_id!r}")
    load_record(candidate)
    active.parent.mkdir(parents=True, exist_ok=True)
    if active.is_file():
        _preserve_previous(active, previous)
    try:
        candidate.replace(active)
    except OSError as error:
        raise RecordError(f"cannot activate calibration candidate {candidate}: {error}") from error
    return active
