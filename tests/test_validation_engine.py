"""Tests for the pinned model artifact and engine command vocabulary."""

from __future__ import annotations

from bora_workbench.validation import validate_resources
from tests.content_fixtures import copy_resource_root, read_json, write_json


def _engine_path(tmp_path):
    """Return a copied engine lock that tests may mutate safely."""
    root = copy_resource_root(tmp_path)
    return root, root / "engine.lock"


def test_engine_lock_pins_verified_model_artifacts(tmp_path) -> None:
    """Keep model identity, revision, filenames, sizes, and digests machine-readable."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    artifact = lock["default_model_artifact"]

    result = validate_resources(root)

    assert result.errors == ()
    assert artifact["revision"] == "5bc3e238d916f48a861bac2f8a1990a0e9b7e98d"
    assert artifact["sha256"] == "0b21525e972670ed59e1812e170b27c26355381f0656ecc4e25617ece7dac58b"
    assert artifact["mmproj"]["sha256"] == (
        "da63cb47a76763c712393f8a017070188a304fa39f8aeea6edc629ed7b975cfa"
    )


def test_engine_lock_requires_model_repository_identity_match(tmp_path) -> None:
    """Reject an artifact block that points away from the declared default model."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    lock["default_model_artifact"]["repository"] = "other/model"
    write_json(path, lock)

    result = validate_resources(root)

    assert any(issue.field_path.endswith("repository") for issue in result.errors)


def test_engine_lock_rejects_invalid_artifact_fields(tmp_path) -> None:
    """Reject unsafe filenames, impossible sizes, and malformed digests."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    artifact = lock["default_model_artifact"]
    artifact["filename"] = "../model.gguf"
    artifact["size_bytes"] = 0
    artifact["mmproj"]["sha256"] = "invalid"
    write_json(path, lock)

    result = validate_resources(root)
    paths = {issue.field_path for issue in result.errors}

    assert "$.default_model_artifact.filename" in paths
    assert "$.default_model_artifact.size_bytes" in paths
    assert "$.default_model_artifact.mmproj.sha256" in paths


def test_engine_lock_requires_model_path_placeholder(tmp_path) -> None:
    """Prevent the declarative model identity from reaching the path-only -m flag."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    lock["command_contract"]["model_args"][1] = "{model}"
    write_json(path, lock)

    result = validate_resources(root)

    assert any("model_path" in issue.message for issue in result.errors)
    assert any("unknown placeholder 'model'" in issue.message for issue in result.errors)


def test_engine_lock_rejects_unknown_placeholder(tmp_path) -> None:
    """Refuse template values that the command builder cannot expand safely."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    lock["command_contract"]["context_args"][1] = "{guessed_value}"
    write_json(path, lock)

    result = validate_resources(root)

    assert any("unknown placeholder 'guessed_value'" in issue.message for issue in result.errors)


def test_engine_lock_rejects_unverified_command_flag(tmp_path) -> None:
    """Require every emitted option token to be present in verified_flags."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    lock["command_contract"]["fixed_args"].append("--invented")
    write_json(path, lock)

    result = validate_resources(root)

    assert any("--invented" in issue.message for issue in result.errors)


def test_engine_lock_rejects_non_string_argument_token(tmp_path) -> None:
    """Prevent runtime expansion of malformed declarative argument arrays."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    lock["command_contract"]["fixed_args"].append(1)
    lock["version_contract"]["args"].append(False)
    write_json(path, lock)

    result = validate_resources(root)

    assert any("argument arrays" in issue.message for issue in result.errors)
    assert any(issue.field_path == "$.version_contract.args" for issue in result.errors)


def test_engine_lock_rejects_duplicate_verified_flags(tmp_path) -> None:
    """Keep the verified option vocabulary canonical and deterministic."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    lock["verified_flags"].append(lock["verified_flags"][0])
    write_json(path, lock)

    result = validate_resources(root)

    assert any("duplicates" in issue.message for issue in result.errors)


def test_engine_lock_schema_rejects_missing_and_unknown_fields(tmp_path) -> None:
    """Require the complete closed lock shape before semantic validation."""
    root, path = _engine_path(tmp_path)
    lock = read_json(path)
    del lock["health_contract"]
    lock["invented"] = True
    write_json(path, lock)

    result = validate_resources(root)
    messages = {issue.message for issue in result.errors if issue.file == "engine.lock"}

    assert any("'health_contract' is a required property" in message for message in messages)
    assert any("Additional properties are not allowed" in message for message in messages)
