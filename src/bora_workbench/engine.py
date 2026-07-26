"""Resolve, verify, activate, and drive the platform-bound llama.cpp engine.

This module owns every contract the launcher reads from `engine.lock` (specification section 4.1):
the pinned model artifacts, the exact command vocabulary, the version and help probes, the managed
activation manifest, and engine discovery. Acquiring a managed installation is delegated to
`_engine_assets` and `_engine_install`, which build on the contracts declared here.

This is one of the four modules allowed to branch on the operating system (specification section
4.1): the Hugging Face cache precedence, the `llama-server` file name, and the managed asset target
are all host-specific.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, cast
from uuid import uuid4

from bora_workbench.config import Config
from bora_workbench.paths import cache_dir, data_dir
from bora_workbench.profiles import LaunchPlan
from bora_workbench.resources import read_json

JsonObject = dict[str, object]

Backend = Literal["cpu", "cuda"]
PlatformKey = Literal["ubuntu", "windows"]
InstallStage = Literal["asset", "download", "extract", "compile", "verify", "activate"]

_MANAGED_SCHEMA = "managed-engine/v1"
_PROBE_TIMEOUT_SECONDS = 60


class EngineError(RuntimeError):
    """Report an absent, incompatible, or unsafe engine artifact."""


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """Hold physical model files without changing their declarative identity."""

    model_path: Path
    mmproj_path: Path | None


@dataclass(frozen=True, slots=True)
class EngineStatus:
    """Describe the active managed engine and its compatibility with the lock."""

    is_active: bool
    release: str | None
    backend: str | None
    executable: Path | None
    is_compatible: bool
    differences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InstallProgressEvent:
    """Describe one truthful managed-engine installation progress update."""

    stage: InstallStage
    detail: str | None = None
    item_index: int | None = None
    item_count: int | None = None
    completed_bytes: int | None = None
    total_bytes: int | None = None
    is_cached: bool = False
    percent: int | None = None


InstallProgress = Callable[[InstallProgressEvent], None]


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Report the selected installation and whether this invocation changed it."""

    status: EngineStatus
    was_installed: bool


@dataclass(frozen=True, slots=True)
class Activation:
    """Describe one promoted installation ready to become current."""

    release: str
    backend: Backend
    executable: Path


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


