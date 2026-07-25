"""Validate packaged declarative content and report precise, actionable issues.

The module owns the validation entry point of specification section 4.1: it declares the issue
model shared by every checker, meta-validates the packaged Draft 2020-12 schemas, applies them to
each content document, and delegates the cross-document semantics to the engine-lock, calibration,
and profile checkers. Only documents that pass their schema reach those semantic checks, so a
malformed file is reported once instead of producing a cascade of derived complaints.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import Literal

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from bora_workbench.resources import resource_root

JsonObject = dict[str, object]

_SCHEMA_FILES = {
    "mode/v1": "mode.v1.json",
    "mode/v2": "mode.v2.json",
    "profile/v1": "profile.v1.json",
    "calibration-policy/v1": "calibration-policy.v1.json",
    "calibration-policy/v2": "calibration-policy.v2.json",
    "calibration-report/v1": "calibration-report.v1.json",
    "calibration-report/v2": "calibration-report.v2.json",
    "calibration-record/v5": "calibration-record.v5.json",
}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Describe one validation failure or non-blocking warning."""

    severity: Literal["error", "warning"]
    file: str
    field_path: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Collect deterministic validation issues and expose exit-code categories."""

    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """Return blocking issues."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Return non-blocking issues."""
        return tuple(issue for issue in self.issues if issue.severity == "warning")


@dataclass(frozen=True, slots=True)
class Document:
    """Hold one decoded content file and its exact bytes for digest checks."""

    file: str
    stem: str
    data: JsonObject
    raw_bytes: bytes


def _field_path(parts: Iterable[object]) -> str:
    """Render a jsonschema absolute path as a stable field location."""
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _read_object(file: Traversable, label: str) -> tuple[Document | None, list[ValidationIssue]]:
    """Read one strict UTF-8 JSON object while preserving bytes for SHA-256."""
    try:
        raw_bytes = file.read_bytes()
        decoded = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, [ValidationIssue("error", label, "$", f"invalid UTF-8 JSON: {error}")]
    if not isinstance(decoded, dict):
        message = "top-level JSON value must be an object"
        return None, [ValidationIssue("error", label, "$", message)]
    return Document(label, file.name.removesuffix(".json"), decoded, raw_bytes), []


def _load_schemas(root: Traversable) -> tuple[dict[str, JsonObject], list[ValidationIssue]]:
    """Load and meta-validate every required Draft 2020-12 schema."""
    schemas: dict[str, JsonObject] = {}
    issues: list[ValidationIssue] = []
    directory = root.joinpath("schemas")
    for schema_id, name in _SCHEMA_FILES.items():
        document, read_issues = _read_object(directory.joinpath(name), f"schemas/{name}")
        issues.extend(read_issues)
        if document is None:
            continue
        try:
            Draft202012Validator.check_schema(document.data)
        except SchemaError as error:
            issues.append(
                ValidationIssue("error", document.file, "$", f"invalid schema: {error.message}")
            )
            continue
        schemas[schema_id] = document.data
    return schemas, issues


def _json_children(directory: Traversable, prefix: str) -> tuple[tuple[Traversable, str], ...]:
    """Return sorted JSON children and labels, or an empty tuple for an absent directory."""
    if not directory.is_dir():
        return ()
    files = sorted(
        (item for item in directory.iterdir() if item.name.endswith(".json")),
        key=lambda item: item.name,
    )
    return tuple((file, f"{prefix}/{file.name}") for file in files)


def _content_files(root: Traversable) -> tuple[tuple[Traversable, str], ...]:
    """Enumerate only the versioned content locations supported by the package."""
    content = root.joinpath("content")
    files = list(_json_children(content.joinpath("modes"), "content/modes"))
    files.extend(_json_children(content.joinpath("profiles"), "content/profiles"))
    files.extend(_json_children(content.joinpath("calibrations"), "content/calibrations"))
    policy = content.joinpath("calibration-policy.json")
    if policy.is_file():
        files.append((policy, "content/calibration-policy.json"))
    return tuple(files)


def _validate_schema(document: Document, schemas: dict[str, JsonObject]) -> list[ValidationIssue]:
    """Validate one document and preserve every field-level schema error."""
    schema_id = document.data.get("schema")
    if not isinstance(schema_id, str) or schema_id not in _SCHEMA_FILES:
        message = "unknown or missing schema identifier"
        return [ValidationIssue("error", document.file, "$.schema", message)]
    schema = schemas.get(schema_id)
    if schema is None:
        message = f"schema {schema_id!r} is unavailable"
        return [ValidationIssue("error", document.file, "$.schema", message)]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(document.data), key=lambda error: list(error.absolute_path)
    )
    return [
        ValidationIssue("error", document.file, _field_path(error.absolute_path), error.message)
        for error in errors
    ]


def _load_engine(root: Traversable) -> tuple[JsonObject, list[ValidationIssue]]:
    """Load and validate the machine lock while retaining its incomplete-asset warning.

    The checker is imported here because it reads the issue model from this module; a module-scope
    import would close that cycle.
    """
    from bora_workbench._validation_engine import validate_engine_lock

    document, issues = _read_object(root.joinpath("engine.lock"), "engine.lock")
    if document is None:
        return {}, issues
    issues.extend(validate_engine_lock(document.data))
    if document.data.get("assets_complete") is not True:
        message = "engine assets are incomplete; managed installation is unavailable"
        issues.append(ValidationIssue("warning", "engine.lock", "$.assets_complete", message))
    return document.data, issues


def _semantic_issues(documents: tuple[Document, ...], engine: JsonObject) -> list[ValidationIssue]:
    """Apply every cross-document check to the already schema-valid documents.

    The checkers read the issue model from this module, so they are imported here instead of at
    module scope to keep that dependency acyclic.
    """
    from bora_workbench._validation_calibration import validate_calibration_content
    from bora_workbench._validation_calibration_v3 import validate_v3_contracts
    from bora_workbench._validation_profiles import (
        collect_mode_ids,
        validate_modes,
        validate_profiles,
    )

    mode_ids = collect_mode_ids(documents)
    issues = validate_modes(documents)
    issues.extend(validate_calibration_content(documents, mode_ids))
    issues.extend(validate_v3_contracts(documents, mode_ids, engine))
    issues.extend(validate_profiles(documents, mode_ids, engine))
    return issues


def validate_resources(root: Traversable | None = None) -> ValidationResult:
    """Validate installed resources without network, filesystem writes, or runtime assumptions."""
    selected_root = resource_root() if root is None else root
    schemas, issues = _load_schemas(selected_root)
    engine, engine_issues = _load_engine(selected_root)
    issues.extend(engine_issues)
    valid_documents: list[Document] = []
    files = _content_files(selected_root)
    if not any(label.startswith("content/modes/") for _, label in files):
        message = "at least one mode is required"
        issues.append(ValidationIssue("error", "content/modes", "$", message))
    for file, label in files:
        document, read_issues = _read_object(file, label)
        issues.extend(read_issues)
        if document is None:
            continue
        schema_issues = _validate_schema(document, schemas)
        issues.extend(schema_issues)
        if not schema_issues:
            valid_documents.append(document)
    issues.extend(_semantic_issues(tuple(valid_documents), engine))
    ordered = tuple(
        sorted(
            issues, key=lambda value: (value.file, value.field_path, value.severity, value.message)
        )
    )
    return ValidationResult(ordered)
