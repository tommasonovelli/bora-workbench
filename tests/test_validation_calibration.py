"""Semantic tests for calibration policy and report evidence."""

from __future__ import annotations

from qwen_launcher.validation import validate_resources
from tests.content_fixtures import (
    build_valid_content,
    copy_resource_root,
    read_json,
    refresh_profile_digest,
    write_json,
)


def valid_policy(backend: str = "cuda") -> dict[str, object]:
    """Build one synthetic policy without publishing calibration content."""
    candidate: dict[str, object] = {"id": "safe", "ctx": 8192}
    policy: dict[str, object] = {
        "id": "synthetic-policy",
        "model": "owner/model:file",
        "engine": "b10011",
        "backend": backend,
        "os": ["linux"],
        "stable_start_runs": 2,
        "modes": {"coding": {"candidates": [candidate]}},
        "hardware_classes": [{"id": "class-one", "ram_gib": [31, 33], "vram_gib": [7, 9]}],
    }
    if backend == "cuda":
        candidate["n_cpu_moe"] = 48
        policy["minimum_calibration_vram_gib"] = 8
        policy["minimum_free_vram_gib"] = 0.5
        policy["vram_release_tolerance_gib"] = 0.125
    return {
        "schema": "calibration-policy/v1",
        "benchmark_protocol": "benchmark/v1",
        "gpu_poll_interval_ms": 250,
        "gpu_release_stabilization_ms": 10000,
        "policies": [policy],
    }


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
    write_json(files.root / "content/calibration-policy.json", valid_policy())
    report = read_json(files.report)
    report["policy"]["id"] = "synthetic-policy"  # type: ignore[index]
    report["hardware_class"] = "class-one"
    write_json(files.report, report)
    refresh_profile_digest(files)

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
