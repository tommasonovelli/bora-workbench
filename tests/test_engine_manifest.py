"""Tests for activation-manifest atomicity and compatibility diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import qwen_launcher._engine_manifest as manifest_module
import qwen_launcher.engine as engine
from qwen_launcher._engine_manifest import Activation
from qwen_launcher._engine_types import EngineError


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
        manifest_module.activate(root, Activation("b10011", "cpu", executable))

    assert current.read_bytes() == original
    assert not list(root.glob(".current-*.tmp"))


def test_status_keeps_active_identity_when_engine_probe_fails(tmp_path, monkeypatch) -> None:
    """Report an active manifest and exact incompatibility instead of hiding its identity."""
    root = tmp_path / "engine"
    executable = root / "installations/b10011-cpu/llama-server"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"server")
    current = {
        "schema": "managed-engine/v1",
        "release": "b10011",
        "backend": "cpu",
        "executable": "installations/b10011-cpu/llama-server",
    }
    (root / "current.json").write_text(json.dumps(current), encoding="utf-8")

    def incompatible(path, lock):
        """Simulate a binary whose version differs from the machine lock."""
        del path, lock
        raise EngineError("version differs from engine.lock")

    monkeypatch.setattr(engine, "verify_engine", incompatible)
    status = manifest_module.inspect_status(root, engine.load_engine_lock())

    assert status.is_active is True
    assert status.release == "b10011"
    assert status.is_compatible is False
    assert status.differences == ("version differs from engine.lock",)
