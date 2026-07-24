"""Validate public calibration/v3 policy and privacy-safe reference evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from qwen_launcher._calibration_privacy import has_private_path_pattern
from qwen_launcher.validation import Document, JsonObject, ValidationIssue

_EXPECTED_BLOCK_COUNT = 41


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create one public calibration/v3 validation error."""
    return ValidationIssue("error", document.file, path, message)


def _lock_identity(engine: JsonObject) -> dict[str, object]:
    """Project stable identity while retaining historical report command digests."""
    artifact = cast(JsonObject, engine.get("default_model_artifact", {}))
    return {
        "model": engine.get("default_model"),
        "model_sha256": artifact.get("sha256"),
        "engine_release": engine.get("release"),
        "engine_source_commit": engine.get("source_commit"),
    }


def _policy_issues(
    document: Document, mode_ids: set[str], engine: JsonObject
) -> list[ValidationIssue]:
    """Require the public method to match modes, pinned identities, and model metadata."""
    issues: list[ValidationIssue] = []
    unknown = set(cast(list[str], document.data["modes"])) - mode_ids
    if unknown:
        issues.append(_error(document, "$.modes", f"references unknown modes {sorted(unknown)!r}"))
    expected = _lock_identity(engine)
    for field, value in expected.items():
        if document.data[field] != value:
            issues.append(_error(document, f"$.{field}", "differs from engine.lock"))
    backends = cast(JsonObject, document.data["backends"])
    cuda = cast(JsonObject, backends["cuda"])
    axis = cast(JsonObject, cuda["axis"])
    if axis["expected_maximum"] != _EXPECTED_BLOCK_COUNT:
        issues.append(_error(document, "$.backends.cuda.axis.expected_maximum", "must be 41"))
    references = cast(list[JsonObject], document.data["evidence"])
    ids = [cast(str, item["id"]) for item in references]
    if len(ids) != len(set(ids)):
        issues.append(_error(document, "$.evidence", "evidence ids must be unique"))
    return issues


def _strings(value: object) -> tuple[str, ...]:
    """Flatten strings from validated JSON for a host-independent privacy scan."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        return tuple(text for item in value.values() for text in _strings(item))
    if isinstance(value, list):
        return tuple(text for item in value for text in _strings(item))
    return ()


def _selection_issues(document: Document, base: str, value: JsonObject) -> list[ValidationIssue]:
    """Recheck selected finalist validity and published unanimous-round dominance."""
    seed = cast(int, value["seed_n_cpu_moe"])
    finalists = cast(list[JsonObject], value["finalists"])
    valid = [item for item in finalists if item["outcome"] == "valid"]
    if not any(item["n_cpu_moe"] == seed for item in valid):
        return [_error(document, f"{base}.finalists", "selected seed must be a valid finalist")]
    if value["selection_rule"] == "single-finalist" and len(valid) != 1:
        return [_error(document, f"{base}.selection_rule", "requires one valid finalist")]
    if value["selection_rule"] != "dominance-unanimous-rounds":
        return []
    if len(valid) != 2:
        return [_error(document, f"{base}.selection_rule", "requires two valid finalists")]
    selected = next(item for item in valid if item["n_cpu_moe"] == seed)
    other = next(item for item in valid if item is not selected)
    selected_rates = cast(list[float | None], selected["round_medians_tok_s"])
    other_rates = cast(list[float | None], other["round_medians_tok_s"])
    pairs = zip(selected_rates, other_rates, strict=True)
    dominates = all(
        left is not None and right is not None and left > right for left, right in pairs
    )
    if dominates:
        return []
    message = "round medians do not show unanimous dominance"
    return [_error(document, f"{base}.selection_rule", message)]


def _mode_issues(document: Document, mode_id: str, value: JsonObject) -> list[ValidationIssue]:
    """Check one report mode's domain, selected seed, reserves, and finalist evidence."""
    base = f"$.modes.{mode_id}"
    domain = cast(JsonObject, cast(JsonObject, document.data["search"])["n_cpu_moe_domain"])
    maximum = cast(int, domain["maximum"])
    envelope = cast(JsonObject, value["observed_local_envelope"])
    seed = cast(int, value["seed_n_cpu_moe"])
    issues: list[ValidationIssue] = []
    if seed != envelope["n_cpu_moe"]:
        issues.append(_error(document, f"{base}.seed_n_cpu_moe", "must match local evidence"))
    probes = cast(list[JsonObject], value["probe_sequence"])
    probe_values = [cast(int, item["n_cpu_moe"]) for item in probes]
    finalists = cast(list[JsonObject], value["finalists"])
    finalist_values = [cast(int, item["n_cpu_moe"]) for item in finalists]
    if any(item > maximum for item in probe_values) or len(probe_values) != len(set(probe_values)):
        issues.append(_error(document, f"{base}.probe_sequence", "must be unique and in domain"))
    if any(item > maximum for item in finalist_values) or len(finalist_values) != len(
        set(finalist_values)
    ):
        issues.append(_error(document, f"{base}.finalists", "must be unique and in domain"))
    issues.extend(_selection_issues(document, base, value))
    if float(cast(float, value["minimum_ram_available_gib"])) < 2.0:
        issues.append(_error(document, f"{base}.minimum_ram_available_gib", "violates reserve"))
    if float(cast(float, value["minimum_vram_free_gib"])) < 0.5:
        issues.append(_error(document, f"{base}.minimum_vram_free_gib", "violates reserve"))
    if float(cast(float, value["maximum_release_above_baseline_gib"])) > 0.125:
        issues.append(
            _error(document, f"{base}.maximum_release_above_baseline_gib", "exceeds tolerance")
        )
    return issues


