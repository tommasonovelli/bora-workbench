"""Semantic tests for calibration policy and report evidence."""

from __future__ import annotations

from qwen_launcher.validation import validate_resources
from tests.calibration_fixtures import valid_policy
from tests.content_fixtures import (
    build_valid_content,
    copy_resource_root,
    read_json,
    refresh_profile_digest,
    write_json,
)


def test_valid_cpu_report_and_profile_use_null_gpu_fields(tmp_path) -> None:
    """Accept CPU evidence only when CUDA parameters and GPU measurements are absent."""
    files = build_valid_content(tmp_path, backend="cpu")

    result = validate_resources(files.root)

    assert result.errors == ()


def test_policy_candidate_backend_rules(tmp_path) -> None:
    """Require n_cpu_moe on CUDA candidates and forbid it on CPU candidates."""
    for backend in ("cuda", "cpu"):
        root = copy_resource_root(tmp_path / backend)
        policy = valid_policy(backend)
        candidate = policy["policies"][0]["modes"]["coding"]["candidates"][0]  # type: ignore[index]
        if backend == "cuda":
            del candidate["n_cpu_moe"]
        else:
            candidate["n_cpu_moe"] = 48
        write_json(root / "content/calibration-policy.json", policy)

        result = validate_resources(root)

        assert any(issue.field_path.endswith("n_cpu_moe") for issue in result.errors)


def test_policy_ids_ranges_and_classes_are_semantic(tmp_path) -> None:
    """Reject duplicate candidates, inverted ranges, and overlapping hardware classes."""
    root = copy_resource_root(tmp_path)
    policy = valid_policy()
    body = policy["policies"][0]  # type: ignore[index]
    candidate = body["modes"]["coding"]["candidates"][0]  # type: ignore[index]
    body["modes"]["coding"]["candidates"].append(candidate.copy())  # type: ignore[index]
    body["hardware_classes"].append(  # type: ignore[index]
        {"id": "class-one", "ram_gib": [32, 40], "vram_gib": [8, 12]}
    )
    body["hardware_classes"].append(  # type: ignore[index]
        {"id": "class-invalid", "ram_gib": [50, 40], "vram_gib": [20, 20]}
    )
    write_json(root / "content/calibration-policy.json", policy)

    result = validate_resources(root)

    messages = {issue.message for issue in result.errors}
    assert any("duplicate id" in message for message in messages)
    assert "minimum must not exceed maximum" in messages
    assert any("overlaps hardware class" in message for message in messages)


def test_policy_and_report_reject_unknown_modes(tmp_path) -> None:
    """Require all contributed mode references to resolve to packaged modes."""
    root = copy_resource_root(tmp_path)
    policy = valid_policy()
    body = policy["policies"][0]  # type: ignore[index]
    body["modes"]["unknown-mode"] = body["modes"].pop("coding")  # type: ignore[index]
    write_json(root / "content/calibration-policy.json", policy)

    result = validate_resources(root)

    assert any("unknown mode" in issue.message for issue in result.errors)


def test_named_report_policy_must_resolve_and_match(tmp_path) -> None:
    """Validate a non-null report policy reference and reject an unknown replacement."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)

    assert validate_resources(files.root).errors == ()

    report["policy"]["id"] = "missing-policy"  # type: ignore[index]
    write_json(files.report, report)
    refresh_profile_digest(files)
    result = validate_resources(files.root)
    assert any(issue.message == "references an unknown policy" for issue in result.errors)


def test_report_summary_and_stable_runs_must_match_evidence(tmp_path) -> None:
    """Recompute benchmark summaries and enforce the policy stable-start count."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    candidate = report["modes"]["coding"]["candidates"][0]  # type: ignore[index]
    candidate["tok_s"]["median"] = 99
    candidate["successful_start_runs"] = 1
    write_json(files.report, report)
    refresh_profile_digest(files)

    result = validate_resources(files.root)

    paths = {issue.field_path for issue in result.errors}
    assert any(path.endswith("successful_start_runs") for path in paths)
    assert any(path.endswith("tok_s.median") for path in paths)


