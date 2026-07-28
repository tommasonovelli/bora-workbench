"""Shared fixtures for the managed model store: a tiny lock and an isolated pair of locations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pytest

import bora_workbench._model_verification as model_verification
from bora_workbench import engine, models

WEIGHTS = b"weights"
PROJECTOR = b"projector"


@dataclass(frozen=True, slots=True)
class Locations:
    """Group the two places a pinned artifact can exist during one test."""

    store: Path
    snapshot: Path
    repository: Path


def tiny_lock() -> engine.JsonObject:
    """Build a lock whose pinned artifacts are small enough to hash in a test."""
    lock = engine.load_engine_lock()
    artifact = lock["default_model_artifact"]
    assert isinstance(artifact, dict)
    artifact.update(
        {
            "repository": "owner/model",
            "revision": "a" * 40,
            "filename": "model.gguf",
            "size_bytes": len(WEIGHTS),
            "sha256": hashlib.sha256(WEIGHTS).hexdigest(),
            "mmproj": {
                "filename": "mmproj.gguf",
                "size_bytes": len(PROJECTOR),
                "sha256": hashlib.sha256(PROJECTOR).hexdigest(),
            },
        }
    )
    lock["default_model"] = "owner/model:file"
    return lock


@pytest.fixture
def locations(tmp_path, monkeypatch) -> Locations:
    """Point the store, the Hugging Face cache, and the verification receipt at one isolated tree.

    Each module binds the path helpers at import time, so each is patched on the module that uses
    it; the cache root additionally travels through the environment the engine itself reads. The
    receipt root is redirected too, because `ensure_artifact` records every verification it makes
    and would otherwise append temporary test paths to the receipt of the machine running the suite.
    """
    store = tmp_path / "store"
    hub = tmp_path / "hub"
    monkeypatch.setattr(models, "models_dir", lambda: store)
    monkeypatch.setattr(engine, "models_dir", lambda: store)
    monkeypatch.setattr(model_verification, "cache_dir", lambda: tmp_path / "cache-root")
    monkeypatch.setenv("LLAMA_CACHE", str(hub))
    repository = hub / "models--owner--model"
    return Locations(store, repository / "snapshots" / ("a" * 40), repository)
