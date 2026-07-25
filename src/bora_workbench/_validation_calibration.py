"""Coordinate mode, policy, and report semantic validation."""

from __future__ import annotations

from typing import cast

from bora_workbench._validation_calibration_v3 import validate_v3_contracts
from bora_workbench._validation_policy import validate_policies, validate_policy_links
from bora_workbench._validation_report import validate_reports
from bora_workbench._validation_selection import validate_report_selections
from bora_workbench.validation import Document, ValidationIssue


def _mode_issues(documents: tuple[Document, ...]) -> tuple[set[str], list[ValidationIssue]]:
    """Validate mode file identities and return the known identifier set."""
    mode_ids: set[str] = set()
    issues: list[ValidationIssue] = []
    for document in documents:
        if document.data.get("schema") != "mode/v2":
            continue
        mode_id = cast(str, document.data["id"])
        if mode_id != document.stem:
            issues.append(
                ValidationIssue("error", document.file, "$.id", "must equal the file name")
            )
        if mode_id in mode_ids:
            issues.append(
                ValidationIssue("error", document.file, "$.id", f"duplicate mode id {mode_id!r}")
            )
        mode_ids.add(mode_id)
    return mode_ids, issues


def validate_calibration(
    documents: tuple[Document, ...], engine: dict[str, object]
) -> list[ValidationIssue]:
    """Validate mode identities and all versioned calibration content semantics."""
    mode_ids, issues = _mode_issues(documents)
    issues.extend(validate_policies(documents, mode_ids))
    issues.extend(validate_reports(documents, mode_ids))
    issues.extend(validate_policy_links(documents))
    issues.extend(validate_report_selections(documents))
    issues.extend(validate_v3_contracts(documents, mode_ids, engine))
    return issues
