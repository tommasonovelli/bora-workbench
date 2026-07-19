"""Contract tests for public calibration/v3 policy and reference evidence."""

from __future__ import annotations

import hashlib

from qwen_launcher.validation import validate_resources
from tests.content_fixtures import read_json, write_json
from tests.v3_content_fixtures import build_v3_content


def _refresh_digest(files) -> None:
    """Rebind a synthetic policy after an intentional report mutation."""
    policy = read_json(files.policy)
    policy["evidence"][0]["sha256"] = hashlib.sha256(files.report.read_bytes()).hexdigest()  # type: ignore[index]
    write_json(files.policy, policy)


def test_linked_v3_policy_and_reference_report_are_valid(tmp_path) -> None:
    """Accept the public method and privacy-safe evidence without a profile/v1 envelope."""
    files = build_v3_content(tmp_path)

    result = validate_resources(files.root)

    assert result.errors == ()
    assert not (files.root / "content/profiles").exists()


def test_policy_identity_and_metadata_domain_must_match_the_lock(tmp_path) -> None:
    """Reject a remote model identity or a domain maximum not derived from the pinned GGUF."""
    files = build_v3_content(tmp_path)
    policy = read_json(files.policy)
    policy["model_sha256"] = "f" * 64
    policy["backends"]["cuda"]["axis"]["expected_maximum"] = 40  # type: ignore[index]
    write_json(files.policy, policy)

    result = validate_resources(files.root)

    paths = {issue.field_path for issue in result.errors}
    assert "$.model_sha256" in paths
    assert "$.backends.cuda.axis.expected_maximum" in paths


def test_policy_binds_exact_report_path_digest_and_scope(tmp_path) -> None:
    """Reject tampered evidence bytes and a measured scope widened away from its report."""
    files = build_v3_content(tmp_path)
    report = read_json(files.report)
    report["hardware"]["ram_total_gib"] = 64  # type: ignore[index]
    write_json(files.report, report)

    result = validate_resources(files.root)
    messages = {issue.message for issue in result.errors}

    assert "report digest does not match exact bytes" in messages
    assert "differs from report hardware" in messages


def test_report_seed_must_remain_a_valid_in_domain_local_observation(tmp_path) -> None:
    """Reject a seed detached from the selected finalist or outside the complete domain."""
    files = build_v3_content(tmp_path)
    report = read_json(files.report)
    mode = report["modes"]["coding"]  # type: ignore[index]
    mode["seed_n_cpu_moe"] = 40
    mode["probe_sequence"][0]["n_cpu_moe"] = 42
    write_json(files.report, report)
    _refresh_digest(files)

    result = validate_resources(files.root)
    messages = {issue.message for issue in result.errors}

    assert "must match local evidence" in messages
    assert "must be unique and in domain" in messages


def test_report_reconstructs_published_unanimous_dominance(tmp_path) -> None:
    """Reject a selected seed whose published medians no longer win both paired rounds."""
    files = build_v3_content(tmp_path)
    report = read_json(files.report)
    selected = report["modes"]["coding"]["finalists"][0]  # type: ignore[index]
    selected["round_medians_tok_s"] = [18, 21]
    write_json(files.report, report)
    _refresh_digest(files)

    result = validate_resources(files.root)

    assert any("do not show unanimous dominance" in issue.message for issue in result.errors)


def test_report_rejects_private_paths_and_non_utc_timestamps(tmp_path) -> None:
    """Scan schema-valid free text for private paths and require an explicit UTC timestamp."""
    files = build_v3_content(tmp_path)
    report = read_json(files.report)
    report["created_at"] = "2026-07-19T14:00:00+02:00"
    report["hardware"]["os_version"] = r"Windows from C:\Users\alice\private"  # type: ignore[index]
    write_json(files.report, report)
    _refresh_digest(files)

    result = validate_resources(files.root)
    messages = {issue.message for issue in result.errors}

    assert "must be expressed in UTC" in messages
    assert "contains a private absolute path pattern" in messages


def test_unreferenced_v3_report_is_not_accepted_as_package_evidence(tmp_path) -> None:
    """Require every distributed report to be authorized by an exact public policy reference."""
    files = build_v3_content(tmp_path)
    files.policy.unlink()

    result = validate_resources(files.root)

    assert any(issue.message == "report is not referenced by a policy" for issue in result.errors)
