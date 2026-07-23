"""Extract pinned ZIP and tar archives without trusting member paths or links."""

from __future__ import annotations

import stat
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from qwen_launcher._engine_transfer import ByteTracker
from qwen_launcher._engine_types import (
    EngineAsset,
    EngineError,
    TransferProgressCallback,
)


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    """Group one verified archive, its staging destination, and byte reporter."""

    asset: EngineAsset
    archive_path: Path
    destination: Path
    progress: TransferProgressCallback | None = None


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


def _extract_zip(request: ExtractionRequest) -> None:
    """Extract regular ZIP files while reporting their total uncompressed bytes."""
    with zipfile.ZipFile(request.archive_path) as archive:
        members = archive.infolist()
        tracker = ByteTracker(sum(member.file_size for member in members), request.progress)
        tracker.start()
        for member in members:
            target = _target_path(request.destination, member.filename)
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
                tracker.copy(source, output)


def _member_key(name: str) -> str:
    """Normalize one already validated tar member name for exact link lookup."""
    return PurePosixPath(*_member_parts(name)).as_posix()


def _safe_symlink_target(
    destination: Path, member: tarfile.TarInfo, members: dict[str, tarfile.TarInfo]
) -> Path:
    """Resolve a relative tar symlink only to another declared file or safe symlink."""
    link_parts = _member_parts(member.linkname)
    parent = PurePosixPath(_member_key(member.name)).parent
    target_key = (parent / PurePosixPath(*link_parts)).as_posix()
    linked_member = members.get(target_key)
    if linked_member is None or not (linked_member.isfile() or linked_member.issym()):
        raise EngineError(f"tar symlink target is not a declared file: {member.linkname!r}")
    linked_path = destination.joinpath(*PurePosixPath(target_key).parts).resolve()
    if not linked_path.is_relative_to(destination.resolve()):
        raise EngineError(f"tar symlink escapes extraction root: {member.name!r}")
    return linked_path


def _create_tar_symlink(
    destination: Path, member: tarfile.TarInfo, members: dict[str, tarfile.TarInfo]
) -> None:
    """Create one validated internal tar symlink after regular files exist."""
    _safe_symlink_target(destination, member, members)
    target = _target_path(destination, member.name)
    _prepare_file(target, member.name)
    target.symlink_to(member.linkname)


def _extract_tar(request: ExtractionRequest) -> None:
    """Extract safe tar members while reporting their total regular-file bytes."""
    with tarfile.open(request.archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        indexed = {_member_key(member.name): member for member in members}
        total_bytes = sum(member.size for member in members if member.isfile())
        tracker = ByteTracker(total_bytes, request.progress)
        tracker.start()
        symlinks: list[tarfile.TarInfo] = []
        for member in members:
            target = _target_path(request.destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.issym():
                _safe_symlink_target(request.destination, member, indexed)
                symlinks.append(member)
            elif member.isfile():
                source = archive.extractfile(member)
                if source is None:
                    raise EngineError(f"cannot read archive member: {member.name!r}")
                _prepare_file(target, member.name)
                with source, target.open("xb") as output:
                    tracker.copy(source, output)
                target.chmod(member.mode & 0o777)
            else:
                raise EngineError(f"non-regular archive member: {member.name!r}")
        for member in symlinks:
            _create_tar_symlink(request.destination, member, indexed)


def extract_asset(request: ExtractionRequest) -> None:
    """Extract one verified asset using only its lock-declared archive format."""
    request.destination.mkdir(parents=True, exist_ok=True)
    try:
        if request.asset.archive == "zip":
            _extract_zip(request)
        elif request.asset.archive == "tar.gz":
            _extract_tar(request)
        else:
            raise EngineError(f"unsupported archive format: {request.asset.archive}")
    except (tarfile.TarError, zipfile.BadZipFile, OSError) as error:
        raise EngineError(f"cannot safely extract {request.asset.filename}: {error}") from error
