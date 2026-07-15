"""Coordinate mode, policy, and report semantic validation."""

from __future__ import annotations

from typing import cast

from qwen_launcher._validation_policy import validate_policies, validate_policy_links
from qwen_launcher._validation_report import validate_reports
from qwen_launcher.validation import Document, ValidationIssue


def _mode_issues(documents: tuple[Document, ...]) -> tuple[set[str], list[ValidationIssue]]:
    """Validate mode file identities and return the known identifier set."""
    mode_ids: set[str] = set()
    issues: list[ValidationIssue] = []
    for document in documents:
        if document.data.get("schema") != "mode/v1":
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


def validate_calibration(documents: tuple[Document, ...]) -> list[ValidationIssue]:
    """Validate mode identities and calibration policy/report semantics."""
    mode_ids, issues = _mode_issues(documents)
    issues.extend(validate_policies(documents, mode_ids))
    issues.extend(validate_reports(documents, mode_ids))
    issues.extend(validate_policy_links(documents))
    return issues
