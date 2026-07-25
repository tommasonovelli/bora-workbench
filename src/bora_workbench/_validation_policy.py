"""Semantic checks for calibration-policy/v1 documents."""

from __future__ import annotations

from itertools import combinations
from typing import cast

from bora_workbench.validation import Document, JsonObject, ValidationIssue


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create a policy error tied to its source document."""
    return ValidationIssue("error", document.file, path, message)


def _duplicate_issues(
    document: Document, path: str, values: list[JsonObject]
) -> list[ValidationIssue]:
    """Report repeated identifiers in one semantic scope."""
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for index, value in enumerate(values):
        identifier = cast(str, value["id"])
        if identifier in seen:
            issues.append(_error(document, f"{path}[{index}].id", f"duplicate id {identifier!r}"))
        seen.add(identifier)
    return issues


def _range_issue(document: Document, path: str, values: object) -> ValidationIssue | None:
    """Reject an inclusive range whose finite maximum is below its minimum."""
    minimum, maximum = cast(list[float | None], values)
    if maximum is not None and minimum is not None and minimum > maximum:
        return _error(document, path, "minimum must not exceed maximum")
    return None


def _overlaps(left: object, right: object) -> bool:
    """Return whether two inclusive ranges share at least one value."""
    left_min, left_max = cast(list[float | None], left)
    right_min, right_max = cast(list[float | None], right)
    left_end = float("inf") if left_max is None else left_max
    right_end = float("inf") if right_max is None else right_max
    return cast(float, left_min) <= right_end and cast(float, right_min) <= left_end


def _candidate_issues(document: Document, policy_index: int) -> list[ValidationIssue]:
    """Validate mode references, unique candidates, and backend-specific fields."""
    policy = cast(JsonObject, cast(list[object], document.data["policies"])[policy_index])
    backend = cast(str, policy["backend"])
    modes = cast(JsonObject, policy["modes"])
    issues: list[ValidationIssue] = []
    for mode_id, mode_value in modes.items():
        base = f"$.policies[{policy_index}].modes.{mode_id}.candidates"
        candidates = cast(list[JsonObject], cast(JsonObject, mode_value)["candidates"])
        issues.extend(_duplicate_issues(document, base, candidates))
        for index, candidate in enumerate(candidates):
            has_value = "n_cpu_moe" in candidate
            if backend == "cuda" and not has_value:
                issues.append(_error(document, f"{base}[{index}].n_cpu_moe", "required for CUDA"))
            if backend == "cpu" and has_value:
                issues.append(_error(document, f"{base}[{index}].n_cpu_moe", "forbidden for CPU"))
    return issues


def _class_issues(document: Document, policy_index: int) -> list[ValidationIssue]:
    """Validate hardware-class IDs, ranges, and non-overlap within one policy."""
    policy = cast(JsonObject, cast(list[object], document.data["policies"])[policy_index])
    classes = cast(list[JsonObject], policy["hardware_classes"])
    base = f"$.policies[{policy_index}].hardware_classes"
    issues = _duplicate_issues(document, base, classes)
    for index, hardware_class in enumerate(classes):
        for field in ("ram_gib", "vram_gib"):
            found = _range_issue(document, f"{base}[{index}].{field}", hardware_class[field])
            if found:
                issues.append(found)
    for (_left_index, left), (right_index, right) in combinations(enumerate(classes), 2):
        if _overlaps(left["ram_gib"], right["ram_gib"]) and _overlaps(
            left["vram_gib"], right["vram_gib"]
        ):
            message = f"overlaps hardware class {cast(str, left['id'])!r}"
            issues.append(_error(document, f"{base}[{right_index}]", message))
    return issues


def _policy_issues(document: Document, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate every policy after its JSON Schema has passed."""
    policies = cast(list[JsonObject], document.data["policies"])
    issues = _duplicate_issues(document, "$.policies", policies)
    for policy_index, policy in enumerate(policies):
        modes = cast(JsonObject, policy["modes"])
        for mode_id in modes:
            if mode_id not in mode_ids:
                path = f"$.policies[{policy_index}].modes.{mode_id}"
                issues.append(_error(document, path, "references an unknown mode"))
        issues.extend(_candidate_issues(document, policy_index))
        issues.extend(_class_issues(document, policy_index))
    return issues


