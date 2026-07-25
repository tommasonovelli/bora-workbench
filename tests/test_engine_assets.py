"""Tests for complete, safe, and exact engine asset selection."""

from __future__ import annotations

import pytest

import bora_workbench.engine as engine
from bora_workbench._engine_assets import select_assets
from bora_workbench._engine_types import EngineError
from bora_workbench.engine import load_engine_lock
from bora_workbench.validation import validate_resources
from tests.content_fixtures import copy_resource_root, read_json, write_json


@pytest.mark.parametrize(
    ("os_name", "backend", "roles"),
    [
        ("ubuntu", "cpu", {"server"}),
        ("ubuntu", "cuda", {"source"}),
        ("windows", "cpu", {"server"}),
        ("windows", "cuda", {"server", "cuda-runtime"}),
    ],
)
def test_selects_exact_verified_asset_matrix(os_name, backend, roles) -> None:
    """Select only the roles verified by Spike 0 for each supported target pair."""
    selected = select_assets(load_engine_lock(), os_name, backend)

    assert {asset.role for asset in selected} == roles
    assert all(asset.url.startswith("https://") for asset in selected)


def test_runtime_refuses_incomplete_or_missing_asset_sets() -> None:
    """Prevent managed installation when completeness or a target role is absent."""
    lock = load_engine_lock()
    lock["assets_complete"] = False
    with pytest.raises(EngineError, match="incomplete"):
        select_assets(lock, "ubuntu", "cpu")

    lock = load_engine_lock()
    lock["assets"] = [item for item in lock["assets"] if item["role"] != "cuda-runtime"]
    with pytest.raises(EngineError, match="exact windows/cuda"):
        select_assets(lock, "windows", "cuda")


def test_platform_selection_rejects_unsupported_architecture_and_linux(monkeypatch) -> None:
    """Never apply x86-64 Ubuntu assets to another architecture or Linux distribution."""
    monkeypatch.setattr(engine.platform, "machine", lambda: "aarch64")
    with pytest.raises(EngineError, match="requires x86-64"):
        engine._platform_key()

    monkeypatch.setattr(engine.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(engine.platform, "system", lambda: "Linux")
    monkeypatch.setattr(engine.platform, "freedesktop_os_release", lambda: {"ID": "debian"})
    with pytest.raises(EngineError, match="requires Ubuntu"):
        engine._platform_key()


def test_validation_rejects_unsafe_asset_metadata(tmp_path) -> None:
    """Reject non-HTTPS downloads, malformed digests, and executable traversal."""
    root = copy_resource_root(tmp_path)
    path = root / "engine.lock"
    lock = read_json(path)
    asset = lock["assets"][0]
    asset["url"] = "http://example.invalid/engine.tar.gz"
    asset["sha256"] = "invalid"
    asset["executable"] = "../llama-server"
    write_json(path, lock)

    result = validate_resources(root)
    paths = {issue.field_path for issue in result.errors}

    assert "$.assets[0].url" in paths
    assert "$.assets[0].sha256" in paths
    assert "$.assets[0].executable" in paths


def test_validation_binds_source_url_and_complete_role_matrix(tmp_path) -> None:
    """Require the pinned source commit and every exact supported role set."""
    root = copy_resource_root(tmp_path)
    path = root / "engine.lock"
    lock = read_json(path)
    source = next(item for item in lock["assets"] if item["role"] == "source")
    source["url"] = "https://example.invalid/source.tar.gz"
    lock["assets"] = [item for item in lock["assets"] if item["role"] != "cuda-runtime"]
    write_json(path, lock)

    result = validate_resources(root)
    messages = {issue.message for issue in result.errors}

    assert "source URL must contain the pinned source_commit" in messages
    assert any("windows/cuda" in message for message in messages)
