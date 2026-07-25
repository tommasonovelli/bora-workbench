"""Tests for extraction confinement and forbidden archive member types."""

from __future__ import annotations

import io
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import cast

import pytest

from bora_workbench._engine_archive import ExtractionRequest, extract_asset
from bora_workbench._engine_types import ArchiveKind, EngineAsset, EngineError, TransferProgress


def asset(archive: str) -> EngineAsset:
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
    extract_asset(ExtractionRequest(asset("zip"), zip_path, zip_out))

    tar_path = tmp_path / "engine.tar.gz"
    with tarfile.open(tar_path, "w:gz") as archive:
        info = tarfile.TarInfo("bin/llama-server")
        info.size = len(b"ubuntu")
        info.mode = 0o755
        archive.addfile(info, io.BytesIO(b"ubuntu"))
    tar_out = tmp_path / "tar-out"
    extract_asset(ExtractionRequest(asset("tar.gz"), tar_path, tar_out))

    assert (zip_out / "bin/llama-server.exe").read_bytes() == b"windows"
    assert (tar_out / "bin/llama-server").read_bytes() == b"ubuntu"


def test_reports_uncompressed_extraction_bytes(tmp_path) -> None:
    """Drive a determinate extraction bar from measured regular-member bytes."""
    archive_path = tmp_path / "engine.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("first.bin", b"first")
        archive.writestr("second.bin", b"second")
    observed: list[TransferProgress] = []
    request = ExtractionRequest(asset("zip"), archive_path, tmp_path / "out", observed.append)

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
    extract_asset(ExtractionRequest(asset("tar.gz"), path, destination))

    assert (destination / "lib/libengine.so.1").read_bytes() == b"library"
    assert observed == [(destination / "lib/libengine.so", "libengine.so.1")]


def test_rejects_zip_traversal_and_symlinks(tmp_path) -> None:
    """Refuse ZIP members that escape staging or encode a Unix symlink."""
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../outside", b"bad")
    with pytest.raises(EngineError, match="unsafe archive member"):
        extract_asset(ExtractionRequest(asset("zip"), traversal, tmp_path / "traversal-out"))

    linked = tmp_path / "link.zip"
    info = zipfile.ZipInfo("llama-server")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(linked, "w") as archive:
        archive.writestr(info, "outside")
    with pytest.raises(EngineError, match="links are forbidden"):
        extract_asset(ExtractionRequest(asset("zip"), linked, tmp_path / "link-out"))


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
        extract_asset(ExtractionRequest(asset("tar.gz"), path, tmp_path / "out"))
