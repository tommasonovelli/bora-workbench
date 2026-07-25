"""Compile, stage, verify, promote, and activate a managed engine installation.

The installer never mutates an existing installation: it assembles a complete candidate in a
private staging directory, probes it against `engine.lock`, moves it to an immutable versioned
directory, and only then replaces the activation manifest (specification section 5.10). Any
failure therefore leaves the previous engine active.

The Ubuntu CUDA target is the one pair compiled here instead of downloaded, using the exact
Spike 0 CMake contract, because the pinned release publishes no Linux CUDA prebuilt.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from uuid import uuid4

from bora_workbench._engine_assets import (
    EngineAsset,
    ExtractionRequest,
    TransferProgress,
    download_asset,
    extract_asset,
    select_assets,
)
from bora_workbench.engine import (
    Activation,
    Backend,
    EngineError,
    EngineStatus,
    InstallProgress,
    InstallProgressEvent,
    InstallResult,
    JsonObject,
    PlatformKey,
    activate,
    inspect_status,
    verify_engine,
)
from bora_workbench.resources import resource

_REQUIRED_TOOLS = ("cmake", "cc", "c++", "nvcc")

# CMake reports build progress as ``[ NN%]`` under Unix Makefiles and ``[done/total]``
# under Ninja; both prefixes are the only truthful source of a compile percentage.
_MAKEFILE_PERCENT = re.compile(r"^\[\s*(\d{1,3})%\]")
_NINJA_STEP = re.compile(r"^\[(\d+)/(\d+)\]")

# Retain enough trailing build output to keep a compiler failure actionable on stderr.
_ERROR_TAIL_LINES = 200


@dataclass(frozen=True, slots=True)
class InstallRequest:
    """Group the roots and target selected by the public engine module."""

    platform_key: PlatformKey
    backend: Backend
    force: bool
    engine_root: Path
    cache_root: Path
    lock: JsonObject
    progress: InstallProgress | None = None


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


def _forward_percentages(lines: Iterable[str], on_percent: Callable[[int], None]) -> deque[str]:
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


def _run_streamed_build(
    command: list[str], staging: Path, on_percent: Callable[[int], None]
) -> None:
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
    staging: Path, lock: JsonObject, on_percent: Callable[[int], None] | None = None
) -> Path:
    """Configure and compile only ``llama-server`` from the exact pinned source commit.

    ``on_percent`` receives a measured CMake compile percentage in [0, 100].
    """
    tools = _require_tools()
    source, build = _source_directory(staging), staging / "build"
    build_number = str(lock["release"]).removeprefix("b")
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


def _report(request: InstallRequest, event: InstallProgressEvent) -> None:
    """Forward one installation update when the caller requested progress."""
    if request.progress is not None:
        request.progress(event)


def _report_compile(request: InstallRequest, percent: int) -> None:
    """Forward one measured CMake compile percentage as a compile progress event."""
    _report(request, InstallProgressEvent("compile", percent=percent))


def _report_transfer(
    request: InstallRequest, event: InstallProgressEvent, update: TransferProgress
) -> None:
    """Attach measured transfer bytes to one asset phase before forwarding it."""
    measured = replace(
        event,
        completed_bytes=update.completed_bytes,
        total_bytes=update.total_bytes,
        is_cached=update.is_cached,
    )
    _report(request, measured)


def _remove_staging(path: Path, engine_root: Path) -> None:
    """Delete only a staging directory proven to be below the managed engine root."""
    resolved, root = path.resolve(), engine_root.resolve()
    if resolved.parent != root or not resolved.name.startswith(".staging-"):
        raise EngineError(f"refusing to remove unmanaged staging path: {resolved}")
    if resolved.exists():
        try:
            shutil.rmtree(resolved)
        except OSError as error:
            raise EngineError(
                f"cannot clean managed staging directory {resolved}: {error}"
            ) from error


def _install_notices(request: InstallRequest, destination: Path) -> None:
    """Copy the third-party notices the target must carry, via Traversable bytes access.

    Windows CUDA also redistributes the NVIDIA runtime, so it carries the CUDA EULA in addition to
    the llama.cpp license.
    """
    relatives = ["notices/llama.cpp-LICENSE"]
    if request.platform_key == "windows" and request.backend == "cuda":
        relatives.append("notices/NVIDIA-CUDA-EULA.html")
    notices = destination / "THIRD_PARTY_NOTICES"
    notices.mkdir(parents=True, exist_ok=True)
    for relative in relatives:
        (notices / Path(relative).name).write_bytes(resource(relative).read_bytes())


def _server_asset(assets: tuple[EngineAsset, ...]) -> EngineAsset:
    """Return the one asset whose executable contract identifies the server."""
    candidates = [asset for asset in assets if asset.executable is not None]
    if len(candidates) != 1:
        raise EngineError("selected asset set must identify exactly one server executable")
    return candidates[0]


def _prepare_staging(request: InstallRequest, staging: Path) -> Path:
    """Download and extract the complete target asset set into one staging directory."""
    assets = select_assets(request.lock, request.platform_key, request.backend)
    staging.mkdir(parents=False)
    for index, asset in enumerate(assets, start=1):
        common = InstallProgressEvent("asset", asset.filename, index, len(assets))
        _report(request, common)
        download_event = replace(common, stage="download")
        download_progress = partial(_report_transfer, request, download_event)
        archive = download_asset(asset, request.cache_root, download_progress)
        extract_event = replace(common, stage="extract")
        _report(request, extract_event)
        extract_progress = partial(_report_transfer, request, extract_event)
        extract_asset(ExtractionRequest(asset, archive, staging, extract_progress))
    _install_notices(request, staging)
    server_asset = _server_asset(assets)
    assert server_asset.executable is not None
    declared = staging / server_asset.executable
    if server_asset.role == "source":
        _report(request, InstallProgressEvent("compile"))
        built = build_cuda_server(staging, request.lock, partial(_report_compile, request))
        if built.resolve() != declared.resolve():
            raise EngineError("Ubuntu CUDA build output differs from engine.lock executable")
    return declared


def _verify_staged(executable: Path, request: InstallRequest) -> Path:
    """Require a regular compatible executable before immutable promotion.

    Only the Ubuntu archives need the executable bit restored; the Windows targets ship it.
    """
    if not executable.is_file() or executable.is_symlink():
        raise EngineError(f"staged engine executable is missing or unsafe: {executable}")
    if request.platform_key == "ubuntu":
        executable.chmod(executable.stat().st_mode | 0o100)
    return verify_engine(executable, request.lock)


def _promote(staging: Path, request: InstallRequest, executable: Path) -> Path:
    """Move verified staging to a new immutable versioned directory on the same filesystem."""
    installations = request.engine_root / "installations"
    installations.mkdir(parents=True, exist_ok=True)
    name = f"{request.lock['release']}-{request.backend}-{uuid4().hex}"
    destination = installations / name
    relative = executable.relative_to(staging)
    staging.replace(destination)
    return destination / relative


def install_managed_engine(request: InstallRequest) -> InstallResult:
    """Install the lock-selected target while leaving prior activation intact on every failure."""
    status = inspect_status(request.engine_root, request.lock)
    same_release = status.release == request.lock.get("release")
    same_target = same_release and status.backend == request.backend
    if not request.force and status.is_compatible and same_target:
        return InstallResult(status, False)
    staging = request.engine_root / f".staging-{uuid4().hex}"
    try:
        request.engine_root.mkdir(parents=True, exist_ok=True)
        staged = _prepare_staging(request, staging)
        _report(request, InstallProgressEvent("verify"))
        verified = _verify_staged(staged, request)
        promoted = _promote(staging, request, verified)
        activation = Activation(str(request.lock["release"]), request.backend, promoted)
        _report(request, InstallProgressEvent("activate"))
        activate(request.engine_root, activation)
        installed = EngineStatus(
            True,
            activation.release,
            activation.backend,
            promoted.resolve(),
            True,
        )
        return InstallResult(installed, True)
    except (EngineError, OSError, KeyboardInterrupt) as error:
        if staging.exists() or staging.is_symlink():
            _remove_staging(staging, request.engine_root)
        if isinstance(error, OSError):
            raise EngineError(f"managed engine installation failed: {error}") from error
        raise
