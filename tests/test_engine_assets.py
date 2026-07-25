"""Tests for exact asset selection, verified downloads, and confined archive extraction."""

from __future__ import annotations

import hashlib
import io
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import cast

import pytest

import bora_workbench._engine_assets as assets
import bora_workbench.engine as engine
from bora_workbench._engine_assets import (
    ArchiveKind,
    EngineAsset,
    ExtractionRequest,
    TransferProgress,
    extract_asset,
    select_assets,
)
from bora_workbench.engine import EngineError, load_engine_lock
from bora_workbench.validation import validate_resources
from tests.content_fixtures import copy_resource_root, read_json, write_json


@pytest.mark.parametrize(
    ("os_name", "backend", "roles"),
    [
        ("ubuntu", "cpu", {"server"}),
        ("ubuntu", "cuda", {"source"}),
        ("windows", "cpu", {"server"}),
        ("windows", "cuda", {"server", "cuda-runtime"}),
    ],
)
def test_selects_exact_verified_asset_matrix(os_name, backend, roles) -> None:
    """Select only the roles verified by Spike 0 for each supported target pair."""
    selected = select_assets(load_engine_lock(), os_name, backend)

    assert {asset.role for asset in selected} == roles
    assert all(asset.url.startswith("https://") for asset in selected)


def test_runtime_refuses_incomplete_or_missing_asset_sets() -> None:
    """Prevent managed installation when completeness or a target role is absent."""
    lock = load_engine_lock()
    lock["assets_complete"] = False
    with pytest.raises(EngineError, match="incomplete"):
        select_assets(lock, "ubuntu", "cpu")

    lock = load_engine_lock()
    lock["assets"] = [item for item in lock["assets"] if item["role"] != "cuda-runtime"]
    with pytest.raises(EngineError, match="exact windows/cuda"):
        select_assets(lock, "windows", "cuda")


def test_platform_selection_rejects_unsupported_architecture_and_linux(monkeypatch) -> None:
    """Never apply x86-64 Ubuntu assets to another architecture or Linux distribution."""
    monkeypatch.setattr(engine.platform, "machine", lambda: "aarch64")
    with pytest.raises(EngineError, match="requires x86-64"):
        engine._platform_key()

    monkeypatch.setattr(engine.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(engine.platform, "system", lambda: "Linux")
    monkeypatch.setattr(engine.platform, "freedesktop_os_release", lambda: {"ID": "debian"})
    with pytest.raises(EngineError, match="requires Ubuntu"):
        engine._platform_key()


def test_validation_rejects_unsafe_asset_metadata(tmp_path) -> None:
    """Reject non-HTTPS downloads, malformed digests, and executable traversal."""
    root = copy_resource_root(tmp_path)
    path = root / "engine.lock"
    lock = read_json(path)
    asset = lock["assets"][0]
    asset["url"] = "http://example.invalid/engine.tar.gz"
    asset["sha256"] = "invalid"
    asset["executable"] = "../llama-server"
    write_json(path, lock)

    result = validate_resources(root)
    paths = {issue.field_path for issue in result.errors}

    assert "$.assets[0].url" in paths
    assert "$.assets[0].sha256" in paths
    assert "$.assets[0].executable" in paths


def test_validation_binds_source_url_and_complete_role_matrix(tmp_path) -> None:
    """Require the pinned source commit and every exact supported role set."""
    root = copy_resource_root(tmp_path)
    path = root / "engine.lock"
    lock = read_json(path)
    source = next(item for item in lock["assets"] if item["role"] == "source")
    source["url"] = "https://example.invalid/source.tar.gz"
    lock["assets"] = [item for item in lock["assets"] if item["role"] != "cuda-runtime"]
    write_json(path, lock)

    result = validate_resources(root)
    messages = {issue.message for issue in result.errors}

    assert "source URL must contain the pinned source_commit" in messages
    assert any("windows/cuda" in message for message in messages)


class FakeResponse:
    """Provide the bounded httpx streaming surface used by the downloader."""

    def __init__(self, chunks, url="https://example.invalid/engine.zip", total=None):
        """Store deterministic chunks, final URL, length, or a failing iterator."""
        self.chunks = chunks
        self.url = url
        self.headers = {} if total is None else {"Content-Length": str(total)}

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


def pinned_asset(payload: bytes, digest: str | None = None) -> EngineAsset:
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
        assets.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse([payload[:8], payload[8:]], total=len(payload)),
    )
    observed: list[TransferProgress] = []

    path = assets.download_asset(pinned_asset(payload), tmp_path, observed.append)

    assert path.read_bytes() == payload
    assert observed == [
        TransferProgress(0, len(payload)),
        TransferProgress(8, len(payload)),
        TransferProgress(len(payload), len(payload)),
    ]
    assert not list(tmp_path.glob("*.part"))


def test_rejects_checksum_mismatch_and_removes_partial(tmp_path, monkeypatch) -> None:
    """Never retain or promote bytes whose SHA-256 differs from ``engine.lock``."""
    monkeypatch.setattr(
        assets.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse([b"wrong"]),
    )

    with pytest.raises(EngineError, match="checksum mismatch"):
        assets.download_asset(pinned_asset(b"expected"), tmp_path)

    assert not any(tmp_path.iterdir())


def test_interrupted_download_removes_partial(tmp_path, monkeypatch) -> None:
    """Clean the managed partial file when streaming stops before completion."""

    def interrupted():
        """Yield one partial chunk before simulating a broken connection."""
        yield b"partial"
        raise OSError("connection interrupted")

    monkeypatch.setattr(
        assets.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse(interrupted()),
    )

    with pytest.raises(EngineError, match="download failed"):
        assets.download_asset(pinned_asset(b"complete"), tmp_path)

    assert not any(tmp_path.iterdir())


