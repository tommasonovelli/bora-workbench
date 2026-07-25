"""Tests for the Ubuntu CUDA build contract, immutable promotion, and atomic activation."""

from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

import bora_workbench._engine_install as installer
import bora_workbench.engine as engine
from bora_workbench._engine_assets import EngineAsset, TransferProgress
from bora_workbench._engine_install import InstallRequest
from bora_workbench.engine import Backend, EngineError, InstallProgressEvent


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
    assert installer._parse_percent(line) == expected


def test_missing_prerequisites_stop_before_running_cmake(tmp_path, monkeypatch) -> None:
    """List missing tools and an actionable remedy without executing installation commands."""
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    run = Mock()
    monkeypatch.setattr(installer.subprocess, "run", run)

    with pytest.raises(EngineError, match=r"cmake, cc, c\+\+, nvcc") as failure:
        installer.build_cuda_server(tmp_path, engine.load_engine_lock())

    assert "apt install build-essential cmake" in str(failure.value)
    run.assert_not_called()


def test_build_uses_pinned_commit_version_and_server_target(tmp_path, monkeypatch) -> None:
    """Configure via run and stream-compile only ``llama-server`` without a shell."""
    _prepare_source(tmp_path)
    monkeypatch.setattr(installer.shutil, "which", lambda name: f"/tools/{name}")
    run = _configure_run()
    monkeypatch.setattr(installer.subprocess, "run", run)
    popen, compile_calls = _fake_popen("[100%] Built target llama-server\n")
    monkeypatch.setattr(installer.subprocess, "Popen", popen)
    lock = engine.load_engine_lock()

    executable = installer.build_cuda_server(tmp_path, lock)

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
    monkeypatch.setattr(installer.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(installer.subprocess, "run", _configure_run())
    output = (
        "[  5%] Building CXX object common/CMakeFiles\n"
        "[ 55%] Building CUDA object ggml/CMakeFiles\n"
        "[ 55%] Building CUDA object ggml/CMakeFiles\n"
        "[100%] Built target llama-server\n"
    )
    popen, _ = _fake_popen(output)
    monkeypatch.setattr(installer.subprocess, "Popen", popen)
    seen: list[int] = []

    installer.build_cuda_server(tmp_path, engine.load_engine_lock(), seen.append)

    assert seen == [5, 55, 100]


def test_streamed_build_failure_reports_exit_and_output_tail(tmp_path, monkeypatch) -> None:
    """Surface the compiler exit code and trailing output when the build fails."""
    _prepare_source(tmp_path)
    monkeypatch.setattr(installer.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(installer.subprocess, "run", _configure_run())
    output = "[ 50%] Building CUDA object\nnvcc fatal   : Unsupported gpu architecture\n"
    popen, _ = _fake_popen(output, returncode=2)
    monkeypatch.setattr(installer.subprocess, "Popen", popen)

    with pytest.raises(EngineError, match="exit 2") as failure:
        installer.build_cuda_server(tmp_path, engine.load_engine_lock())

    assert "nvcc fatal" in str(failure.value)


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
    return InstallRequest(
        "windows",
        cast(Backend, backend),
        force,
        tmp_path / "engine",
        tmp_path / "cache",
        engine.load_engine_lock(),
    )


def patch_artifacts(monkeypatch) -> None:
    """Replace network and extraction while preserving promotion and manifest behavior."""
    monkeypatch.setattr(
        installer,
        "select_assets",
        lambda lock, platform_key, backend: (server_asset(backend),),
    )

    def download(asset, root, progress):
        """Represent an already verified cached archive and report its known size."""
        progress(TransferProgress(6, 6, True))
        return root / asset.filename

    monkeypatch.setattr(installer, "download_asset", download)

    def extract(request):
        """Materialize the synthetic server instead of opening a real archive."""
        path = request.destination / str(request.asset.executable)
        path.parent.mkdir(parents=True, exist_ok=True)
        request.progress(TransferProgress(0, 6))
        path.write_bytes(b"server")
        request.progress(TransferProgress(6, 6))

    monkeypatch.setattr(installer, "extract_asset", extract)
    monkeypatch.setattr(installer, "verify_engine", lambda executable, lock: executable.resolve())
    monkeypatch.setattr(engine, "verify_engine", lambda executable, lock: executable.resolve())


def manifest_bytes(root: Path) -> bytes:
    """Read the exact current manifest bytes for atomicity assertions."""
    return (root / "engine/current.json").read_bytes()


def test_ubuntu_verification_requests_executable_mode(tmp_path, monkeypatch) -> None:
    """Apply the Ubuntu executable bit without asserting POSIX mode behavior on Windows hosts."""
    executable = tmp_path / "llama-server"
    executable.write_bytes(b"server")
    selected = replace(request(tmp_path), platform_key="ubuntu")
    observed_modes: list[int] = []

    def capture_mode(path, mode):
        """Record the requested mode independently of host chmod semantics."""
        del path
        observed_modes.append(mode)

    monkeypatch.setattr(Path, "chmod", capture_mode)
    monkeypatch.setattr(installer, "verify_engine", lambda path, lock: path.resolve())

    installer._verify_staged(executable, selected)

    assert observed_modes[0] & 0o100


def test_install_no_op_force_and_backend_change(tmp_path, monkeypatch) -> None:
    """No-op an identical target but promote new immutable directories for force and backend."""
    patch_artifacts(monkeypatch)
    first = installer.install_managed_engine(request(tmp_path))
    second = installer.install_managed_engine(request(tmp_path))
    forced = installer.install_managed_engine(request(tmp_path, force=True))
    changed = installer.install_managed_engine(request(tmp_path, backend="cuda"))
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


def test_install_reports_blocking_phases_in_execution_order(tmp_path, monkeypatch) -> None:
    """Expose download, extraction, probe, and activation so installation never looks idle."""
    patch_artifacts(monkeypatch)
    source = replace(server_asset(), role="source")
    monkeypatch.setattr(installer, "select_assets", lambda lock, platform_key, backend: (source,))
    monkeypatch.setattr(
        installer, "build_cuda_server", lambda staging, *_: staging / "llama-server.exe"
    )
    observed: list[InstallProgressEvent] = []
    selected = replace(request(tmp_path), progress=observed.append)
    installer.install_managed_engine(selected)
    assert observed == [
        InstallProgressEvent("asset", "engine.zip", 1, 1),
        InstallProgressEvent("download", "engine.zip", 1, 1, 6, 6, True),
        InstallProgressEvent("extract", "engine.zip", 1, 1),
        InstallProgressEvent("extract", "engine.zip", 1, 1, 0, 6),
        InstallProgressEvent("extract", "engine.zip", 1, 1, 6, 6),
        InstallProgressEvent("compile"),
        InstallProgressEvent("verify"),
        InstallProgressEvent("activate"),
    ]


def test_staging_failure_leaves_previous_activation_intact(tmp_path, monkeypatch) -> None:
    """Clean failed staging without changing the active installation or current manifest."""
    patch_artifacts(monkeypatch)
    installer.install_managed_engine(request(tmp_path))
    previous = manifest_bytes(tmp_path)

    def fail_extract(extraction):
        """Simulate an extraction failure after a prior activation exists."""
        del extraction
        raise EngineError("synthetic extraction failure")

    monkeypatch.setattr(installer, "extract_asset", fail_extract)
    with pytest.raises(EngineError, match="synthetic extraction failure"):
        installer.install_managed_engine(request(tmp_path, force=True))

    assert manifest_bytes(tmp_path) == previous
    assert not list((tmp_path / "engine").glob(".staging-*"))
    assert len(list((tmp_path / "engine/installations").iterdir())) == 1


def test_activation_failure_keeps_old_manifest_and_promoted_install(tmp_path, monkeypatch) -> None:
    """Keep prior activation while leaving a verified promoted directory inactive for inspection."""
    patch_artifacts(monkeypatch)
    installer.install_managed_engine(request(tmp_path))
    previous = manifest_bytes(tmp_path)
    original_activate = installer.activate

    def fail_activation(engine_root, activation):
        """Simulate failure while replacing the activation manifest."""
        del engine_root, activation
        raise EngineError("synthetic manifest failure")

    monkeypatch.setattr(installer, "activate", fail_activation)
    with pytest.raises(EngineError, match="synthetic manifest failure"):
        installer.install_managed_engine(request(tmp_path, force=True))
    monkeypatch.setattr(installer, "activate", original_activate)

    assert manifest_bytes(tmp_path) == previous
    assert len(list((tmp_path / "engine/installations").iterdir())) == 2


def test_corrupt_manifest_is_repaired_by_complete_install(tmp_path, monkeypatch) -> None:
    """Replace a corrupt current manifest only after a new compatible installation is promoted."""
    patch_artifacts(monkeypatch)
    root = tmp_path / "engine"
    root.mkdir()
    (root / "current.json").write_text("{broken", encoding="utf-8")

    result = installer.install_managed_engine(request(tmp_path))

    assert result.was_installed is True
    assert json.loads((root / "current.json").read_text())["release"] == "b10011"
