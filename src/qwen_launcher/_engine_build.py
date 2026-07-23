"""Build the pinned Ubuntu CUDA server with the exact Spike 0 CMake contract."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import deque
from collections.abc import Iterable
from pathlib import Path

from qwen_launcher._engine_types import CompileProgress, EngineError

_REQUIRED_TOOLS = ("cmake", "cc", "c++", "nvcc")

# CMake reports build progress as ``[ NN%]`` under Unix Makefiles and ``[done/total]``
# under Ninja; both prefixes are the only truthful source of a compile percentage.
_MAKEFILE_PERCENT = re.compile(r"^\[\s*(\d{1,3})%\]")
_NINJA_STEP = re.compile(r"^\[(\d+)/(\d+)\]")

# Retain enough trailing build output to keep a compiler failure actionable on stderr.
_ERROR_TAIL_LINES = 200


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


def _parse_percent(line: str) -> int | None:
    """Read a compile percentage from one CMake Unix Makefiles or Ninja progress line."""
    stripped = line.lstrip()
    if makefile := _MAKEFILE_PERCENT.match(stripped):
        return min(100, int(makefile.group(1)))
    if ninja := _NINJA_STEP.match(stripped):
        done, total = int(ninja.group(1)), int(ninja.group(2))
        if total > 0:
            return min(100, done * 100 // total)
    return None


def _forward_percentages(lines: Iterable[str], on_percent: CompileProgress) -> deque[str]:
    """Forward strictly increasing compile percentages and keep a bounded failure tail."""
    tail: deque[str] = deque(maxlen=_ERROR_TAIL_LINES)
    last_percent = -1
    for line in lines:
        tail.append(line)
        percent = _parse_percent(line)
        if percent is not None and percent > last_percent:
            last_percent = percent
            on_percent(percent)
    return tail


def _run_streamed_build(command: list[str], staging: Path, on_percent: CompileProgress) -> None:
    """Compile without a shell while streaming real CMake percentages to the caller."""
    try:
        with subprocess.Popen(
            command,
            cwd=staging,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        ) as process:
            assert process.stdout is not None
            tail = _forward_percentages(iter(process.stdout.readline, ""), on_percent)
            returncode = process.wait()
    except OSError as error:
        raise EngineError(f"cannot execute Ubuntu CUDA build command: {error}") from error
    if returncode:
        output = "".join(tail)[-4000:]
        raise EngineError(f"Ubuntu CUDA build failed with exit {returncode}:\n{output}")


def build_cuda_server(
    staging: Path, lock: dict[str, object], on_percent: CompileProgress | None = None
) -> Path:
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
    report = on_percent if on_percent is not None else (lambda _percent: None)
    _run_build_command(configure, staging)
    _run_streamed_build(compile_server, staging, report)
    return build / "bin" / "llama-server"
