"""Tests for lock-pinned model resolution, executable probing, discovery, and activation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import bora_workbench.engine as engine
from bora_workbench.config import Config
from bora_workbench.engine import Activation, EngineError
from bora_workbench.profiles import LaunchPlan, load_catalog


def plan(tmp_path: Path, backend: str = "cpu", mode_id: str = "coding") -> LaunchPlan:
    """Build one packaged-mode launch plan without depending on host hardware."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    mmproj = tmp_path / "mmproj.gguf" if mode.services.vision else None
    return LaunchPlan(
        mode,
        "owner/model:file",
        tmp_path / "model.gguf",
        mmproj,
        8080,
        None,
        8192,
        48 if backend == "cuda" else None,
        backend,  # type: ignore[arg-type]
        0 if backend == "cuda" else None,
        (),
        "disabled" if mode.services.vision else "mtp2",
    )


def tiny_lock(data: bytes = b"model") -> engine.JsonObject:
    """Build a lock-shaped tiny artifact contract suitable for offline hashing."""
    lock = engine.load_engine_lock()
    artifact = lock["default_model_artifact"]
    assert isinstance(artifact, dict)
    artifact.update(
        {
            "repository": "owner/model",
            "revision": "a" * 40,
            "filename": "model.gguf",
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "mmproj": {
                "filename": "mmproj.gguf",
                "size_bytes": 6,
                "sha256": hashlib.sha256(b"vision").hexdigest(),
            },
        }
    )
    lock["default_model"] = "owner/model:file"
    return lock


def snapshot_path(cache: Path, lock: engine.JsonObject) -> Path:
    """Return the exact cache snapshot path encoded by a tiny test lock."""
    artifact = lock["default_model_artifact"]
    assert isinstance(artifact, dict)
    return (
        cache
        / "models--owner--model"
        / "snapshots"
        / str(artifact["revision"])
        / str(artifact["filename"])
    )


def test_resolves_exact_pinned_snapshot_without_writing(tmp_path, monkeypatch) -> None:
    """Resolve only the lock revision below b10011's highest-precedence cache root."""
    lock = tiny_lock()
    cache = tmp_path / "cache"
    model = snapshot_path(cache, lock)
    model.parent.mkdir(parents=True)
    model.write_bytes(b"model")
    monkeypatch.setenv("LLAMA_CACHE", str(cache))

    resolved = engine.resolve_model(Config(model="owner/model:file"), lock)

    assert resolved.model_path == model.resolve()
    assert resolved.mmproj_path is None
    assert not (model.parent.parent / "different").exists()


def test_resolver_rejects_absent_wrong_size_and_wrong_digest(tmp_path, monkeypatch) -> None:
    """Refuse every pinned-artifact mismatch before an engine process can start."""
    lock = tiny_lock()
    cache = tmp_path / "cache"
    model = snapshot_path(cache, lock)
    monkeypatch.setenv("LLAMA_CACHE", str(cache))
    with pytest.raises(engine.EngineError, match="absent or unreadable"):
        engine.resolve_model(Config(model="owner/model:file"), lock)

    model.parent.mkdir(parents=True)
    model.write_bytes(b"x")
    with pytest.raises(engine.EngineError, match="unexpected size"):
        engine.resolve_model(Config(model="owner/model:file"), lock)

    model.write_bytes(b"other")
    lock = tiny_lock(b"wrong")
    with pytest.raises(engine.EngineError, match="checksum"):
        engine.resolve_model(Config(model="owner/model:file"), lock)


def test_default_identity_cannot_escape_the_pinned_snapshot(tmp_path) -> None:
    """Reserve model_path for other identities instead of bypassing the pinned revision."""
    lock = tiny_lock()
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")

    with pytest.raises(engine.EngineError, match="only accepted for a non-default model"):
        engine.resolve_model(Config(model="owner/model:file", model_path=model), lock)


def test_nondefault_model_requires_only_explicit_readable_gguf(tmp_path) -> None:
    """Avoid inventing a digest for another identity while requiring a local GGUF."""
    lock = tiny_lock()
    with pytest.raises(engine.EngineError, match="requires an explicit model_path"):
        engine.resolve_model(Config(model="other/model:file"), lock)

    model = tmp_path / "custom.gguf"
    model.write_bytes(b"unlocked custom bytes")
    resolved = engine.resolve_model(Config(model="other/model:file", model_path=model), lock)

    assert resolved.model_path == model.resolve()


