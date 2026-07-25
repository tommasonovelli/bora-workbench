"""Bind public calibration/v3 policy references to exact report evidence."""

from __future__ import annotations

import hashlib
from typing import cast

from bora_workbench.validation import Document, JsonObject, ValidationIssue

_IDENTITY_FIELDS = (
    "model",
    "model_sha256",
    "engine_release",
    "engine_source_commit",
    "command_contract_sha256",
)


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create one policy-to-report link error."""
    return ValidationIssue("error", document.file, path, message)


def _scope_issues(policy: Document, report: Document, reference_id: str) -> list[ValidationIssue]:
    """Require D-047 measured scope to reproduce the linked report hardware exactly."""
    coverage = cast(JsonObject, policy.data["empirical_coverage"])
    scopes = cast(list[JsonObject], coverage["measured_scope"])
    scope = next((item for item in scopes if item["evidence_id"] == reference_id), None)
    if scope is None:
        path = "$.empirical_coverage.measured_scope"
        return [_error(policy, path, "missing evidence scope")]
    hardware = cast(JsonObject, report.data["hardware"])
    fields = ("os_name", "os_version", "backend", "gpu_name", "vram_total_gib", "ram_total_gib")
    if any(scope[field] != hardware[field] for field in fields):
        path = "$.empirical_coverage.measured_scope"
        return [_error(policy, path, "differs from report hardware")]
    return []


def _identity_issues(policy: Document, report: Document) -> list[ValidationIssue]:
    """Require one report to copy exact model and engine policy identity."""
    issues = []
    if report.data["policy_id"] != policy.data["id"]:
        issues.append(_error(report, "$.policy_id", "differs from referenced policy"))
    for field in _IDENTITY_FIELDS:
        if report.data[field] != policy.data[field]:
            issues.append(_error(report, f"$.{field}", "differs from referenced policy"))
    return issues


def _domain_issue(policy: Document, report: Document) -> ValidationIssue | None:
    """Require reference evidence to use the policy's metadata-reviewed upper bound."""
    backends = cast(JsonObject, policy.data["backends"])
    cuda = cast(JsonObject, backends["cuda"])
    policy_axis = cast(JsonObject, cuda["axis"])
    report_search = cast(JsonObject, report.data["search"])
    report_domain = cast(JsonObject, report_search["n_cpu_moe_domain"])
    if report_domain["maximum"] == policy_axis["expected_maximum"]:
        return None
    path = "$.search.n_cpu_moe_domain.maximum"
    return _error(report, path, "differs from policy")


def _reference_issues(
    policy: Document, report: Document, reference: JsonObject
) -> list[ValidationIssue]:
    """Check one exact report path, digest, identity, domain, and measured scope."""
    report_id = cast(str, reference["id"])
    issues: list[ValidationIssue] = []
    if reference["path"] != f"calibrations/{report_id}.json":
        issues.append(_error(policy, "$.evidence", "report path does not match its id"))
    if reference["sha256"] != hashlib.sha256(report.raw_bytes).hexdigest():
        issues.append(_error(policy, "$.evidence", "report digest does not match exact bytes"))
    issues.extend(_identity_issues(policy, report))
    domain_issue = _domain_issue(policy, report)
    if domain_issue is not None:
        issues.append(domain_issue)
    issues.extend(_scope_issues(policy, report, report_id))
    return issues


def validate_v3_links(policy: Document, reports: dict[str, Document]) -> list[ValidationIssue]:
    """Bind all policy evidence references to present, byte-exact reports."""
    issues: list[ValidationIssue] = []
    for reference in cast(list[JsonObject], policy.data["evidence"]):
        report_id = cast(str, reference["id"])
        report = reports.get(report_id)
        if report is None:
            issues.append(_error(policy, "$.evidence", f"missing report {report_id!r}"))
        else:
            issues.extend(_reference_issues(policy, report, reference))
    return issues
