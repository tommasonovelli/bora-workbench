"""Tests for immutable promotion and atomic managed-engine activation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import qwen_launcher._engine_install as installer
import qwen_launcher.engine as engine
from qwen_launcher._engine_types import Backend, EngineAsset, EngineError, InstallRequest


def server_asset(backend: str = "cpu") -> EngineAsset:
    """Build a synthetic prebuilt server selected by offline orchestration tests."""
    return EngineAsset(
        "windows",
        cast(Backend, backend),
        "server",
        "engine.zip",
        "https://example.invalid/engine.zip",
        "0" * 64,
        "zip",
        "llama-server.exe",
    )


def request(tmp_path: Path, backend: str = "cpu", force: bool = False) -> InstallRequest:
    """Build one isolated Windows installation request using the packaged lock."""
    notices = ("notices/llama.cpp-LICENSE",)
    if backend == "cuda":
        notices += ("notices/NVIDIA-CUDA-EULA.html",)
    return InstallRequest(
        "windows",
        cast(Backend, backend),
        force,
        tmp_path / "engine",
        tmp_path / "cache",
        engine.load_engine_lock(),
        notices,
        False,
    )


def patch_artifacts(monkeypatch) -> None:
    """Replace network and extraction while preserving promotion and manifest behavior."""
    monkeypatch.setattr(
        installer,
        "select_assets",
        lambda lock, platform_key, backend: (server_asset(backend),),
    )
    monkeypatch.setattr(installer, "download_asset", lambda asset, root: root / asset.filename)

    def extract(asset, archive, destination):
        """Materialize the synthetic server instead of opening a real archive."""
        del archive
        path = destination / str(asset.executable)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"server")

    monkeypatch.setattr(installer, "extract_asset", extract)
    monkeypatch.setattr(engine, "verify_engine", lambda executable, lock: executable.resolve())


def manifest_bytes(root: Path) -> bytes:
    """Read the exact current manifest bytes for atomicity assertions."""
    return (root / "engine/current.json").read_bytes()


def test_ubuntu_verification_requests_executable_mode(tmp_path, monkeypatch) -> None:
    """Apply the Ubuntu executable bit without asserting POSIX mode behavior on Windows hosts."""
    executable = tmp_path / "llama-server"
    executable.write_bytes(b"server")
    selected = replace(request(tmp_path), platform_key="ubuntu", set_executable_mode=True)
    observed_modes: list[int] = []

    def capture_mode(path, mode):
        """Record the requested mode independently of host chmod semantics."""
        del path
        observed_modes.append(mode)

    monkeypatch.setattr(Path, "chmod", capture_mode)
    monkeypatch.setattr(engine, "verify_engine", lambda path, lock: path.resolve())

    installer._verify_staged(executable, selected)

    assert observed_modes[0] & 0o100


def test_install_no_op_force_and_backend_change(tmp_path, monkeypatch) -> None:
    """No-op an identical target but promote new immutable directories for force and backend."""
    patch_artifacts(monkeypatch)

    first = installer.install_engine(request(tmp_path))
    second = installer.install_engine(request(tmp_path))
    forced = installer.install_engine(request(tmp_path, force=True))
    changed = installer.install_engine(request(tmp_path, backend="cuda"))

    assert first.was_installed is True
    assert second.was_installed is False
    assert forced.status.executable != first.status.executable
    assert changed.status.backend == "cuda"
    cuda_root = changed.status.executable.parent / "THIRD_PARTY_NOTICES"
    assert (cuda_root / "NVIDIA-CUDA-EULA.html").is_file()
    assert len(list((tmp_path / "engine/installations").iterdir())) == 3
    manifest = json.loads(manifest_bytes(tmp_path))
    assert manifest["schema"] == "managed-engine/v1"
    assert manifest["backend"] == "cuda"


def test_staging_failure_leaves_previous_activation_intact(tmp_path, monkeypatch) -> None:
    """Clean failed staging without changing the active installation or current manifest."""
    patch_artifacts(monkeypatch)
    installer.install_engine(request(tmp_path))
    previous = manifest_bytes(tmp_path)

    def fail_extract(asset, archive, destination):
        """Simulate an extraction failure after a prior activation exists."""
        del asset, archive, destination
        raise EngineError("synthetic extraction failure")

    monkeypatch.setattr(installer, "extract_asset", fail_extract)
    with pytest.raises(EngineError, match="synthetic extraction failure"):
        installer.install_engine(request(tmp_path, force=True))

    assert manifest_bytes(tmp_path) == previous
    assert not list((tmp_path / "engine").glob(".staging-*"))
    assert len(list((tmp_path / "engine/installations").iterdir())) == 1


def test_activation_failure_keeps_old_manifest_and_promoted_install(tmp_path, monkeypatch) -> None:
    """Keep prior activation while leaving a verified promoted directory inactive for inspection."""
    patch_artifacts(monkeypatch)
    installer.install_engine(request(tmp_path))
    previous = manifest_bytes(tmp_path)
    original_activate = installer.activate

    def fail_activation(engine_root, activation):
        """Simulate failure while replacing the activation manifest."""
        del engine_root, activation
        raise EngineError("synthetic manifest failure")

    monkeypatch.setattr(installer, "activate", fail_activation)
    with pytest.raises(EngineError, match="synthetic manifest failure"):
        installer.install_engine(request(tmp_path, force=True))
    monkeypatch.setattr(installer, "activate", original_activate)

    assert manifest_bytes(tmp_path) == previous
    assert len(list((tmp_path / "engine/installations").iterdir())) == 2


def test_corrupt_manifest_is_repaired_by_complete_install(tmp_path, monkeypatch) -> None:
    """Replace a corrupt current manifest only after a new compatible installation is promoted."""
    patch_artifacts(monkeypatch)
    root = tmp_path / "engine"
    root.mkdir()
    (root / "current.json").write_text("{broken", encoding="utf-8")

    result = installer.install_engine(request(tmp_path))

    assert result.was_installed is True
    assert json.loads((root / "current.json").read_text())["release"] == "b10011"