def test_vision_resolution_requires_pinned_mmproj(tmp_path, monkeypatch) -> None:
    """Resolve and verify mmproj only when the requested mode enables vision."""
    lock = tiny_lock()
    cache = tmp_path / "cache"
    model = snapshot_path(cache, lock)
    model.parent.mkdir(parents=True)
    model.write_bytes(b"model")
    monkeypatch.setenv("LLAMA_CACHE", str(cache))

    with pytest.raises(engine.EngineError, match="absent or unreadable"):
        engine.resolve_model(Config(model="owner/model:file"), lock, require_vision=True)

    mmproj = model.with_name("mmproj.gguf")
    mmproj.write_bytes(b"vision")
    resolved = engine.resolve_model(Config(model="owner/model:file"), lock, require_vision=True)
    assert resolved.mmproj_path == mmproj.resolve()


def test_engine_probe_requires_version_and_complete_help(tmp_path, monkeypatch) -> None:
    """Accept the exact release contract and reject a help surface missing one verified flag."""
    lock = engine.load_engine_lock()
    flags = " ".join(lock["verified_flags"])
    outputs = [
        SimpleNamespace(returncode=0, stdout="version: 10011 bf2c86ddc", stderr=""),
        SimpleNamespace(returncode=0, stdout=flags, stderr=""),
    ]
    run = Mock(side_effect=outputs)
    monkeypatch.setattr(engine.subprocess, "run", run)
    executable = tmp_path / "llama-server"

    assert engine.verify_engine(executable, lock) == executable.resolve()
    assert all("shell" not in call.kwargs for call in run.call_args_list)
    assert all(call.kwargs["timeout"] == 60 for call in run.call_args_list)

    outputs = [
        SimpleNamespace(returncode=0, stdout="version: 10011 bf2c86ddc", stderr=""),
        SimpleNamespace(returncode=0, stdout="--help", stderr=""),
    ]
    monkeypatch.setattr(engine.subprocess, "run", Mock(side_effect=outputs))
    with pytest.raises(engine.EngineError, match="missing verified flags"):
        engine.verify_engine(executable, lock)


