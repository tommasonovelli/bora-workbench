"""Validate a generated calibration bundle without changing installed-resource validation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

from jsonschema import Draft202012Validator, FormatChecker

from qwen_launcher._validation_report import validate_reports
from qwen_launcher.profiles import load_catalog
from qwen_launcher.resources import read_json
from qwen_launcher.validation import Document, JsonObject, ValidationIssue, ValidationResult


def _issue(file: str, path: str, message: str) -> ValidationIssue:
    """Create one deterministic bundle validation error."""
    return ValidationIssue("error", file, path, message)


def _field_path(parts: Iterable[object]) -> str:
    """Render a jsonschema path consistently with installed-resource validation."""
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _safe_relative(value: str) -> bool:
    """Reject cross-platform absolute, drive-relative, and parent-traversal manifest paths."""
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return bool(value) and not (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    )


def _read_object(path: Path) -> tuple[JsonObject | None, list[ValidationIssue]]:
    """Read one strict UTF-8 bundle JSON object."""
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, [_issue(path.name, "$", f"invalid UTF-8 JSON: {error}")]
    if not isinstance(value, dict):
        return None, [_issue(path.name, "$", "top-level JSON value must be an object")]
    return cast(JsonObject, value), []


def _report(root: Path) -> tuple[Document | None, list[ValidationIssue]]:
    """Schema- and semantic-validate the single draft calibration report."""
    files = sorted(root.glob("calibration-*.json"))
    if len(files) != 1:
        return None, [_issue(str(root), "$", "bundle must contain exactly one report")]
    path = files[0]
    value, issues = _read_object(path)
    if value is None:
        return None, issues
    schema = cast(JsonObject, read_json("schemas/calibration-report.v1.json"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    issues.extend(
        _issue(path.name, _field_path(error.absolute_path), error.message) for error in errors
    )
    document = Document(path.name, path.stem, value, path.read_bytes())
    if not errors:
        mode_ids = {mode.id for mode in load_catalog().modes}
        issues.extend(validate_reports((document,), mode_ids))
    return document, issues


def _manifest(root: Path) -> list[ValidationIssue]:
    """Require safe, complete, duplicate-free SHA-256 coverage of every shareable file."""
    path = root / "SHA256SUMS"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        return [_issue("SHA256SUMS", "$", f"cannot read manifest: {error}")]
    issues: list[ValidationIssue] = []
    entries: dict[str, str] = {}
    for index, line in enumerate(lines):
        fields = line.split("  ", 1)
        if len(fields) != 2 or len(fields[0]) != 64 or not _safe_relative(fields[-1]):
            issues.append(_issue("SHA256SUMS", f"$[{index}]", "invalid manifest entry"))
            continue
        digest, relative = fields
        if relative in entries:
            issues.append(_issue("SHA256SUMS", f"$[{index}]", "duplicate manifest path"))
        entries[relative] = digest
    actual = {
        file.relative_to(root).as_posix()
        for file in root.rglob("*")
        if file.is_file() and file.name != "SHA256SUMS"
    }
    if set(entries) != actual:
        issues.append(_issue("SHA256SUMS", "$", "manifest file set differs from bundle"))
    for relative, expected in entries.items():
        file = root / relative
        if not file.is_file():
            continue
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if digest != expected:
            issues.append(_issue("SHA256SUMS", relative, "SHA-256 mismatch"))
    return issues


def _log_digests(root: Path, document: Document | None) -> list[ValidationIssue]:
    """Verify every report log digest against its relative bundle file."""
    if document is None:
        return []
    issues: list[ValidationIssue] = []
    modes = cast(JsonObject, document.data["modes"])
    for mode_value in modes.values():
        candidates = cast(list[JsonObject], cast(JsonObject, mode_value)["candidates"])
        for candidate in candidates:
            for log in cast(list[JsonObject], candidate["log_digests"]):
                relative = cast(str, log["path"])
                file = root / relative
                if not file.is_file():
                    issues.append(_issue(document.file, relative, "referenced log is missing"))
                    continue
                actual = hashlib.sha256(file.read_bytes()).hexdigest()
                if actual != log["sha256"]:
                    issues.append(_issue(document.file, relative, "log SHA-256 mismatch"))
    return issues


def _proposal(root: Path, document: Document | None) -> list[ValidationIssue]:
    """Ensure draft selections reference valid candidates without claiming an approved window."""
    value, issues = _read_object(root / "profile-proposal.json")
    if value is None or document is None:
        return issues
    if value.get("status") != "draft-not-distributable":
        issues.append(_issue("profile-proposal.json", "$.status", "must remain a draft"))
    if value.get("match") is not None or value.get("hardware_class") is not None:
        issues.append(_issue("profile-proposal.json", "$.match", "cannot invent a hardware class"))
    report_modes = cast(JsonObject, document.data["modes"])
    proposal_modes = value.get("modes")
    if not isinstance(proposal_modes, dict) or set(proposal_modes) != set(report_modes):
        issues.append(_issue("profile-proposal.json", "$.modes", "must match report modes"))
        return issues
    for mode_id, proposal_value in proposal_modes.items():
        proposal = cast(JsonObject, proposal_value)
        selected = proposal.get("proposed_candidate_id")
        candidates = cast(list[JsonObject], cast(JsonObject, report_modes[mode_id])["candidates"])
        valid_ids = {item["id"] for item in candidates if item["outcome"] == "valid"}
        if selected is not None and selected not in valid_ids:
            path = f"$.modes.{mode_id}.proposed_candidate_id"
            issues.append(_issue("profile-proposal.json", path, "must reference a valid candidate"))
    return issues


def validate_bundle(root: Path) -> ValidationResult:
    """Validate one local Step 5A bundle independently from packaged resource content."""
    if not root.is_dir():
        return ValidationResult((_issue(str(root), "$", "bundle path must be a directory"),))
    document, issues = _report(root)
    issues.extend(_manifest(root))
    issues.extend(_log_digests(root, document))
    issues.extend(_proposal(root, document))
    return ValidationResult(tuple(sorted(issues, key=lambda item: (item.file, item.field_path))))
