"""Resolve pinned model artifacts and locate a compatible llama.cpp executable.

This module may branch on the operating system because engine and cache layouts are platform-bound
(specification sections 4.1, 5.8, and Spike 0's locked source evidence).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from qwen_launcher.config import Config
from qwen_launcher.paths import data_dir
from qwen_launcher.profiles import LaunchPlan
from qwen_launcher.resources import read_json

JsonObject = dict[str, object]


class EngineError(RuntimeError):
    """Report an absent or incompatible model or engine artifact."""


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """Hold physical model files without changing their declarative identity."""

    model_path: Path
    mmproj_path: Path | None


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
    from qwen_launcher._engine_artifact import verify_artifact, verify_custom_model

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


def _probe(executable: Path, contract: JsonObject) -> str:
    """Run one bounded version or help probe without a shell."""
    args = [str(executable), *cast(list[str], contract["args"])]
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EngineError(f"cannot probe engine {executable}: {error}") from error
    output = result.stdout + result.stderr
    if result.returncode != contract["exit_code"]:
        raise EngineError(f"engine probe failed with exit code {result.returncode}: {executable}")
    return output


def _flag_listed(output: str, flag: str) -> bool:
    """Match one complete option token rather than accepting it inside another flag."""
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(flag)}(?![A-Za-z0-9_-])"
    return re.search(pattern, output) is not None


def verify_engine(executable: Path, lock: JsonObject) -> Path:
    """Require the lock's version fragments and complete verified option vocabulary."""
    version_contract = cast(JsonObject, lock["version_contract"])
    version_output = _probe(executable, version_contract)
    fragments = cast(list[str], version_contract["output_contains"])
    if any(fragment not in version_output for fragment in fragments):
        raise EngineError(
            f"engine version is incompatible with release {lock['release']}: {executable}"
        )
    help_output = _probe(executable, cast(JsonObject, lock["help_contract"]))
    missing = [
        flag
        for flag in cast(list[str], lock["verified_flags"])
        if not _flag_listed(help_output, flag)
    ]
    if missing:
        raise EngineError(f"engine help is missing verified flags {missing}: {executable}")
    return executable.resolve()


def _managed_candidate(backend: str, lock: JsonObject) -> Path | None:
    """Resolve a managed manifest only when it stays below immutable installations."""
    engine_root = data_dir() / "engine"
    manifest_path = engine_root / "current.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EngineError(
            f"managed engine manifest is invalid: {manifest_path}: {error}"
        ) from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("schema"), str):
        raise EngineError(f"managed engine manifest has no valid schema: {manifest_path}")
    if manifest.get("release") != lock["release"] or manifest.get("backend") != backend:
        raise EngineError("managed engine release or backend differs from engine.lock")
    relative = manifest.get("executable")
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise EngineError("managed engine executable must be a relative path")
    candidate = (engine_root / relative).resolve()
    installations = (engine_root / "installations").resolve()
    if not candidate.is_relative_to(installations):
        raise EngineError("managed engine executable escapes the installations directory")
    return candidate


def build_command(executable: Path, plan: LaunchPlan, lock: JsonObject) -> tuple[str, ...]:
    """Build the verified llama-server command through the lock-only expander."""
    from qwen_launcher._engine_command import build_engine_command

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
