"""Resolve, install, and locate the platform-bound engine from locked evidence."""

from __future__ import annotations

import os
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from bora_workbench._engine_probe import verify_engine
from bora_workbench._engine_types import (
    Backend,
    EngineError,
    EngineStatus,
    InstallProgress,
    InstallRequest,
    InstallResult,
    PlatformKey,
    ResolvedModel,
)
from bora_workbench.config import Config
from bora_workbench.paths import cache_dir, data_dir
from bora_workbench.profiles import LaunchPlan
from bora_workbench.resources import read_json

JsonObject = dict[str, object]


def load_engine_lock() -> JsonObject:
    """Load the already validated packaged engine machine contract."""
    return cast(JsonObject, read_json("engine.lock"))


def _hf_cache_dir(environ: Mapping[str, str]) -> Path:
    """Apply the exact b10011 cache precedence observed in locked ``hf-cache.cpp``."""
    entries = (
        ("LLAMA_CACHE", Path()),
        ("HF_HUB_CACHE", Path()),
        ("HUGGINGFACE_HUB_CACHE", Path()),
        ("HF_HOME", Path("hub")),
        ("XDG_CACHE_HOME", Path("huggingface") / "hub"),
    )
    for variable, suffix in entries:
        if value := environ.get(variable):
            return Path(value) / suffix
    home_variable = "USERPROFILE" if os.name == "nt" else "HOME"
    if value := environ.get(home_variable):
        return Path(value) / ".cache" / "huggingface" / "hub"
    if os.name != "nt":
        return Path.home() / ".cache" / "huggingface" / "hub"
    raise EngineError("cannot determine the Hugging Face cache; set HF_HUB_CACHE")


def resolve_model(config: Config, lock: JsonObject, require_vision: bool = False) -> ResolvedModel:
    """Resolve locally without writes, pinned to the lock revision for the default model."""
    from bora_workbench._engine_artifact import verify_artifact, verify_custom_model

    artifact = cast(JsonObject, lock["default_model_artifact"])
    if config.model != lock["default_model"]:
        if config.model_path is None:
            raise EngineError("a non-default model requires an explicit model_path")
        return ResolvedModel(verify_custom_model(config.model_path), None)
    if config.model_path is not None:
        message = "model_path is only accepted for a non-default model identity"
        raise EngineError(message)
    repository = cast(str, artifact["repository"]).replace("/", "--")
    snapshot = _hf_cache_dir(os.environ) / f"models--{repository}" / "snapshots"
    snapshot /= cast(str, artifact["revision"])
    model_path = snapshot / cast(str, artifact["filename"])
    verified_model = verify_artifact(model_path, artifact)
    if not require_vision:
        return ResolvedModel(verified_model, None)
    mmproj = cast(JsonObject, artifact["mmproj"])
    mmproj_path = model_path.parent / cast(str, mmproj["filename"])
    return ResolvedModel(verified_model, verify_artifact(mmproj_path, mmproj))


def _managed_candidate(backend: str, lock: JsonObject) -> Path | None:
    """Resolve the active manifest through the confined managed-engine contract."""
    from bora_workbench._engine_manifest import managed_candidate

    return managed_candidate(data_dir() / "engine", backend, lock)


def _platform_key() -> PlatformKey:
    """Map only supported x86-64 Windows and Ubuntu hosts to lock asset identifiers."""
    machine = platform.machine().lower()
    if machine not in {"amd64", "x86_64"}:
        raise EngineError(f"managed engine installation requires x86-64, found {machine!r}")
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system != "linux":
        raise EngineError(f"managed engine installation is unsupported on {platform.system()}")
    try:
        distribution = platform.freedesktop_os_release().get("ID", "").lower()
    except OSError as error:
        raise EngineError(f"cannot identify the Linux distribution: {error}") from error
    if distribution != "ubuntu":
        raise EngineError(f"managed engine installation requires Ubuntu, found {distribution!r}")
    return "ubuntu"


def install_engine(
    backend: Backend, force: bool = False, progress: InstallProgress | None = None
) -> InstallResult:
    """Install and activate the complete lock-selected engine for this host."""
    from bora_workbench._engine_install import install_engine as run_install

    lock = load_engine_lock()
    platform_key = _platform_key()
    notices = ("notices/llama.cpp-LICENSE",)
    if platform_key == "windows" and backend == "cuda":
        notices += ("notices/NVIDIA-CUDA-EULA.html",)
    request = InstallRequest(
        platform_key,
        backend,
        force,
        data_dir() / "engine",
        cache_dir() / "llama.cpp",
        lock,
        notices,
        platform_key == "ubuntu",
        progress,
    )
    return run_install(request)


def engine_status(lock: JsonObject | None = None) -> EngineStatus:
    """Inspect the active managed engine without creating files or directories."""
    from bora_workbench._engine_manifest import inspect_status

    selected_lock = load_engine_lock() if lock is None else lock
    return inspect_status(data_dir() / "engine", selected_lock)


def build_command(executable: Path, plan: LaunchPlan, lock: JsonObject) -> tuple[str, ...]:
    """Build the verified llama-server command through the lock-only expander."""
    from bora_workbench._engine_command import build_engine_command

    return build_engine_command(executable, plan, lock)


def locate(config: Config, backend: str, lock: JsonObject | None = None) -> Path:
    """Locate and verify explicit, PATH, then managed engine candidates in normative order."""
    selected_lock = load_engine_lock() if lock is None else lock
    if config.engine_path is not None:
        return verify_engine(config.engine_path, selected_lock)
    name = "llama-server.exe" if os.name == "nt" else "llama-server"
    if discovered := shutil.which(name):
        return verify_engine(Path(discovered), selected_lock)
    managed = _managed_candidate(backend, selected_lock)
    if managed is not None:
        return verify_engine(managed, selected_lock)
    raise EngineError(
        "no compatible llama-server found; set engine_path or install the pinned engine"
    )
