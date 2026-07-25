"""Tests for the exact offline Ubuntu CUDA build command contract."""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import bora_workbench._engine_build as builder
from bora_workbench._engine_types import EngineError
from bora_workbench.engine import load_engine_lock


class _FakeProcess:
    """Stand in for a streamed compile process yielding scripted output lines."""

    def __init__(self, text: str, returncode: int) -> None:
        """Retain the scripted build output and the exit code to report on wait."""
        self.stdout = io.StringIO(text)
        self._returncode = returncode

    def __enter__(self) -> _FakeProcess:
        """Enter the context exactly as ``subprocess.Popen`` would."""
        return self

    def __exit__(self, *exc: object) -> bool:
        """Leave the context without suppressing exceptions."""
        return False

    def wait(self) -> int:
        """Report the scripted exit code after the output stream is drained."""
        return self._returncode


def _fake_popen(text: str = "", returncode: int = 0):
    """Build a ``subprocess.Popen`` replacement that records each compile invocation."""
    calls: list[SimpleNamespace] = []

    def popen(command, **kwargs):
        """Record the streamed command and its keyword arguments for assertions."""
        calls.append(SimpleNamespace(command=command, kwargs=kwargs))
        return _FakeProcess(text, returncode)

    return popen, calls


def _prepare_source(tmp_path) -> None:
    """Create the single CMake source directory the pinned archive would contain."""
    source = tmp_path / "llama.cpp-pinned"
    source.mkdir()
    (source / "CMakeLists.txt").write_text("test", encoding="utf-8")


def _configure_run() -> Mock:
    """Build a successful ``subprocess.run`` used for the configure phase only."""
    return Mock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("[  5%] Building CXX object common", 5),
        ("[100%] Built target llama-server", 100),
        ("[132/500] Building CUDA object ggml", 26),
        ("gmake[2]: Entering directory", None),
        ("-- Configuring done", None),
    ],
)
def test_parse_percent_reads_makefile_and_ninja_progress(line, expected) -> None:
    """Read a percentage only from CMake Unix Makefiles or Ninja progress prefixes."""
    assert builder._parse_percent(line) == expected


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
    """Configure via run and stream-compile only ``llama-server`` without a shell."""
    _prepare_source(tmp_path)
    monkeypatch.setattr(builder.shutil, "which", lambda name: f"/tools/{name}")
    run = _configure_run()
    monkeypatch.setattr(builder.subprocess, "run", run)
    popen, compile_calls = _fake_popen("[100%] Built target llama-server\n")
    monkeypatch.setattr(builder.subprocess, "Popen", popen)
    lock = load_engine_lock()

    executable = builder.build_cuda_server(tmp_path, lock)

    configure = run.call_args_list[0].args[0]
    compile_server = compile_calls[0].command
    assert "-DGGML_CUDA=ON" in configure
    assert "-DLLAMA_BUILD_NUMBER=10011" in configure
    assert f"-DLLAMA_BUILD_COMMIT={lock['source_commit']}" in configure
    assert compile_server[-2:] == ["--target", "llama-server"]
    assert executable == tmp_path / "build/bin/llama-server"
    assert "shell" not in compile_calls[0].kwargs
    assert all("shell" not in call.kwargs for call in run.call_args_list)


def test_compile_streams_measured_percentages(tmp_path, monkeypatch) -> None:
    """Forward strictly increasing CMake percentages parsed from real build output."""
    _prepare_source(tmp_path)
    monkeypatch.setattr(builder.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(builder.subprocess, "run", _configure_run())
    output = (
        "[  5%] Building CXX object common/CMakeFiles\n"
        "[ 55%] Building CUDA object ggml/CMakeFiles\n"
        "[ 55%] Building CUDA object ggml/CMakeFiles\n"
        "[100%] Built target llama-server\n"
    )
    popen, _ = _fake_popen(output)
    monkeypatch.setattr(builder.subprocess, "Popen", popen)
    seen: list[int] = []

    builder.build_cuda_server(tmp_path, load_engine_lock(), seen.append)

    assert seen == [5, 55, 100]


def test_streamed_build_failure_reports_exit_and_output_tail(tmp_path, monkeypatch) -> None:
    """Surface the compiler exit code and trailing output when the build fails."""
    _prepare_source(tmp_path)
    monkeypatch.setattr(builder.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(builder.subprocess, "run", _configure_run())
    output = "[ 50%] Building CUDA object\nnvcc fatal   : Unsupported gpu architecture\n"
    popen, _ = _fake_popen(output, returncode=2)
    monkeypatch.setattr(builder.subprocess, "Popen", popen)

    with pytest.raises(EngineError, match="exit 2") as failure:
        builder.build_cuda_server(tmp_path, load_engine_lock())

    assert "nvcc fatal" in str(failure.value)
