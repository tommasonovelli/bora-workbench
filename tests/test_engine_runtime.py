"""Tests for lock-only command expansion and compatible engine discovery order."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import bora_workbench._engine_probe as engine_probe
import bora_workbench.engine as engine
from bora_workbench.config import Config
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


@pytest.mark.parametrize("backend", ["cpu", "cuda"])
@pytest.mark.parametrize(
    ("mode_id", "has_ui", "has_vision", "sampling"),
    [
        ("coding", False, False, ("0.6", "0.95")),
        ("studio", True, False, ("0.7", "0.8")),
        ("vstudio", True, True, ("0.7", "0.8")),
    ],
)
def test_builder_emits_verified_three_mode_matrix(
    tmp_path, backend, mode_id, has_ui, has_vision, sampling
) -> None:
    """Emit exact UI, vision, sampling, and backend switches for all three modes."""
    lock = engine.load_engine_lock()
    selected_plan = plan(tmp_path, backend, mode_id)
    command = engine.build_command(tmp_path / "llama-server", selected_plan, lock)
    flags = {token for token in command[1:] if token.startswith("-")}

    assert flags <= set(lock["verified_flags"])
    assert ("--webui" in command) is has_ui
    assert ("--no-webui" in command) is not has_ui
    assert ("--mmproj" in command) is has_vision
    assert ("--no-mmproj" in command) is not has_vision
    assert sampling[0] == command[command.index("--temp") + 1]
    assert sampling[1] == command[command.index("--top-p") + 1]
    assert command[command.index("--top-k") + 1] == "20"
    assert str(selected_plan.model_path) in command
    assert (str(selected_plan.mmproj_path) in command) is has_vision
    assert ("-ncmoe" in command) is (backend == "cuda")
    assert ("-ngl" in command) is (backend == "cuda")
    assert ("--cache-type-k" in command) is (backend == "cuda")
    assert ("--cache-type-v" in command) is (backend == "cuda")
    if backend == "cuda":
        assert command[command.index("--cache-type-k") + 1] == "q8_0"
        assert command[command.index("--cache-type-v") + 1] == "q8_0"
    assert "--no-mmap" not in command
    assert "--mmap" in command
    assert ("--spec-type" in command) is not has_vision
    assert ("--spec-draft-n-max" in command) is not has_vision


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
    monkeypatch.setattr(engine_probe.subprocess, "run", run)
    executable = tmp_path / "llama-server"

    assert engine.verify_engine(executable, lock) == executable.resolve()
    assert all("shell" not in call.kwargs for call in run.call_args_list)
    assert all(call.kwargs["timeout"] == 60 for call in run.call_args_list)

    outputs = [
        SimpleNamespace(returncode=0, stdout="version: 10011 bf2c86ddc", stderr=""),
        SimpleNamespace(returncode=0, stdout="--help", stderr=""),
    ]
    monkeypatch.setattr(engine_probe.subprocess, "run", Mock(side_effect=outputs))
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
    manifest = {"schema": "managed-engine/v1", "release": "b10011", "backend": "cpu"}
    monkeypatch.setattr(engine, "data_dir", lambda: data)
    monkeypatch.setattr(engine.shutil, "which", lambda name: None)

    for unsafe in ("../outside", r"C:\\outside\\llama-server.exe"):
        (engine_root / "current.json").write_text(
            json.dumps({**manifest, "executable": unsafe}), encoding="utf-8"
        )
        with pytest.raises(engine.EngineError, match="safe relative"):
            engine.locate(Config(), "cpu")

    relative = "installations/b10011-cpu/llama-server"
    (engine_root / "current.json").write_text(
        json.dumps({**manifest, "executable": relative}), encoding="utf-8"
    )
    monkeypatch.setattr(engine, "verify_engine", lambda path, lock: path)
    assert engine.locate(Config(), "cpu") == (engine_root / relative).resolve()