def _sha256(path: Path) -> str:
    """Hash one artifact incrementally so multi-GiB GGUF files are never read into memory."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EngineError(f"cannot read model artifact {path}: {error}") from error
    return digest.hexdigest()


def _verify_artifact(path: Path, specification: JsonObject) -> Path:
    """Require the locked filename, exact byte size, and SHA-256 before startup."""
    if path.name != specification["filename"]:
        raise EngineError(f"model artifact must be named {specification['filename']!r}: {path}")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise EngineError(f"model artifact is absent or unreadable: {path}: {error}") from error
    if size != specification["size_bytes"]:
        raise EngineError(f"model artifact has unexpected size: {path}")
    if _sha256(path) != specification["sha256"]:
        raise EngineError(f"model artifact checksum does not match engine.lock: {path}")
    return path.absolute()


def _verify_custom_model(path: Path) -> Path:
    """Require a readable GGUF for an identity with no pinned artifact contract."""
    if path.suffix.casefold() != ".gguf" or not path.is_file():
        raise EngineError(f"model_path must be a readable GGUF file: {path}")
    try:
        with path.open("rb") as source:
            source.read(1)
    except OSError as error:
        raise EngineError(f"model_path must be readable: {path}: {error}") from error
    return path.resolve()


def resolve_model(config: Config, lock: JsonObject, require_vision: bool = False) -> ResolvedModel:
    """Resolve locally without writes, pinned to the lock revision for the default model."""
    artifact = cast(JsonObject, lock["default_model_artifact"])
    if config.model != lock["default_model"]:
        if config.model_path is None:
            raise EngineError("a non-default model requires an explicit model_path")
        return ResolvedModel(_verify_custom_model(config.model_path), None)
    if config.model_path is not None:
        message = "model_path is only accepted for a non-default model identity"
        raise EngineError(message)
    repository = cast(str, artifact["repository"]).replace("/", "--")
    snapshot = _hf_cache_dir(os.environ) / f"models--{repository}" / "snapshots"
    snapshot /= cast(str, artifact["revision"])
    model_path = snapshot / cast(str, artifact["filename"])
    verified_model = _verify_artifact(model_path, artifact)
    if not require_vision:
        return ResolvedModel(verified_model, None)
    mmproj = cast(JsonObject, artifact["mmproj"])
    mmproj_path = model_path.parent / cast(str, mmproj["filename"])
    return ResolvedModel(verified_model, _verify_artifact(mmproj_path, mmproj))


def _expand(tokens: object, values: dict[str, str]) -> list[str]:
    """Expand complete placeholder tokens without interpreting engine option semantics."""
    expanded: list[str] = []
    for token in cast(list[str], tokens):
        if token.startswith("{") and token.endswith("}"):
            name = token[1:-1]
            if name not in values:
                raise EngineError(f"engine command requires unavailable placeholder {name!r}")
            expanded.append(values[name])
        else:
            expanded.append(token)
    return expanded


def _values(plan: LaunchPlan) -> dict[str, str]:
    """Serialize plan values for exact lock placeholder substitution."""
    values = {
        "model_path": str(plan.model_path),
        "ctx": str(plan.ctx),
        "temp": str(plan.mode.sampling.temp),
        "top_p": str(plan.mode.sampling.top_p),
        "top_k": str(plan.mode.sampling.top_k),
        "port": str(plan.port),
    }
    optional = ("min_p", "presence_penalty", "repeat_penalty")
    for name in optional:
        value = getattr(plan.mode.sampling, name)
        if value is not None:
            values[name] = str(value)
    if plan.mmproj_path is not None:
        values["mmproj"] = str(plan.mmproj_path)
    if plan.n_cpu_moe is not None:
        values["n_cpu_moe"] = str(plan.n_cpu_moe)
    return values


def _optional_mode_arrays(plan: LaunchPlan, command: JsonObject) -> list[object]:
    """Emit prepared mode/v2 arrays only when validated mode values are present."""
    extended = cast(JsonObject, command["extended_sampling_args"])
    arrays = [
        extended[name]
        for name in ("min_p", "presence_penalty", "repeat_penalty")
        if getattr(plan.mode.sampling, name) is not None
    ]
    reasoning = plan.mode.sampling.reasoning
    if reasoning is not None:
        arrays.append(cast(JsonObject, command["reasoning_args"])[reasoning])
    return arrays


def _contract_arrays(plan: LaunchPlan, command: JsonObject) -> tuple[object, ...]:
    """Select explicit behavior, speculative, vision, and backend arrays."""
    sampling = cast(JsonObject, command["sampling_args"])
    ui = cast(JsonObject, command["ui_args"])
    vision = cast(JsonObject, command["vision_args"])
    backends = cast(JsonObject, command["backend_args"])
    arrays = [command["model_args"], command["context_args"]]
    arrays.extend(sampling[name] for name in ("temp", "top_p", "top_k"))
    arrays.extend(_optional_mode_arrays(plan, command))
    arrays.extend((command["network_args"], command["metrics_args"], command["fixed_args"]))
    arrays.append(cast(JsonObject, command["speculative_args"])[plan.speculative])
    arrays.extend(
        (command["post_speculative_args"], ui["enabled" if plan.mode.services.ui else "disabled"])
    )
    arrays.append(vision["enabled" if plan.mode.services.vision else "disabled"])
    arrays.append(backends[plan.backend])
    return tuple(arrays)


def build_command(executable: Path, plan: LaunchPlan, lock: JsonObject) -> tuple[str, ...]:
    """Build a complete shell-free command and enforce verified_flags defensively.

    The flag vocabulary and its order come only from the lock: `command_contract_sha256` binds
    published calibration records to these exact bytes, so nothing here may be reordered or
    rewritten without invalidating measured evidence.
    """
    command = cast(JsonObject, lock["command_contract"])
    values = _values(plan)
    arguments: list[str] = [str(executable)]
    for tokens in _contract_arrays(plan, command):
        arguments.extend(_expand(tokens, values))
    verified = set(cast(list[str], lock["verified_flags"]))
    emitted = {token for token in arguments[1:] if token.startswith("-")}
    unknown = sorted(emitted - verified)
    if unknown:
        raise EngineError(f"engine command emitted flags outside engine.lock: {unknown}")
    return tuple(arguments)


def _probe(executable: Path, contract: JsonObject) -> str:
    """Run one bounded version or help probe without a shell."""
    args = [str(executable), *cast(list[str], contract["args"])]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
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


def _read_manifest(engine_root: Path) -> JsonObject | None:
    """Decode the current manifest without creating its parent directory."""
    path = engine_root / "current.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EngineError(f"managed engine manifest is invalid: {path}: {error}") from error
    if not isinstance(value, dict):
        raise EngineError(f"managed engine manifest must be an object: {path}")
    return value


def _resolve_executable(engine_root: Path, manifest: JsonObject) -> Path:
    """Resolve a relative executable only below immutable managed installations."""
    if manifest.get("schema") != _MANAGED_SCHEMA:
        raise EngineError(f"managed engine manifest schema must equal {_MANAGED_SCHEMA!r}")
    relative = manifest.get("executable")
    if not isinstance(relative, str):
        raise EngineError("managed engine executable must be a relative path")
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    is_unsafe = (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
    )
    if is_unsafe:
        raise EngineError("managed engine executable must be a safe relative path")
    executable = engine_root.joinpath(*posix.parts).resolve()
    installations = (engine_root / "installations").resolve()
    if not executable.is_relative_to(installations):
        raise EngineError("managed engine executable escapes the installations directory")
    return executable


def _managed_candidate(engine_root: Path, backend: str, lock: JsonObject) -> Path | None:
    """Return the active executable only when release and backend match the launch request."""
    manifest = _read_manifest(engine_root)
    if manifest is None:
        return None
    if manifest.get("release") != lock["release"] or manifest.get("backend") != backend:
        raise EngineError("managed engine release or backend differs from engine.lock")
    return _resolve_executable(engine_root, manifest)


def _lock_differences(executable: Path, manifest: JsonObject, lock: JsonObject) -> tuple[str, ...]:
    """List how the active manifest diverges, probing the binary only when identity agrees."""
    release = manifest.get("release")
    backend = manifest.get("backend")
    differences: list[str] = []
    if release != lock.get("release"):
        differences.append(f"release {release!r} differs from lock {lock.get('release')!r}")
    if backend not in {"cpu", "cuda"}:
        differences.append(f"backend {backend!r} is invalid")
    if differences:
        return tuple(differences)
    try:
        verify_engine(executable, lock)
    except EngineError as error:
        return (str(error),)
    return ()


def inspect_status(engine_root: Path, lock: JsonObject) -> EngineStatus:
    """Describe absence, corruption, lock differences, and executable compatibility."""
    try:
        manifest = _read_manifest(engine_root)
        if manifest is None:
            return EngineStatus(False, None, None, None, False, ("not installed",))
        executable = _resolve_executable(engine_root, manifest)
        differences = _lock_differences(executable, manifest, lock)
        release = manifest.get("release")
        backend = manifest.get("backend")
        return EngineStatus(
            True,
            release if isinstance(release, str) else None,
            backend if isinstance(backend, str) else None,
            executable,
            not differences,
            differences,
        )
    except EngineError as error:
        return EngineStatus(False, None, None, None, False, (str(error),))


def _manifest_bytes(engine_root: Path, activation: Activation) -> bytes:
    """Serialize one activation with an executable relative to the managed root."""
    installations = (engine_root / "installations").resolve()
    executable = activation.executable.resolve()
    if not executable.is_relative_to(installations):
        raise EngineError("cannot activate an executable outside managed installations")
    value = {
        "schema": _MANAGED_SCHEMA,
        "release": activation.release,
        "backend": activation.backend,
        "executable": executable.relative_to(engine_root.resolve()).as_posix(),
    }
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def activate(engine_root: Path, activation: Activation) -> None:
    """Flush and atomically replace ``current.json`` without touching the old installation."""
    engine_root.mkdir(parents=True, exist_ok=True)
    target = engine_root / "current.json"
    temporary = engine_root / f".current-{uuid4().hex}.tmp"
    payload = _manifest_bytes(engine_root, activation)
    try:
        with temporary.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(target)
    except OSError as error:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise EngineError(f"cannot activate managed engine: {error}") from error


def locate(config: Config, backend: str, lock: JsonObject | None = None) -> Path:
    """Locate and verify explicit, PATH, then managed engine candidates in normative order."""
    selected_lock = load_engine_lock() if lock is None else lock
    if config.engine_path is not None:
        return verify_engine(config.engine_path, selected_lock)
    name = "llama-server.exe" if os.name == "nt" else "llama-server"
    if discovered := shutil.which(name):
        return verify_engine(Path(discovered), selected_lock)
    managed = _managed_candidate(data_dir() / "engine", backend, selected_lock)
    if managed is not None:
        return verify_engine(managed, selected_lock)
    raise EngineError(
        "no compatible llama-server found; set engine_path or install the pinned engine"
    )


def engine_status(lock: JsonObject | None = None) -> EngineStatus:
    """Inspect the active managed engine without creating files or directories."""
    selected_lock = load_engine_lock() if lock is None else lock
    return inspect_status(data_dir() / "engine", selected_lock)


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
    """Install and activate the complete lock-selected engine for this host.

    The installer is imported here because it builds on this module's lock, verification, and
    activation contracts; importing it at module scope would close an import cycle.
    """
    from bora_workbench._engine_install import InstallRequest, install_managed_engine

    # Read the lock before inspecting the host: on a machine that is both unsupported and carries an
    # unreadable packaged lock, the broken lock is the failure the user must hear about first.
    # Evaluating these inside the constructor would reverse that order.
    lock = load_engine_lock()
    platform_key = _platform_key()
    request = InstallRequest(
        platform_key,
        backend,
        force,
        data_dir() / "engine",
        cache_dir() / "llama.cpp",
        lock,
        progress,
    )
    return install_managed_engine(request)
