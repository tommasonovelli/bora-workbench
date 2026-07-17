"""Cross-document tests for profile, report, engine, and overlap semantics."""

from __future__ import annotations

from qwen_launcher.profiles import load_catalog
from qwen_launcher.validation import validate_resources
from tests.content_fixtures import (
    build_valid_content,
    read_json,
    refresh_profile_digest,
    write_json,
)


def test_partial_profile_with_accepted_report_is_valid(tmp_path) -> None:
    """Allow a profile to cover coding without requiring studio or vstudio."""
    files = build_valid_content(tmp_path)

    result = validate_resources(files.root)

    assert result.errors == ()


def test_profile_report_digest_mismatch_is_error(tmp_path) -> None:
    """Bind a profile to the exact UTF-8 bytes of its accepted report."""
    files = build_valid_content(tmp_path)
    files.report.write_bytes(files.report.read_bytes() + b"\n")

    result = validate_resources(files.root)

    assert any(issue.field_path == "$.calibration_report_sha256" for issue in result.errors)


def test_missing_report_is_error(tmp_path) -> None:
    """Reject a profile whose report is absent from packaged calibrations."""
    files = build_valid_content(tmp_path)
    files.report.unlink()

    result = validate_resources(files.root)

    assert any("referenced report is missing" in issue.message for issue in result.errors)


def test_selected_candidate_must_exist_and_match_envelope(tmp_path) -> None:
    """Reject both an invalid selection and profile parameters not supported by evidence."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["modes"]["coding"]["selected_candidate_id"] = "missing"  # type: ignore[index]
    write_json(files.report, report)
    refresh_profile_digest(files)
    profile = read_json(files.profile)
    profile["modes"]["coding"]["ctx"] = 16384  # type: ignore[index]
    write_json(files.profile, profile)

    result = validate_resources(files.root)

    messages = {issue.message for issue in result.errors}
    assert "must reference a valid candidate" in messages
    assert "missing selected candidate in report" in messages


def test_profile_model_and_hardware_must_match_report(tmp_path) -> None:
    """Reject identity and hardware classes that diverge from measured evidence."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["engine"] = "b9999"
    write_json(files.report, report)
    refresh_profile_digest(files)
    profile = read_json(files.profile)
    profile["model"] = "other/model:file"
    profile["match"]["ram_gib"] = [64, 64]  # type: ignore[index]
    write_json(files.profile, profile)

    result = validate_resources(files.root)

    paths = {issue.field_path for issue in result.errors}
    assert "$.model" in paths
    assert "$.engine" in paths
    assert "$.match.ram_gib" in paths


def test_profile_must_copy_policy_class_and_measured_os_exactly(tmp_path) -> None:
    """Prevent profile windows from being widened beyond their accepted evidence provenance."""
    files = build_valid_content(tmp_path)
    profile = read_json(files.profile)
    profile["match"]["vram_gib"] = [6, 10]  # type: ignore[index]
    profile["match"]["os"] = ["linux", "windows"]  # type: ignore[index]
    write_json(files.profile, profile)

    result = validate_resources(files.root)

    messages = {issue.message for issue in result.errors}
    assert "differs from the report's approved policy class" in messages
    assert "must contain only the operating system measured by the report" in messages


def test_unaccepted_report_cannot_calibrate_profile(tmp_path) -> None:
    """Reject a reviewed report until its decision and mode selection are accepted."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["decision"] = "rejected"
    report["modes"]["coding"]["selected_candidate_id"] = None  # type: ignore[index]
    write_json(files.report, report)
    refresh_profile_digest(files)

    result = validate_resources(files.root)

    assert any(issue.message == "report is not accepted" for issue in result.errors)


def test_engine_divergence_is_warning_and_runtime_flag(tmp_path) -> None:
    """Keep a structurally valid old-engine profile but mark it uncalibrated at runtime."""
    files = build_valid_content(tmp_path, engine="b9999")

    result = validate_resources(files.root)
    catalog = load_catalog(files.root)

    assert result.errors == ()
    assert any(issue.field_path == "$.engine" for issue in result.warnings)
    assert catalog.profiles[0].is_engine_compatible is False


def test_profile_ranges_and_token_summary_are_semantically_ordered(tmp_path) -> None:
    """Reject inverted ranges and min/median/max values not expressible in JSON Schema."""
    files = build_valid_content(tmp_path)
    profile = read_json(files.profile)
    profile["match"]["ram_gib"] = [40, 30]  # type: ignore[index]
    profile["modes"]["coding"]["tok_s"] = {"min": 5, "median": 3, "max": 1}  # type: ignore[index]
    write_json(files.profile, profile)

    result = validate_resources(files.root)

    paths = {issue.field_path for issue in result.errors}
    assert "$.match.ram_gib" in paths
    assert "$.modes.coding.tok_s" in paths


def test_applicable_profile_windows_must_not_overlap(tmp_path) -> None:
    """Reject a second profile that can apply to the same OS, backend, memory, and mode."""
    files = build_valid_content(tmp_path)
    duplicate = read_json(files.profile)
    duplicate["id"] = "second-profile"
    second = files.profile.with_name("second-profile.json")
    write_json(second, duplicate)

    result = validate_resources(files.root)

    assert any("overlaps profile" in issue.message for issue in result.errors)