def validate_policies(documents: tuple[Document, ...], mode_ids: set[str]) -> list[ValidationIssue]:
    """Return semantic issues from every schema-valid calibration policy."""
    issues: list[ValidationIssue] = []
    for document in documents:
        if document.data.get("schema") == "calibration-policy/v1":
            issues.extend(_policy_issues(document, mode_ids))
    return issues


def _policy_catalog(
    documents: tuple[Document, ...],
) -> tuple[dict[str, JsonObject], tuple[int, int] | None]:
    """Index policies and retain their global polling and release-window protocol."""
    policies: dict[str, JsonObject] = {}
    protocol: tuple[int, int] | None = None
    for document in documents:
        if document.data.get("schema") != "calibration-policy/v1":
            continue
        protocol = (
            cast(int, document.data["gpu_poll_interval_ms"]),
            cast(int, document.data["gpu_release_stabilization_ms"]),
        )
        for policy in cast(list[JsonObject], document.data["policies"]):
            policies[cast(str, policy["id"])] = policy
    return policies, protocol


def _expected_candidates(policy: JsonObject, report: Document) -> list[JsonObject]:
    """Flatten policy candidates for only the modes exercised by one report."""
    report_modes = cast(JsonObject, report.data["modes"])
    expected: list[JsonObject] = []
    for mode_id, mode_value in cast(JsonObject, policy["modes"]).items():
        if mode_id not in report_modes:
            continue
        for candidate in cast(list[JsonObject], cast(JsonObject, mode_value)["candidates"]):
            expected.append({"mode": mode_id, **candidate})
    return expected


def _link_issues(
    report: Document, policies: dict[str, JsonObject], protocol: tuple[int, int] | None
) -> list[ValidationIssue]:
    """Require a named report policy snapshot to match its packaged policy exactly."""
    snapshot = cast(JsonObject, report.data["policy"])
    policy_id = cast(str | None, snapshot["id"])
    if policy_id is None:
        return []
    policy = policies.get(policy_id)
    if policy is None:
        return [_error(report, "$.policy.id", "references an unknown policy")]
    hardware = cast(JsonObject, report.data["hardware"])
    issues: list[ValidationIssue] = []
    for field in ("model", "engine"):
        if report.data[field] != policy[field]:
            issues.append(_error(report, f"$.{field}", "differs from referenced policy"))
    if hardware["backend"] != policy["backend"]:
        issues.append(_error(report, "$.hardware.backend", "differs from referenced policy"))
    if hardware["os_name"] not in cast(list[str], policy["os"]):
        issues.append(_error(report, "$.hardware.os_name", "not covered by referenced policy"))
    fields = ("stable_start_runs", "minimum_free_vram_gib", "vram_release_tolerance_gib")
    for field in fields:
        if snapshot[field] != policy.get(field):
            issues.append(_error(report, f"$.policy.{field}", "differs from referenced policy"))
    observed_protocol = (
        snapshot["gpu_poll_interval_ms"],
        snapshot["gpu_release_stabilization_ms"],
    )
    if observed_protocol != protocol:
        issues.append(_error(report, "$.policy", "GPU protocol differs from policy catalog"))
    if snapshot["candidates"] != _expected_candidates(policy, report):
        issues.append(_error(report, "$.policy.candidates", "differs from referenced policy"))
    classes = {item["id"] for item in cast(list[JsonObject], policy["hardware_classes"])}
    if report.data["hardware_class"] not in classes:
        issues.append(_error(report, "$.hardware_class", "not present in referenced policy"))
    return issues


def validate_policy_links(documents: tuple[Document, ...]) -> list[ValidationIssue]:
    """Validate every non-null report policy reference against packaged policy content."""
    policies, protocol = _policy_catalog(documents)
    issues: list[ValidationIssue] = []
    for document in documents:
        if document.data.get("schema") == "calibration-report/v1":
            issues.extend(_link_issues(document, policies, protocol))
    return issues
