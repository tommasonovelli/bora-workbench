"""Tests for lock-only command expansion and compatible engine discovery order."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import qwen_launcher.engine as engine
from qwen_launcher.config import Config
from qwen_launcher.profiles import LaunchPlan, load_catalog


def plan(tmp_path: Path, backend: str = "cpu") -> LaunchPlan:
    """Build a coding launch plan without depending on host hardware."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    return LaunchPlan(
        mode,
        "owner/model:file",
        tmp_path / "model.gguf",
        None,
        8080,
        None,
        8192,
        48 if backend == "cuda" else None,
        backend,  # type: ignore[arg-type]
        0 if backend == "cuda" else None,
        (),
    )


@pytest.mark.parametrize("backend", ["cpu", "cuda"])
def test_builder_emits_only_verified_flags_and_explicit_coding_switches(tmp_path, backend) -> None:
    """Build distinct CPU/CUDA commands with coding UI and vision explicitly disabled."""
    lock = engine.load_engine_lock()
    command = engine.build_command(tmp_path / "llama-server", plan(tmp_path, backend), lock)
    flags = {token for token in command[1:] if token.startswith("-")}

    assert flags <= set(lock["verified_flags"])
    assert "--no-webui" in command
    assert "--no-mmproj" in command
    assert ("-ncmoe" in command) is (backend == "cuda")
    assert ("-ngl" in command) is (backend == "cuda")
    assert str(tmp_path / "model.gguf") in command


def test_builder_defensively_rejects_unverified_lock_option(tmp_path) -> None:
    """Fail even if malformed lock data reaches the builder without prior validation."""
    lock = engine.load_engine_lock()
    contract = lock["command_contract"]
    assert isinstance(contract, dict)
    fixed = contract["fixed_args"]
    assert isinstance(fixed, list)
    fixed.append("--invented")

    with pytest.raises(engine.EngineError, match=r"outside engine\.lock"):
        engine.build_command(tmp_path / "llama-server", plan(tmp_path), lock)


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

    outputs = [
        SimpleNamespace(returncode=0, stdout="version: 10011 bf2c86ddc", stderr=""),
        SimpleNamespace(returncode=0, stdout="--help", stderr=""),
    ]
    monkeypatch.setattr(engine.subprocess, "run", Mock(side_effect=outputs))
    with pytest.raises(engine.EngineError, match="missing verified flags"):
        engine.verify_engine(executable, lock)


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
    manifest = {"schema": "test/v1", "release": "b10011", "backend": "cpu"}
    monkeypatch.setattr(engine, "data_dir", lambda: data)
    monkeypatch.setattr(engine.shutil, "which", lambda name: None)

    (engine_root / "current.json").write_text(
        json.dumps({**manifest, "executable": "../outside"}), encoding="utf-8"
    )
    with pytest.raises(engine.EngineError, match="escapes"):
        engine.locate(Config(), "cpu")

    relative = "installations/b10011-cpu/llama-server"
    (engine_root / "current.json").write_text(
        json.dumps({**manifest, "executable": relative}), encoding="utf-8"
    )
    monkeypatch.setattr(engine, "verify_engine", lambda path, lock: path)
    assert engine.locate(Config(), "cpu") == (engine_root / relative).resolve()
