"""Tests for streamed engine downloads and mandatory checksum verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import qwen_launcher._engine_download as downloader
from qwen_launcher._engine_types import EngineAsset, EngineError


class FakeResponse:
    """Provide the bounded httpx streaming surface used by the downloader."""

    def __init__(self, chunks, url="https://example.invalid/engine.zip"):
        """Store deterministic chunks, final URL, or an iterator that raises."""
        self.chunks = chunks
        self.url = url

    def __enter__(self):
        """Enter the fake response context."""
        return self

    def __exit__(self, *args):
        """Leave the fake response context without suppressing failures."""
        return False

    def raise_for_status(self):
        """Represent a successful HTTP response."""

    def iter_bytes(self, chunk_size):
        """Yield configured chunks while accepting the production chunk size."""
        del chunk_size
        yield from self.chunks


def asset(payload: bytes, digest: str | None = None) -> EngineAsset:
    """Build one synthetic lock asset with a digest for the provided payload."""
    sha256 = hashlib.sha256(payload).hexdigest() if digest is None else digest
    return EngineAsset(
        "windows",
        "cpu",
        "server",
        "engine.zip",
        "https://example.invalid/engine.zip",
        sha256,
        "zip",
        "llama-server.exe",
    )


def test_streams_to_part_then_promotes_verified_download(tmp_path, monkeypatch) -> None:
    """Expose only the final archive after all streamed bytes match the lock digest."""
    payload = b"verified engine archive"
    monkeypatch.setattr(
        downloader.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse([payload[:8], payload[8:]]),
    )

    path = downloader.download_asset(asset(payload), tmp_path)

    assert path.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))


def test_rejects_checksum_mismatch_and_removes_partial(tmp_path, monkeypatch) -> None:
    """Never retain or promote bytes whose SHA-256 differs from ``engine.lock``."""
    monkeypatch.setattr(
        downloader.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse([b"wrong"]),
    )

    with pytest.raises(EngineError, match="checksum mismatch"):
        downloader.download_asset(asset(b"expected"), tmp_path)

    assert not any(tmp_path.iterdir())


def test_interrupted_download_removes_partial(tmp_path, monkeypatch) -> None:
    """Clean the managed partial file when streaming stops before completion."""

    def interrupted():
        """Yield one partial chunk before simulating a broken connection."""
        yield b"partial"
        raise OSError("connection interrupted")

    monkeypatch.setattr(
        downloader.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse(interrupted()),
    )

    with pytest.raises(EngineError, match="download failed"):
        downloader.download_asset(asset(b"complete"), tmp_path)

    assert not any(tmp_path.iterdir())


def test_rejects_redirect_downgrade_to_plain_http(tmp_path, monkeypatch) -> None:
    """Keep TLS mandatory even when an HTTPS endpoint responds with a downgrade redirect."""
    monkeypatch.setattr(
        downloader.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse([b"payload"], "http://example.invalid/engine.zip"),
    )

    with pytest.raises(EngineError, match="redirected away from HTTPS"):
        downloader.download_asset(asset(b"payload"), tmp_path)

    assert not any(tmp_path.iterdir())


def test_reuses_only_a_valid_cached_archive(tmp_path, monkeypatch) -> None:
    """Avoid a request when the existing final cache file already matches the lock."""
    payload = b"cached"
    cached = Path(tmp_path, "engine.zip")
    cached.write_bytes(payload)
    monkeypatch.setattr(
        downloader.httpx,
        "stream",
        lambda *args, **kwargs: pytest.fail("network must not be used"),
    )

    assert downloader.download_asset(asset(payload), tmp_path) == cached
