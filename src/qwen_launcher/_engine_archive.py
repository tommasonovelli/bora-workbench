"""Extract pinned ZIP and tar archives without trusting member paths or links."""

from __future__ import annotations

import shutil
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from qwen_launcher._engine_types import EngineAsset, EngineError


def _member_parts(name: str) -> tuple[str, ...]:
    """Return safe portable member components or reject an escaping name."""
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if (
        not name
        or "\\" in name
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise EngineError(f"unsafe archive member path: {name!r}")
    parts = tuple(part for part in posix.parts if part not in {"", "."})
    if not parts:
        raise EngineError(f"empty archive member path: {name!r}")
    return parts


def _target_path(destination: Path, name: str) -> Path:
    """Resolve one member below the extraction root as a second confinement check."""
    target = destination.joinpath(*_member_parts(name)).resolve()
    if not target.is_relative_to(destination.resolve()):
        raise EngineError(f"archive member escapes extraction root: {name!r}")
    return target


def _prepare_file(target: Path, name: str) -> None:
    """Create a member's parent while refusing to overwrite another member."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise EngineError(f"archive contains a duplicate member: {name!r}")


def _extract_zip(archive_path: Path, destination: Path) -> None:
    """Extract regular ZIP files and directories while rejecting Unix links."""
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = _target_path(destination, member.filename)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise EngineError(f"archive links are forbidden: {member.filename!r}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if mode and stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                raise EngineError(f"non-regular archive member: {member.filename!r}")
            _prepare_file(target, member.filename)
            with archive.open(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)


def _extract_tar(archive_path: Path, destination: Path) -> None:
    """Extract regular tar members without links, devices, or special files."""
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive:
            target = _target_path(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise EngineError(f"non-regular archive member: {member.name!r}")
            source = archive.extractfile(member)
            if source is None:
                raise EngineError(f"cannot read archive member: {member.name!r}")
            _prepare_file(target, member.name)
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(member.mode & 0o777)


def extract_asset(asset: EngineAsset, archive_path: Path, destination: Path) -> None:
    """Extract one verified asset using only its lock-declared archive format."""
    destination.mkdir(parents=True, exist_ok=True)
    try:
        if asset.archive == "zip":
            _extract_zip(archive_path, destination)
        elif asset.archive == "tar.gz":
            _extract_tar(archive_path, destination)
        else:
            raise EngineError(f"unsupported archive format: {asset.archive}")
    except (tarfile.TarError, zipfile.BadZipFile, OSError) as error:
        raise EngineError(f"cannot safely extract {asset.filename}: {error}") from error