def test_rejects_redirect_downgrade_to_plain_http(tmp_path, monkeypatch) -> None:
    """Keep TLS mandatory even when an HTTPS endpoint responds with a downgrade redirect."""
    monkeypatch.setattr(
        assets.httpx,
        "stream",
        lambda *args, **kwargs: FakeResponse([b"payload"], "http://example.invalid/engine.zip"),
    )

    with pytest.raises(EngineError, match="redirected away from HTTPS"):
        assets.download_asset(pinned_asset(b"payload"), tmp_path)

    assert not any(tmp_path.iterdir())


def test_reuses_only_a_valid_cached_archive(tmp_path, monkeypatch) -> None:
    """Avoid a request when the existing final cache file already matches the lock."""
    payload = b"cached"
    cached = Path(tmp_path, "engine.zip")
    cached.write_bytes(payload)
    monkeypatch.setattr(
        assets.httpx,
        "stream",
        lambda *args, **kwargs: pytest.fail("network must not be used"),
    )

    observed: list[TransferProgress] = []

    assert assets.download_asset(pinned_asset(payload), tmp_path, observed.append) == cached
    assert observed == [TransferProgress(len(payload), len(payload), True)]


def archive_asset(archive: str) -> EngineAsset:
    """Build one synthetic CPU asset for offline archive tests."""
    filename = "engine.zip" if archive == "zip" else "engine.tar.gz"
    return EngineAsset(
        "windows" if archive == "zip" else "ubuntu",
        "cpu",
        "server",
        filename,
        f"https://example.invalid/{filename}",
        "0" * 64,
        cast(ArchiveKind, archive),
        "llama-server",
    )


def test_extracts_regular_zip_and_tar_files(tmp_path) -> None:
    """Extract ordinary files from both lock-supported archive formats."""
    zip_path = tmp_path / "engine.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("bin/llama-server.exe", b"windows")
    zip_out = tmp_path / "zip-out"
    extract_asset(ExtractionRequest(archive_asset("zip"), zip_path, zip_out))

    tar_path = tmp_path / "engine.tar.gz"
    with tarfile.open(tar_path, "w:gz") as archive:
        info = tarfile.TarInfo("bin/llama-server")
        info.size = len(b"ubuntu")
        info.mode = 0o755
        archive.addfile(info, io.BytesIO(b"ubuntu"))
    tar_out = tmp_path / "tar-out"
    extract_asset(ExtractionRequest(archive_asset("tar.gz"), tar_path, tar_out))

    assert (zip_out / "bin/llama-server.exe").read_bytes() == b"windows"
    assert (tar_out / "bin/llama-server").read_bytes() == b"ubuntu"


def test_reports_uncompressed_extraction_bytes(tmp_path) -> None:
    """Drive a determinate extraction bar from measured regular-member bytes."""
    archive_path = tmp_path / "engine.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("first.bin", b"first")
        archive.writestr("second.bin", b"second")
    observed: list[TransferProgress] = []
    request = ExtractionRequest(
        archive_asset("zip"), archive_path, tmp_path / "out", observed.append
    )

    extract_asset(request)

    assert observed[0] == TransferProgress(0, 11)
    assert observed[-1] == TransferProgress(11, 11)


def test_accepts_confined_declared_tar_symlink(tmp_path, monkeypatch) -> None:
    """Allow only the internal relative symlinks required by the verified Ubuntu CPU asset."""
    path = tmp_path / "safe-link.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        file_info = tarfile.TarInfo("lib/libengine.so.1")
        file_info.size = len(b"library")
        archive.addfile(file_info, io.BytesIO(b"library"))
        link_info = tarfile.TarInfo("lib/libengine.so")
        link_info.type = tarfile.SYMTYPE
        link_info.linkname = "libengine.so.1"
        archive.addfile(link_info)
    observed: list[tuple[Path, str]] = []

    def capture_symlink(target, link_name):
        """Record safe symlink creation without requiring Windows symlink privileges."""
        observed.append((target, link_name))

    monkeypatch.setattr(Path, "symlink_to", capture_symlink)
    destination = tmp_path / "safe-link-out"
    extract_asset(ExtractionRequest(archive_asset("tar.gz"), path, destination))

    assert (destination / "lib/libengine.so.1").read_bytes() == b"library"
    assert observed == [(destination / "lib/libengine.so", "libengine.so.1")]


def test_rejects_zip_traversal_and_symlinks(tmp_path) -> None:
    """Refuse ZIP members that escape staging or encode a Unix symlink."""
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../outside", b"bad")
    with pytest.raises(EngineError, match="unsafe archive member"):
        extract_asset(
            ExtractionRequest(archive_asset("zip"), traversal, tmp_path / "traversal-out")
        )

    linked = tmp_path / "link.zip"
    info = zipfile.ZipInfo("llama-server")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(linked, "w") as archive:
        archive.writestr(info, "outside")
    with pytest.raises(EngineError, match="links are forbidden"):
        extract_asset(ExtractionRequest(archive_asset("zip"), linked, tmp_path / "link-out"))


@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_rejects_escaping_symlink_and_all_hardlinks(tmp_path, link_type) -> None:
    """Refuse escaping symbolic links and hardlinks rather than following their targets."""
    path = tmp_path / f"link-{link_type!r}.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("llama-server")
        info.type = link_type
        info.linkname = "../outside"
        archive.addfile(info)

    with pytest.raises(EngineError, match=r"unsafe archive member|non-regular archive member"):
        extract_asset(ExtractionRequest(archive_asset("tar.gz"), path, tmp_path / "out"))
