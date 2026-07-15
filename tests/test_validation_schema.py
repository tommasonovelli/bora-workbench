"""Schema-boundary tests for packaged declarative content."""

from __future__ import annotations

import pytest

from qwen_launcher.validation import validate_resources
from tests.content_fixtures import build_valid_content, copy_resource_root, read_json, write_json


def test_installed_content_has_only_expected_engine_warning() -> None:
    """Accept production modes and the intentionally incomplete Step 4 asset lock."""
    result = validate_resources()

    assert result.errors == ()
    assert len(result.warnings) == 1
    assert result.warnings[0].field_path == "$.assets_complete"


def test_malformed_json_reports_file_path_and_reason(tmp_path) -> None:
    """Turn malformed UTF-8 JSON into an actionable issue instead of a traceback."""
    root = copy_resource_root(tmp_path)
    path = root / "content/modes/coding.json"
    path.write_text('{"schema": ', encoding="utf-8")

    result = validate_resources(root)

    issue = next(item for item in result.errors if item.file.endswith("coding.json"))
    assert issue.field_path == "$"
    assert "invalid UTF-8 JSON" in issue.message


@pytest.mark.parametrize(
    ("case", "expected_path"),
    [
        ("missing", "$"),
        ("unknown", "$"),
        ("wrong-type", "$.services.ui"),
        ("boundary", "$.sampling.top_p"),
        ("unknown-schema", "$.schema"),
    ],
)
def test_mode_schema_error_classes_are_reported(tmp_path, case, expected_path) -> None:
    """Cover required, additional, type, boundary, and schema-dispatch failures."""
    root = copy_resource_root(tmp_path)
    path = root / "content/modes/coding.json"
    mode = read_json(path)
    if case == "missing":
        del mode["description"]
    elif case == "unknown":
        mode["unexpected"] = True
    elif case == "wrong-type":
        mode["services"]["ui"] = "false"  # type: ignore[index]
    elif case == "boundary":
        mode["sampling"]["top_p"] = 0  # type: ignore[index]
    else:
        mode["schema"] = "mode/v99"
    write_json(path, mode)

    result = validate_resources(root)

    assert any(issue.field_path == expected_path for issue in result.errors)


def test_report_conditional_rejects_five_measurements_when_discarded(tmp_path) -> None:
    """Prevent a discarded candidate from carrying a complete benchmark summary."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    candidate = report["modes"]["coding"]["candidates"][0]  # type: ignore[index]
    candidate["outcome"] = "discarded"
    candidate["discard_reason"] = "simulated failure"
    candidate["tok_s"] = None
    write_json(files.report, report)

    result = validate_resources(files.root)

    assert any(issue.field_path.endswith("measured_tok_s") for issue in result.errors)


def test_validation_rejects_invalid_timestamp(tmp_path) -> None:
    """Reject malformed date-time values without leaking a parser traceback."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["created_at"] = "not-a-date"
    write_json(files.report, report)

    result = validate_resources(files.root)

    assert any(issue.field_path == "$.created_at" for issue in result.errors)
