"""Build the pinned Ubuntu CUDA server with the exact Spike 0 CMake contract."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from qwen_launcher._engine_types import EngineError

_REQUIRED_TOOLS = ("cmake", "cc", "c++", "nvcc")


def _require_tools() -> dict[str, str]:
    """Resolve build prerequisites before running any configure or build command."""
    found = {name: shutil.which(name) for name in _REQUIRED_TOOLS}
    missing = [name for name, path in found.items() if path is None]
    if missing:
        package_command = "apt install build-essential cmake"
        cuda_guidance = "install the NVIDIA CUDA Toolkit so that nvcc is on PATH"
        raise EngineError(
            f"missing Ubuntu CUDA build prerequisites: {', '.join(missing)}. "
            f"Ask an administrator to run `{package_command}` where applicable and {cuda_guidance}."
        )
    return {name: path for name, path in found.items() if path is not None}


def _source_directory(staging: Path) -> Path:
    """Select the single source directory created by the pinned GitHub archive."""
    directories = [item for item in staging.iterdir() if item.is_dir()]
    candidates = [item for item in directories if (item / "CMakeLists.txt").is_file()]
    if len(candidates) != 1:
        raise EngineError("pinned source archive must contain exactly one CMake source directory")
    return candidates[0]


def _run_build_command(command: list[str], staging: Path) -> None:
    """Run one CMake phase without a shell and retain actionable failure output."""
    try:
        result = subprocess.run(
            command,
            cwd=staging,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as error:
        raise EngineError(f"cannot execute Ubuntu CUDA build command: {error}") from error
    if result.returncode:
        output = (result.stdout + result.stderr)[-4000:]
        raise EngineError(f"Ubuntu CUDA build failed with exit {result.returncode}:\n{output}")


def build_cuda_server(staging: Path, lock: dict[str, object]) -> Path:
    """Configure and compile only ``llama-server`` from the exact pinned source commit."""
    tools = _require_tools()
    source, build = _source_directory(staging), staging / "build"
    release = str(lock["release"])
    build_number = release.removeprefix("b")
    commit = str(lock["source_commit"])
    configure = [
        tools["cmake"],
        "-S",
        str(source),
        "-B",
        str(build),
        "-DBUILD_SHARED_LIBS=OFF",
        "-DGGML_CUDA=ON",
        "-DLLAMA_CURL=OFF",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DLLAMA_BUILD_NUMBER={build_number}",
        f"-DLLAMA_BUILD_COMMIT={commit}",
    ]
    parallel = str(max(1, os.cpu_count() or 1))
    compile_server = [
        tools["cmake"],
        "--build",
        str(build),
        "--config",
        "Release",
        "--parallel",
        parallel,
        "--target",
        "llama-server",
    ]
    _run_build_command(configure, staging)
    _run_build_command(compile_server, staging)
    return build / "bin" / "llama-server"
