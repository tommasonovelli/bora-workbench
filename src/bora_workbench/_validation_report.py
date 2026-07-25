"""Semantic checks for calibration-report/v1 documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from statistics import median
from typing import cast

from bora_workbench.validation import Document, JsonObject, ValidationIssue

_GPU_FIELDS = ("gpu_index", "gpu_name", "gpu_driver", "vram_total_gib", "vram_free_gib")
_MEMORY_FIELDS = ("vram_baseline_gib", "vram_peak_gib", "vram_min_free_gib")
_MEMORY_FIELDS += ("vram_release_used_gib",)


@dataclass(frozen=True, slots=True)
class _ReportContext:
    """Hold report-wide facts needed while checking nested candidate results."""

    document: Document
    backend: str
    stable_start_runs: int


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create a report error tied to its source document."""
    return ValidationIssue("error", document.file, path, message)


def _is_relative_path(value: str) -> bool:
    """Reject POSIX or Windows absolute, drive-relative, and parent-traversal paths."""
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return bool(value) and not (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    )


def _timestamp_issues(document: Document) -> list[ValidationIssue]:
    """Require the report timestamp to carry an explicit UTC offset."""
    value = cast(str, document.data["created_at"])
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return [_error(document, "$.created_at", "must be a valid date-time")]
    if timestamp.utcoffset() != UTC.utcoffset(timestamp):
        return [_error(document, "$.created_at", "must be expressed in UTC")]
    return []


def _hardware_issues(document: Document) -> list[ValidationIssue]:
    """Require GPU facts on CUDA and null GPU facts on CPU."""
    hardware = cast(JsonObject, document.data["hardware"])
    backend = cast(str, hardware["backend"])
    issues: list[ValidationIssue] = []
    for field in _GPU_FIELDS:
        value = hardware[field]
        if backend == "cpu" and value is not None:
            issues.append(_error(document, f"$.hardware.{field}", "must be null on CPU"))
        if backend == "cuda" and value is None:
            issues.append(_error(document, f"$.hardware.{field}", "must be present on CUDA"))
    policy = cast(JsonObject, document.data["policy"])
    for field in ("minimum_free_vram_gib", "vram_release_tolerance_gib"):
        value = policy[field]
        if backend == "cpu" and value is not None:
            issues.append(_error(document, f"$.policy.{field}", "must be null on CPU"))
        if backend == "cuda" and value is None:
            issues.append(_error(document, f"$.policy.{field}", "required on CUDA"))
    return issues


def _backend_field_issues(
    context: _ReportContext, path: str, value: JsonObject
) -> list[ValidationIssue]:
    """Validate backend-specific candidate and VRAM fields."""
    issues: list[ValidationIssue] = []
    has_n_cpu_moe = "n_cpu_moe" in value
    if context.backend == "cuda" and not has_n_cpu_moe:
        issues.append(_error(context.document, f"{path}.n_cpu_moe", "required for CUDA"))
    if context.backend == "cpu" and has_n_cpu_moe:
        issues.append(_error(context.document, f"{path}.n_cpu_moe", "forbidden for CPU"))
    for field in _MEMORY_FIELDS:
        if field not in value:
            continue
        if context.backend == "cpu" and value[field] is not None:
            issues.append(_error(context.document, f"{path}.{field}", "must be null on CPU"))
        if context.backend == "cuda" and value[field] is None:
            issues.append(_error(context.document, f"{path}.{field}", "required on CUDA"))
    return issues


def _metric_issues(
    context: _ReportContext, path: str, candidate: JsonObject
) -> list[ValidationIssue]:
    """Verify valid-run counts and exact min/median/max summaries."""
    if candidate["outcome"] != "valid":
        return []
    issues: list[ValidationIssue] = []
    starts = cast(int, candidate["successful_start_runs"])
    if starts < context.stable_start_runs:
        issues.append(_error(context.document, f"{path}.successful_start_runs", "below policy"))
    measurements = cast(list[float], candidate["measured_tok_s"])
    summary = cast(JsonObject, candidate["tok_s"])
    expected = {"min": min(measurements), "median": median(measurements), "max": max(measurements)}
    for field, value in expected.items():
        if summary[field] != value:
            message = "does not match measurements"
            issues.append(_error(context.document, f"{path}.tok_s.{field}", message))
    return issues


