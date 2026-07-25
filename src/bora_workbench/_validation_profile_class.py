"""Require packaged profile ranges to reproduce their approved report policy class."""

from __future__ import annotations

from typing import cast

from bora_workbench.validation import Document, JsonObject, ValidationIssue


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create one profile-to-policy consistency error."""
    return ValidationIssue("error", document.file, path, message)


def _documents_by_id(documents: tuple[Document, ...], schema: str) -> dict[str, Document]:
    """Index schema-valid documents carrying a top-level identifier."""
    return {
        cast(str, document.data["id"]): document
        for document in documents
        if document.data.get("schema") == schema
    }


def _policies_by_id(documents: tuple[Document, ...]) -> dict[str, JsonObject]:
    """Index nested policy objects from every schema-valid catalog."""
    policies: dict[str, JsonObject] = {}
    for document in documents:
        if document.data.get("schema") != "calibration-policy/v1":
            continue
        for policy in cast(list[JsonObject], document.data["policies"]):
            policies[cast(str, policy["id"])] = policy
    return policies


def _profile_issues(
    profile: Document, report: Document, policy: JsonObject
) -> list[ValidationIssue]:
    """Compare one profile match object with its named class and measured operating system."""
    class_id = report.data["hardware_class"]
    classes = cast(list[JsonObject], policy["hardware_classes"])
    hardware_class = next((item for item in classes if item["id"] == class_id), None)
    if hardware_class is None:
        return []
    match = cast(JsonObject, profile.data["match"])
    issues: list[ValidationIssue] = []
    for field in ("ram_gib", "vram_gib"):
        if match[field] != hardware_class[field]:
            message = "differs from the report's approved policy class"
            issues.append(_error(profile, f"$.match.{field}", message))
    hardware = cast(JsonObject, report.data["hardware"])
    if match.get("os") != [hardware["os_name"]]:
        message = "must contain only the operating system measured by the report"
        issues.append(_error(profile, "$.match.os", message))
    return issues


def validate_profile_classes(documents: tuple[Document, ...]) -> list[ValidationIssue]:
    """Validate class provenance without violating D-034's local-performance boundary."""
    reports = _documents_by_id(documents, "calibration-report/v1")
    policies = _policies_by_id(documents)
    issues: list[ValidationIssue] = []
    for profile in documents:
        if profile.data.get("schema") != "profile/v1":
            continue
        report = reports.get(cast(str, profile.data["calibration_report"]))
        if report is None:
            continue
        policy_id = cast(JsonObject, report.data["policy"])["id"]
        policy = policies.get(cast(str, policy_id)) if policy_id is not None else None
        if policy is not None:
            issues.extend(_profile_issues(profile, report, policy))
    return issues
