"""Read and atomically replace the managed-engine activation manifest."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

from qwen_launcher._engine_types import Backend, EngineError, EngineStatus

JsonObject = dict[str, object]
_SCHEMA = "managed-engine/v1"


@dataclass(frozen=True, slots=True)
class Activation:
    """Describe one promoted installation ready to become current."""

    release: str
    backend: Backend
    executable: Path


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
    if manifest.get("schema") != _SCHEMA:
        raise EngineError(f"managed engine manifest schema must equal {_SCHEMA!r}")
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


def managed_candidate(engine_root: Path, backend: str, lock: JsonObject) -> Path | None:
    """Return the active executable only when release and backend match the launch request."""
    manifest = _read_manifest(engine_root)
    if manifest is None:
        return None
    if manifest.get("release") != lock["release"] or manifest.get("backend") != backend:
        raise EngineError("managed engine release or backend differs from engine.lock")
    return _resolve_executable(engine_root, manifest)


def inspect_status(engine_root: Path, lock: JsonObject) -> EngineStatus:
    """Describe absence, corruption, lock differences, and executable compatibility."""
    try:
        manifest = _read_manifest(engine_root)
        if manifest is None:
            return EngineStatus(False, None, None, None, False, ("not installed",))
        executable = _resolve_executable(engine_root, manifest)
        release = manifest.get("release")
        backend = manifest.get("backend")
        differences: list[str] = []
        if release != lock.get("release"):
            differences.append(f"release {release!r} differs from lock {lock.get('release')!r}")
        if backend not in {"cpu", "cuda"}:
            differences.append(f"backend {backend!r} is invalid")
        if not differences:
            from qwen_launcher.engine import verify_engine

            try:
                verify_engine(executable, lock)
            except EngineError as error:
                differences.append(str(error))
        return EngineStatus(
            True,
            release if isinstance(release, str) else None,
            backend if isinstance(backend, str) else None,
            executable,
            not differences,
            tuple(differences),
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
        "schema": _SCHEMA,
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
