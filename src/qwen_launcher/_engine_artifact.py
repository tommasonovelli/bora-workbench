"""Verify local GGUF artifacts without network access or filesystem writes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from qwen_launcher.engine import EngineError, JsonObject


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


def verify_artifact(path: Path, specification: JsonObject) -> Path:
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


def verify_custom_model(path: Path) -> Path:
    """Require a readable GGUF for an identity with no pinned artifact contract."""
    if path.suffix.casefold() != ".gguf" or not path.is_file():
        raise EngineError(f"model_path must be a readable GGUF file: {path}")
    try:
        with path.open("rb") as source:
            source.read(1)
    except OSError as error:
        raise EngineError(f"model_path must be readable: {path}: {error}") from error
    return path.resolve()