def _mode_issues(context: _ReportContext, mode_id: str, mode: JsonObject) -> list[ValidationIssue]:
    """Check candidate identity, ordering, evidence, and final selection for one mode."""
    document = context.document
    base = f"$.modes.{mode_id}.candidates"
    candidates = cast(list[JsonObject], mode["candidates"])
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        candidate_id = cast(str, candidate["id"])
        path = f"{base}[{index}]"
        if candidate_id in seen:
            issues.append(_error(document, f"{path}.id", f"duplicate id {candidate_id!r}"))
        seen.add(candidate_id)
        issues.extend(_backend_field_issues(context, path, candidate))
        issues.extend(_metric_issues(context, path, candidate))
        logs = cast(list[JsonObject], candidate["log_digests"])
        for log_index, log in enumerate(logs):
            if not _is_relative_path(cast(str, log["path"])):
                log_path = f"{path}.log_digests[{log_index}].path"
                issues.append(_error(document, log_path, "must be relative"))
    selected_id = cast(str | None, mode["selected_candidate_id"])
    if selected_id is not None:
        selected = next((item for item in candidates if item["id"] == selected_id), None)
        if selected is None or selected["outcome"] != "valid":
            selection_path = f"$.modes.{mode_id}.selected_candidate_id"
            issues.append(_error(document, selection_path, "must reference a valid candidate"))
    return issues


def _snapshot_issues(context: _ReportContext, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate policy snapshot modes, backend fields, and candidate result order."""
    document = context.document
    policy = cast(JsonObject, document.data["policy"])
    snapshot = cast(list[JsonObject], policy["candidates"])
    modes = cast(JsonObject, document.data["modes"])
    issues: list[ValidationIssue] = []
    for index, candidate in enumerate(snapshot):
        path = f"$.policy.candidates[{index}]"
        mode_id = cast(str, candidate["mode"])
        if mode_id not in mode_ids:
            issues.append(_error(document, f"{path}.mode", "references an unknown mode"))
        issues.extend(_backend_field_issues(context, path, candidate))
    for mode_id, mode_value in modes.items():
        expected = [item["id"] for item in snapshot if item["mode"] == mode_id]
        actual = [item["id"] for item in cast(JsonObject, mode_value)["candidates"]]
        if expected != actual:
            path = f"$.modes.{mode_id}.candidates"
            issues.append(_error(document, path, "order differs from policy snapshot"))
    return issues


def _report_issues(document: Document, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate one schema-valid report and all of its candidate evidence."""
    hardware = cast(JsonObject, document.data["hardware"])
    policy = cast(JsonObject, document.data["policy"])
    context = _ReportContext(
        document, cast(str, hardware["backend"]), cast(int, policy["stable_start_runs"])
    )
    issues = _timestamp_issues(document) + _hardware_issues(document)
    if document.data["id"] != document.stem:
        issues.append(_error(document, "$.id", "must equal the file name"))
    manifest = cast(str, document.data["evidence_manifest"])
    if not _is_relative_path(manifest):
        issues.append(_error(document, "$.evidence_manifest", "must be relative"))
    modes = cast(JsonObject, document.data["modes"])
    for mode_id, mode_value in modes.items():
        if mode_id not in mode_ids:
            issues.append(_error(document, f"$.modes.{mode_id}", "references an unknown mode"))
        issues.extend(_mode_issues(context, mode_id, cast(JsonObject, mode_value)))
    issues.extend(_snapshot_issues(context, mode_ids))
    return issues


def validate_reports(documents: tuple[Document, ...], mode_ids: set[str]) -> list[ValidationIssue]:
    """Return semantic issues from every schema-valid calibration report."""
    issues: list[ValidationIssue] = []
    for document in documents:
        if document.data.get("schema") == "calibration-report/v1":
            issues.extend(_report_issues(document, mode_ids))
    return issues
