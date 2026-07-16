"""Tests for extraction confinement and forbidden archive member types."""

from __future__ import annotations

import io
import stat
import tarfile
import zipfile
from typing import cast

import pytest

from qwen_launcher._engine_archive import extract_asset
from qwen_launcher._engine_types import ArchiveKind, EngineAsset, EngineError


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
    extract_asset(asset("zip"), zip_path, zip_out)

    tar_path = tmp_path / "engine.tar.gz"
    with tarfile.open(tar_path, "w:gz") as archive:
        info = tarfile.TarInfo("bin/llama-server")
        info.size = len(b"ubuntu")
        info.mode = 0o755
        archive.addfile(info, io.BytesIO(b"ubuntu"))
    tar_out = tmp_path / "tar-out"
    extract_asset(asset("tar.gz"), tar_path, tar_out)

    assert (zip_out / "bin/llama-server.exe").read_bytes() == b"windows"
    assert (tar_out / "bin/llama-server").read_bytes() == b"ubuntu"


def test_rejects_zip_traversal_and_symlinks(tmp_path) -> None:
    """Refuse ZIP members that escape staging or encode a Unix symlink."""
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../outside", b"bad")
    with pytest.raises(EngineError, match="unsafe archive member"):
        extract_asset(asset("zip"), traversal, tmp_path / "traversal-out")

    linked = tmp_path / "link.zip"
    info = zipfile.ZipInfo("llama-server")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(linked, "w") as archive:
        archive.writestr(info, "outside")
    with pytest.raises(EngineError, match="links are forbidden"):
        extract_asset(asset("zip"), linked, tmp_path / "link-out")


@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_rejects_tar_symbolic_and_hard_links(tmp_path, link_type) -> None:
    """Refuse both link kinds before tarfile can resolve their targets."""
    path = tmp_path / f"link-{link_type!r}.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("llama-server")
        info.type = link_type
        info.linkname = "../outside"
        archive.addfile(info)

    with pytest.raises(EngineError, match="non-regular archive member"):
        extract_asset(asset("tar.gz"), path, tmp_path / "out")
