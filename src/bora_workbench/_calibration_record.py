"""Own what one calibration run leaves on disk: its record, its evidence, and their privacy.

One record format is supported. ``RECORD_SCHEMA`` identifies it inside the file so a record written
by an older launcher is diagnosed as superseded instead of being misread; it is a data-format marker
and never a choice the operator has to make.

The record is lean (spec 3.6): probes, pruned candidates and logs are not duplicated in it, because
they live in the evidence tree keyed by ``evidence_run_id``; only the envelopes and the per-round
medians that reconstruct the selection are retained. Evidence promotion and the privacy rules belong
here for the same reason: they decide what those two artifacts may contain and keep.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import shutil
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from bora_workbench._calibration_runner import ModeResult
from bora_workbench._calibration_types import (
    BALANCED_CEILING,
    CALIBRATION_PROTOCOL,
    DEADBAND_PCT,
    MIN_CTX_FAST,
    PREFERENCES,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    EnvelopeResult,
    Preference,
    launcher_version,
)
from bora_workbench.calibration import CalibrationTarget
from bora_workbench.paths import data_dir
from bora_workbench.profiles import Mode
from bora_workbench.resources import read_json

JsonObject = dict[str, object]
RECORD_SCHEMA = "calibration-record/v5"
_RECORD_SCHEMA_FILE = "schemas/calibration-record.v5.json"
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_GENERIC_PRIVATE_PATTERNS = (
    re.compile(r"(?<![\w:])/(?:home|Users)/[^/\s\"']+"),
    re.compile(r"(?<![\w:])/(?:root|tmp|var|opt|mnt|media|srv|run|etc)(?:/[^\s\"']+)+"),
    re.compile(r"(?i)(?<![a-z0-9])[a-z]:[\\/][^\s\"']+"),
    re.compile(r"\\\\[^\\/\s]+[\\/][^\\/\s]+"),
)


class RecordError(RuntimeError):
    """Report a local record that cannot be trusted or promoted."""


class RecordSupersededError(RecordError):
    """Report a record written by an older launcher that this one cannot reuse."""


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


def _mode_policy_sha256(mode: Mode) -> str:
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


@dataclass(frozen=True, slots=True)
class RecordContext:
    """Group per-run identity the builder cannot read from the measured samples."""

    target: CalibrationTarget
    evidence_run_id: str
    active_preference: Preference
    gpu_driver: str | None


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


def build_record(context: RecordContext, result: ModeResult) -> JsonObject:
    """Build one complete candidate record document for one measured mode."""
    target = context.target
    artifact = cast(JsonObject, target.lock["default_model_artifact"])
    return {
        "schema": RECORD_SCHEMA,
        "mode": result.mode.id,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "launcher_version": launcher_version(),
        "calibration_protocol": CALIBRATION_PROTOCOL,
        "model": target.config.model,
        "model_sha256": artifact["sha256"],
        "engine_release": target.lock["release"],
        "engine_source_commit": target.lock["source_commit"],
        "command_contract_sha256": command_contract_sha256(target.lock),
        "mode_policy_sha256": _mode_policy_sha256(result.mode),
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


def _invalid_record(path: Path, message: str) -> RecordError:
    """Build one actionable semantic record rejection tied to its file."""
    return RecordError(f"local calibration record {path} is invalid: {message}")


def _mode_from_path(path: Path) -> str:
    """Derive mode identity from active, candidate, or previous lifecycle names."""
    name = path.name
    for suffix in (".candidate.json", ".previous.json", ".json"):
        if name.endswith(suffix):
            return name.removesuffix(suffix)
    return path.stem


def _verify_record(document: JsonObject, path: Path) -> None:
    """Cross-check the fields JSON Schema cannot: reserves and the active envelope."""
    reserves = cast(JsonObject, document["reserves"])
    expected = {
        "vram_gib": VRAM_RESERVE_GIB,
        "ram_gib": RAM_RESERVE_GIB,
        "release_tolerance_gib": RELEASE_TOLERANCE_GIB,
    }
    if reserves != expected:
        raise _invalid_record(path, "record reserves do not match the pinned calibration constants")
    envelopes = cast(JsonObject, document["envelopes"])
    if document["active_preference"] not in envelopes:
        raise _invalid_record(path, "active preference must name one recorded envelope")


def _validate_record(document: JsonObject, path: Path) -> None:
    """Validate one decoded record's file identity, schema, and semantics."""
    if document.get("mode") != _mode_from_path(path):
        raise _invalid_record(path, "mode must match file name")
    if document.get("schema") != RECORD_SCHEMA:
        raise RecordError(
            f"local calibration record {path} has unsupported schema {document.get('schema')!r}"
        )
    schema = cast(JsonObject, read_json(_RECORD_SCHEMA_FILE))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        raise _invalid_record(path, errors[0].message)
    _verify_record(document, path)


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
    """Load one current record, diagnosing any record an older launcher wrote as superseded."""
    document = _decode_record(path)
    schema = document.get("schema")
    if isinstance(schema, str) and schema != RECORD_SCHEMA and schema.startswith("calibration-"):
        raise RecordSupersededError(
            f"local calibration record {path} uses superseded schema {schema}; "
            "rerun `bora calibrate`"
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


def _rotate(destination: Path) -> None:
    """Delete only older UUID-named managed evidence after the new run is in place."""
    for child in destination.parent.iterdir():
        if child == destination or not child.is_dir() or not _RUN_ID.fullmatch(child.name):
            continue
        shutil.rmtree(child)


def preserve_evidence(calibration_root: Path, runtime_root: Path, run_id: str) -> Path:
    """Promote runtime logs to the latest evidence slot before removing the prior slot."""
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("calibration evidence run id must be 32 lowercase hexadecimal characters")
    directory = calibration_root / "evidence"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / run_id
    if destination.exists():
        raise FileExistsError(f"calibration evidence destination already exists: {destination}")
    runtime_root.replace(destination)
    _rotate(destination)
    return destination


def has_private_path_pattern(text: str) -> bool:
    """Return whether text contains a generic POSIX, Windows, or UNC private path."""
    return any(pattern.search(text) for pattern in _GENERIC_PRIVATE_PATTERNS)


def _local_markers(root: Path) -> tuple[str, ...]:
    """Return local identity and path values that must not occur in a shared bundle."""
    values = {
        getpass.getuser(),
        socket.gethostname(),
        str(Path.home()),
        str(root.resolve()),
    }
    expanded = values | {value.replace("\\", "/") for value in values}
    return tuple(sorted((value for value in expanded if value), key=len, reverse=True))


def privacy_findings(root: Path) -> tuple[tuple[str, str], ...]:
    """Find local identity values and generic absolute paths in every shareable file."""
    markers = _local_markers(root)
    findings: list[tuple[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        if any(marker in text for marker in markers):
            findings.append((relative, "contains local username, hostname, or absolute path"))
            continue
        if has_private_path_pattern(text):
            findings.append((relative, "contains a private absolute path pattern"))
    return tuple(findings)
