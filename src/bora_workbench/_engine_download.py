"""Download pinned engine archives with TLS, streaming, and mandatory SHA-256."""

from __future__ import annotations

import hashlib
import os
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from bora_workbench._engine_types import (
    EngineAsset,
    EngineError,
    TransferProgress,
    TransferProgressCallback,
)

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


def _content_length(response: httpx.Response) -> int | None:
    """Read optional response length for UX without weakening byte verification."""
    value = response.headers.get("Content-Length")
    try:
        total = int(value) if value is not None else None
    except ValueError:
        return None
    return total if total is not None and total >= 0 else None


def _stream_to_file(
    asset: EngineAsset, partial: Path, progress: TransferProgressCallback | None
) -> str:
    """Stream one HTTPS response into a partial file and report measured transfer bytes."""
    digest = hashlib.sha256()
    timeout = httpx.Timeout(60.0, connect=10.0)
    with httpx.stream("GET", asset.url, follow_redirects=True, timeout=timeout) as response:
        response.raise_for_status()
        if urlparse(str(response.url)).scheme != "https":
            raise EngineError(f"download redirected away from HTTPS: {response.url}")
        total, completed = _content_length(response), 0
        if progress is not None:
            progress(TransferProgress(0, total))
        with partial.open("xb") as output:
            for chunk in response.iter_bytes(_CHUNK_SIZE):
                output.write(chunk)
                digest.update(chunk)
                completed += len(chunk)
                if progress is not None:
                    progress(TransferProgress(completed, total))
            output.flush()
            os.fsync(output.fileno())
    if progress is not None and total is None:
        progress(TransferProgress(completed, completed))
    return digest.hexdigest()


def download_asset(
    asset: EngineAsset,
    cache_root: Path,
    progress: TransferProgressCallback | None = None,
) -> Path:
    """Return a verified cached archive, reporting bytes for download progress and ETA."""
    partial = cache_root / f".{asset.filename}-{uuid4().hex}.part"
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        target = cache_root / asset.filename
        if target.is_symlink():
            target.unlink()
        if target.is_file() and file_sha256(target) == asset.sha256:
            if progress is not None:
                size = target.stat().st_size
                progress(TransferProgress(size, size, True))
            return target
        if target.exists() and not target.is_file():
            raise EngineError(f"managed cache target is not a regular file: {target}")
        if target.exists():
            target.unlink()
        digest = _stream_to_file(asset, partial, progress)
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
