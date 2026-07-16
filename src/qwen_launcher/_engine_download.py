"""Download pinned engine archives with TLS, streaming, and mandatory SHA-256."""

from __future__ import annotations

import hashlib
import os
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from qwen_launcher._engine_types import EngineAsset, EngineError

_CHUNK_SIZE = 1024 * 1024


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discard(path: Path) -> None:
    """Remove one managed partial file while tolerating an absent path."""
    with suppress(FileNotFoundError):
        path.unlink()


def _stream_to_file(asset: EngineAsset, partial: Path) -> str:
    """Stream one HTTPS response into a partial file and return its digest."""
    digest = hashlib.sha256()
    timeout = httpx.Timeout(60.0, connect=10.0)
    with httpx.stream("GET", asset.url, follow_redirects=True, timeout=timeout) as response:
        response.raise_for_status()
        if urlparse(str(response.url)).scheme != "https":
            raise EngineError(f"download redirected away from HTTPS: {response.url}")
        with partial.open("xb") as output:
            for chunk in response.iter_bytes(_CHUNK_SIZE):
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
    return digest.hexdigest()


def download_asset(asset: EngineAsset, cache_root: Path) -> Path:
    """Return a verified cached archive, downloading through a unique ``.part`` file."""
    partial = cache_root / f".{asset.filename}-{uuid4().hex}.part"
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        target = cache_root / asset.filename
        if target.is_symlink():
            target.unlink()
        if target.is_file() and file_sha256(target) == asset.sha256:
            return target
        if target.exists() and not target.is_file():
            raise EngineError(f"managed cache target is not a regular file: {target}")
        if target.exists():
            target.unlink()
        digest = _stream_to_file(asset, partial)
        if digest != asset.sha256:
            raise EngineError(
                f"checksum mismatch for {asset.filename}: expected {asset.sha256}, got {digest}"
            )
        partial.replace(target)
        return target
    except (EngineError, OSError, httpx.HTTPError) as error:
        _discard(partial)
        if isinstance(error, EngineError):
            raise
        raise EngineError(f"download failed for {asset.url}: {error}") from error
