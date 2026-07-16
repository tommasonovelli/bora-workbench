"""Tests for the exact offline Ubuntu CUDA build command contract."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import qwen_launcher._engine_build as builder
from qwen_launcher._engine_types import EngineError
from qwen_launcher.engine import load_engine_lock


def test_missing_prerequisites_stop_before_running_cmake(tmp_path, monkeypatch) -> None:
    """List missing tools and an actionable remedy without executing installation commands."""
    monkeypatch.setattr(builder.shutil, "which", lambda name: None)
    run = Mock()
    monkeypatch.setattr(builder.subprocess, "run", run)

    with pytest.raises(EngineError, match=r"cmake, cc, c\+\+, nvcc") as failure:
        builder.build_cuda_server(tmp_path, load_engine_lock())

    assert "apt install build-essential cmake" in str(failure.value)
    run.assert_not_called()


def test_build_uses_pinned_commit_version_and_server_target(tmp_path, monkeypatch) -> None:
    """Configure the verified static CUDA build and compile only ``llama-server`` without shell."""
    source = tmp_path / "llama.cpp-pinned"
    source.mkdir()
    (source / "CMakeLists.txt").write_text("test", encoding="utf-8")
    monkeypatch.setattr(builder.shutil, "which", lambda name: f"/tools/{name}")
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(builder.subprocess, "run", run)
    lock = load_engine_lock()

    executable = builder.build_cuda_server(tmp_path, lock)

    configure = run.call_args_list[0].args[0]
    compile_server = run.call_args_list[1].args[0]
    assert "-DGGML_CUDA=ON" in configure
    assert "-DLLAMA_BUILD_NUMBER=10011" in configure
    assert f"-DLLAMA_BUILD_COMMIT={lock['source_commit']}" in configure
    assert compile_server[-2:] == ["--target", "llama-server"]
    assert executable == tmp_path / "build/bin/llama-server"
    assert all("shell" not in call.kwargs for call in run.call_args_list)