def test_report_candidate_order_must_match_policy_snapshot(tmp_path) -> None:
    """Prevent report results from silently diverging from the declared candidate order."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["policy"]["candidates"][0]["id"] = "different"  # type: ignore[index]
    write_json(files.report, report)
    refresh_profile_digest(files)

    result = validate_resources(files.root)

    assert any("order differs" in issue.message for issue in result.errors)


def test_accepted_report_requires_policy_and_deterministic_winner(tmp_path) -> None:
    """Reject ungoverned acceptance and a valid candidate that loses the declared selection rule."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["policy"]["id"] = None  # type: ignore[index]
    write_json(files.report, report)
    refresh_profile_digest(files)
    result = validate_resources(files.root)
    assert any("approved policy" in issue.message for issue in result.errors)

    report["policy"]["id"] = "synthetic-policy"  # type: ignore[index]
    candidate = report["modes"]["coding"]["candidates"][0].copy()  # type: ignore[index]
    candidate.update({"id": "slower", "n_cpu_moe": 47, "measured_tok_s": [1, 1, 1, 1, 1]})
    candidate["tok_s"] = {"min": 1, "median": 1, "max": 1}
    report["modes"]["coding"]["candidates"].append(candidate)  # type: ignore[index]
    report["modes"]["coding"]["selected_candidate_id"] = "slower"  # type: ignore[index]
    snapshot = {"mode": "coding", "id": "slower", "ctx": 8192, "n_cpu_moe": 47}
    report["policy"]["candidates"].append(snapshot)  # type: ignore[index]
    policy = valid_policy()
    mode = policy["policies"][0]["modes"]["coding"]  # type: ignore[index]
    mode["candidates"].append({"id": "slower", "ctx": 8192, "n_cpu_moe": 47})
    write_json(files.root / "content/calibration-policy.json", policy)
    write_json(files.report, report)
    refresh_profile_digest(files)

    result = validate_resources(files.root)
    assert any("deterministic selection rule" in issue.message for issue in result.errors)


def test_valid_cuda_candidate_must_reproduce_resource_constraints(tmp_path) -> None:
    """Reject accepted candidate evidence below reserve or above post-stop release tolerance."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    candidate = report["modes"]["coding"]["candidates"][0]  # type: ignore[index]
    candidate["vram_min_free_gib"] = 0.25
    candidate["vram_peak_gib"] = 7.75
    candidate["vram_release_used_gib"] = 1.2
    write_json(files.report, report)
    refresh_profile_digest(files)

    result = validate_resources(files.root)
    messages = {issue.message for issue in result.errors}
    assert "violates policy reserve" in messages
    assert "exceeds release tolerance" in messages


def test_named_policy_class_must_contain_calibration_host(tmp_path) -> None:
    """Prevent a report from assigning measured hardware to an unrelated nominal class."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["hardware"]["ram_total_gib"] = 64  # type: ignore[index]
    write_json(files.report, report)
    refresh_profile_digest(files)

    result = validate_resources(files.root)
    assert any("outside the named policy class" in issue.message for issue in result.errors)


def test_report_paths_must_be_bundle_relative(tmp_path) -> None:
    """Reject traversal and absolute paths in shareable calibration evidence."""
    files = build_valid_content(tmp_path)
    report = read_json(files.report)
    report["evidence_manifest"] = "../SHA256SUMS"
    log = report["modes"]["coding"]["candidates"][0]["log_digests"][0]  # type: ignore[index]
    log["path"] = r"C:\private\server.log"
    write_json(files.report, report)
    refresh_profile_digest(files)

    result = validate_resources(files.root)

    paths = {issue.field_path for issue in result.errors}
    assert "$.evidence_manifest" in paths
    assert any(path.endswith("log_digests[0].path") for path in paths)
