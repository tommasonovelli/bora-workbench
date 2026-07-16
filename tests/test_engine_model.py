"""Tests for read-only model resolution at the exact pinned snapshot and digest."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import qwen_launcher.engine as engine
from qwen_launcher.config import Config


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