def _report_issues(document: Document, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate report identity, UTC time, privacy, modes, and metadata-derived domain."""
    issues: list[ValidationIssue] = []
    if document.data["id"] != document.stem:
        issues.append(_error(document, "$.id", "must equal the file name"))
    timestamp = datetime.fromisoformat(
        cast(str, document.data["created_at"]).replace("Z", "+00:00")
    )
    if timestamp.utcoffset() != UTC.utcoffset(timestamp):
        issues.append(_error(document, "$.created_at", "must be expressed in UTC"))
    if any(has_private_path_pattern(text) for text in _strings(document.data)):
        issues.append(_error(document, "$", "contains a private absolute path pattern"))
    search = cast(JsonObject, document.data["search"])
    domain = cast(JsonObject, search["n_cpu_moe_domain"])
    if domain["maximum"] != _EXPECTED_BLOCK_COUNT:
        issues.append(_error(document, "$.search.n_cpu_moe_domain.maximum", "must be 41"))
    modes = cast(JsonObject, document.data["modes"])
    for mode_id, value in modes.items():
        if mode_id not in mode_ids:
            issues.append(_error(document, f"$.modes.{mode_id}", "references an unknown mode"))
        issues.extend(_mode_issues(document, mode_id, cast(JsonObject, value)))
    return issues


def validate_v3_contracts(
    documents: tuple[Document, ...], mode_ids: set[str], engine: JsonObject
) -> list[ValidationIssue]:
    """Validate every public calibration/v3 policy and report after schema validation."""
    policies = [item for item in documents if item.data.get("schema") == "calibration-policy/v2"]
    reports = {
        cast(str, item.data["id"]): item
        for item in documents
        if item.data.get("schema") == "calibration-report/v2"
    }
    issues: list[ValidationIssue] = []
    from qwen_launcher._validation_calibration_v3_links import validate_v3_links

    for policy in policies:
        issues.extend(_policy_issues(policy, mode_ids, engine))
        issues.extend(validate_v3_links(policy, reports))
    referenced = {
        cast(str, reference["id"])
        for policy in policies
        for reference in cast(list[JsonObject], policy.data["evidence"])
    }
    for report_id, report in reports.items():
        issues.extend(_report_issues(report, mode_ids))
        if report_id not in referenced:
            issues.append(_error(report, "$.policy_id", "report is not referenced by a policy"))
    return issues