def test_engine_probe_maps_invalid_utf8_to_engine_error(tmp_path, monkeypatch) -> None:
    """Report undecodable probe output as an expected engine failure."""
    executable = tmp_path / "llama-server"
    executable.write_bytes(b"binary")
    monkeypatch.setattr(
        engine.subprocess,
        "run",
        Mock(side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")),
    )

    with pytest.raises(EngineError, match="cannot probe engine"):
        engine.verify_engine(executable, tiny_lock())


def test_locate_prefers_explicit_then_path(tmp_path, monkeypatch) -> None:
    """Honor explicit configuration before PATH and avoid silently changing candidates."""
    explicit = tmp_path / "explicit"
    discovered = tmp_path / "path-engine"
    verify = Mock(side_effect=lambda path, lock: path)
    monkeypatch.setattr(engine, "verify_engine", verify)
    monkeypatch.setattr(engine.shutil, "which", lambda name: str(discovered))

    assert engine.locate(Config(engine_path=explicit), "cpu") == explicit
    assert engine.locate(Config(), "cpu") == discovered
    assert verify.call_args_list[0].args[0] == explicit


def test_managed_manifest_must_stay_below_installations(tmp_path, monkeypatch) -> None:
    """Reject traversal and accept a relative executable inside immutable installations."""
    data = tmp_path / "data"
    engine_root = data / "engine"
    engine_root.mkdir(parents=True)
    manifest = {"schema": "managed-engine/v1", "release": "b10011", "backend": "cpu"}
    monkeypatch.setattr(engine, "data_dir", lambda: data)
    monkeypatch.setattr(engine.shutil, "which", lambda name: None)

    for unsafe in ("../outside", r"C:\\outside\\llama-server.exe"):
        (engine_root / "current.json").write_text(
            json.dumps({**manifest, "executable": unsafe}), encoding="utf-8"
        )
        with pytest.raises(engine.EngineError, match="safe relative"):
            engine.locate(Config(), "cpu")

    relative = f"installations/b10011-cpu-{'a' * 32}/llama-server"
    (engine_root / "current.json").write_text(
        json.dumps({**manifest, "executable": relative}), encoding="utf-8"
    )
    monkeypatch.setattr(engine, "verify_engine", lambda path, lock: path)
    assert engine.locate(Config(), "cpu") == (engine_root / relative).resolve()


def test_managed_manifest_cannot_relabel_installation_backend(tmp_path) -> None:
    """Bind manifest release and backend to the immutable directory name."""
    root = tmp_path / "engine"
    directory = root / "installations" / f"b10011-cpu-{'a' * 32}"
    directory.mkdir(parents=True)
    executable = directory / "llama-server"
    executable.write_bytes(b"server")
    manifest = {
        "schema": "managed-engine/v1",
        "release": "b10011",
        "backend": "cuda",
        "executable": executable.relative_to(root).as_posix(),
    }
    (root / "current.json").write_text(json.dumps(manifest), encoding="utf-8")

    status = engine.inspect_status(root, tiny_lock())

    assert status.is_active is False
    assert "does not match release and backend" in status.differences[0]


def test_interrupted_atomic_replace_preserves_current_manifest(tmp_path, monkeypatch) -> None:
    """Flush a temporary manifest but leave current bytes intact when replacement fails."""
    root = tmp_path / "engine"
    executable = root / "installations/b10011-cpu-new/llama-server"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"server")
    current = root / "current.json"
    current.write_text('{"old": true}\n', encoding="utf-8")
    original = current.read_bytes()

    def fail_replace(path, target):
        """Simulate an operating-system failure at the atomic replacement boundary."""
        del path, target
        raise OSError("replace interrupted")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(EngineError, match="cannot activate"):
        engine.activate(root, Activation("b10011", "cpu", executable))

    assert current.read_bytes() == original
    assert not list(root.glob(".current-*.tmp"))


def test_status_keeps_active_identity_when_engine_probe_fails(tmp_path, monkeypatch) -> None:
    """Report an active manifest and exact incompatibility instead of hiding its identity."""
    root = tmp_path / "engine"
    installation = f"b10011-cpu-{'a' * 32}"
    executable = root / "installations" / installation / "llama-server"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"server")
    current = {
        "schema": "managed-engine/v1",
        "release": "b10011",
        "backend": "cpu",
        "executable": f"installations/{installation}/llama-server",
    }
    (root / "current.json").write_text(json.dumps(current), encoding="utf-8")

    def incompatible(path, lock):
        """Simulate a binary whose version differs from the machine lock."""
        del path, lock
        raise EngineError("version differs from engine.lock")

    monkeypatch.setattr(engine, "verify_engine", incompatible)
    status = engine.inspect_status(root, engine.load_engine_lock())

    assert status.is_active is True
    assert status.release == "b10011"
    assert status.is_compatible is False
    assert status.differences == ("version differs from engine.lock",)


def test_install_diagnoses_an_unreadable_lock_before_the_host_check(monkeypatch) -> None:
    """Read the packaged contract first, because a host can fail both checks at once."""
    monkeypatch.setattr(engine.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(
        engine, "load_engine_lock", Mock(side_effect=EngineError("cannot read engine.lock"))
    )

    with pytest.raises(EngineError, match=r"engine\.lock"):
        engine.install_engine("cpu")


def test_platform_selection_enforces_supported_os_versions(monkeypatch) -> None:
    """Reject Windows 10 and Ubuntu 20.04 before selecting pinned assets."""
    monkeypatch.setattr(engine.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(engine.platform, "system", lambda: "Windows")
    monkeypatch.setattr(engine.platform, "version", lambda: "10.0.19045")
    with pytest.raises(EngineError, match="Windows 11"):
        engine._platform_key()

    monkeypatch.setattr(engine.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        engine.platform,
        "freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "20.04"},
    )
    with pytest.raises(EngineError, match=r"Ubuntu 22\.04"):
        engine._platform_key()
