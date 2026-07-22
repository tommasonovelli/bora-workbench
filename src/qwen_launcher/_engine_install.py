"""Stage, verify, promote, and atomically activate a managed engine installation."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from qwen_launcher._engine_archive import extract_asset
from qwen_launcher._engine_assets import select_assets
from qwen_launcher._engine_build import build_cuda_server
from qwen_launcher._engine_download import download_asset
from qwen_launcher._engine_manifest import Activation, activate, inspect_status
from qwen_launcher._engine_types import (
    EngineAsset,
    EngineError,
    EngineStatus,
    InstallRequest,
    InstallResult,
    InstallStage,
)
from qwen_launcher.resources import resource


def _report(request: InstallRequest, stage: InstallStage, detail: str | None = None) -> None:
    """Forward an installation phase when the caller requested progress updates."""
    if request.progress is not None:
        request.progress(stage, detail)


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


def _copy_notice(relative: str, destination: Path) -> None:
    """Copy one packaged third-party notice without assuming a physical wheel resource."""
    destination.write_bytes(resource(relative).read_bytes())


def _install_notices(request: InstallRequest, destination: Path) -> None:
    """Copy the exact third-party notices selected by the public engine module."""
    notices = destination / "THIRD_PARTY_NOTICES"
    notices.mkdir(parents=True, exist_ok=True)
    for relative in request.notice_resources:
        _copy_notice(relative, notices / Path(relative).name)


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
    for asset in assets:
        _report(request, "asset", asset.filename)
        archive = download_asset(asset, request.cache_root)
        _report(request, "extract", asset.filename)
        extract_asset(asset, archive, staging)
    _install_notices(request, staging)
    server_asset = _server_asset(assets)
    assert server_asset.executable is not None
    declared = staging / server_asset.executable
    if server_asset.role == "source":
        _report(request, "compile")
        built = build_cuda_server(staging, request.lock)
        if built.resolve() != declared.resolve():
            raise EngineError("Ubuntu CUDA build output differs from engine.lock executable")
    return declared


def _verify_staged(executable: Path, request: InstallRequest) -> Path:
    """Require a regular compatible executable before immutable promotion."""
    if not executable.is_file() or executable.is_symlink():
        raise EngineError(f"staged engine executable is missing or unsafe: {executable}")
    if request.set_executable_mode:
        executable.chmod(executable.stat().st_mode | 0o100)
    from qwen_launcher.engine import verify_engine

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


def _existing_result(request: InstallRequest) -> InstallResult | None:
    """Return a no-op result only for the same fully compatible active target."""
    status = inspect_status(request.engine_root, request.lock)
    same_release = status.release == request.lock.get("release")
    same_target = same_release and status.backend == request.backend
    if not request.force and status.is_compatible and same_target:
        return InstallResult(status, False)
    return None


def install_engine(request: InstallRequest) -> InstallResult:
    """Install the lock-selected target while leaving prior activation intact on every failure."""
    existing = _existing_result(request)
    if existing is not None:
        return existing
    staging = request.engine_root / f".staging-{uuid4().hex}"
    try:
        request.engine_root.mkdir(parents=True, exist_ok=True)
        staged = _prepare_staging(request, staging)
        _report(request, "verify")
        verified = _verify_staged(staged, request)
        promoted = _promote(staging, request, verified)
        activation = Activation(str(request.lock["release"]), request.backend, promoted)
        _report(request, "activate")
        activate(request.engine_root, activation)
        status = EngineStatus(
            True,
            activation.release,
            activation.backend,
            promoted.resolve(),
            True,
        )
        return InstallResult(status, True)
    except (EngineError, OSError, KeyboardInterrupt) as error:
        if staging.exists() or staging.is_symlink():
            _remove_staging(staging, request.engine_root)
        if isinstance(error, OSError):
            raise EngineError(f"managed engine installation failed: {error}") from error
        raise
