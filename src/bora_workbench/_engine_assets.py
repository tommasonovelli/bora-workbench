"""Select, download, and safely unpack the archives pinned by ``engine.lock``.

The module turns one lock asset declaration into verified bytes on disk (specification section
5.10). Every step is deliberately distrustful: only complete, exactly matching role sets may be
installed, downloads stay on HTTPS with a mandatory SHA-256, and archive members are confined to
the extraction root before anything is written.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tarfile
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO, Literal, cast
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx

from bora_workbench.engine import Backend, EngineError, JsonObject, PlatformKey

ArchiveKind = Literal["zip", "tar.gz"]
Role = Literal["server", "cuda-runtime", "source"]

_CHUNK_SIZE = 1024 * 1024
_MAX_REDIRECTS = 10
_ALLOWED_ROLES = {"server", "cuda-runtime", "source"}
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DEVICE = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.I)
# Ubuntu CUDA is the only pair compiled instead of downloaded: the pinned release publishes no
# Linux CUDA prebuilt, so the lock pins the commit archive as its source asset (specification
# section 5.10). Windows CUDA needs two roles because upstream ships the server and the
# redistributable CUDA runtime as separate archives.
_REQUIRED_ROLES = {
    ("ubuntu", "cpu"): {"server"},
    ("ubuntu", "cuda"): {"source"},
    ("windows", "cpu"): {"server"},
    ("windows", "cuda"): {"server", "cuda-runtime"},
}


@dataclass(frozen=True, slots=True)
class TransferProgress:
    """Report measured bytes for one download or extraction operation."""

    completed_bytes: int
    total_bytes: int | None
    is_cached: bool = False


TransferProgressCallback = Callable[[TransferProgress], None]


@dataclass(frozen=True, slots=True)
class RemoteFile:
    """Describe one pinned file that can be fetched over HTTPS and proved by digest."""

    filename: str
    url: str
    sha256: str


@dataclass(frozen=True, slots=True)
class EngineAsset:
    """Describe one archive pinned by ``engine.lock`` for a target pair."""

    os_name: PlatformKey
    backend: Backend
    role: Role
    filename: str
    url: str
    sha256: str
    archive: ArchiveKind
    executable: str | None


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    """Group one verified archive, its staging destination, and byte reporter."""

    asset: EngineAsset
    archive_path: Path
    destination: Path
    progress: TransferProgressCallback | None = None


def _is_safe_relative(value: str) -> bool:
    """Reject archive-controlled absolute, drive-relative, and parent paths."""
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return bool(posix.parts) and not (
        "\\" in value
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
        or _has_unsafe_windows_component(posix.parts)
    )


def _has_unsafe_windows_component(parts: tuple[str, ...]) -> bool:
    """Reject names Windows redirects, aliases, or normalizes to another path."""
    forbidden = '<>:"|?*'
    return any(
        not part
        or part.endswith((" ", "."))
        or any(character in forbidden or ord(character) < 32 for character in part)
        or _WINDOWS_DEVICE.fullmatch(part) is not None
        for part in parts
    )


def _parse_identity(item: JsonObject) -> tuple[PlatformKey, Backend, Role]:
    """Validate one asset's target and role discriminators."""
    os_name = item.get("os")
    backend = item.get("backend")
    role = item.get("role")
    if os_name not in {"ubuntu", "windows"}:
        raise EngineError(f"engine asset has unsupported OS {os_name!r}")
    if backend not in {"cpu", "cuda"}:
        raise EngineError(f"engine asset has unsupported backend {backend!r}")
    if role not in _ALLOWED_ROLES:
        raise EngineError(f"engine asset has unsupported role {role!r}")
    return cast(PlatformKey, os_name), cast(Backend, backend), cast(Role, role)


def _parse_asset(value: object) -> EngineAsset:
    """Construct one defensive runtime asset from validated lock data."""
    if not isinstance(value, dict):
        raise EngineError("every engine asset must be an object")
    item = cast(JsonObject, value)
    os_name, backend, role = _parse_identity(item)
    strings = ("filename", "url", "sha256", "archive")
    if any(not isinstance(item.get(field), str) for field in strings):
        raise EngineError("engine asset filename, URL, digest, and archive must be strings")
    filename, url = cast(str, item["filename"]), cast(str, item["url"])
    executable = item.get("executable")
    parsed_url = urlparse(url)
    unsafe_filename = not _is_safe_relative(filename) or "/" in filename or "\\" in filename
    if unsafe_filename or parsed_url.scheme != "https" or not parsed_url.netloc:
        raise EngineError(f"engine asset has unsafe filename or non-HTTPS URL: {filename}")
    archive = item["archive"]
    digest = cast(str, item["sha256"])
    if archive not in {"zip", "tar.gz"} or _HEX_64.fullmatch(digest) is None:
        raise EngineError(f"engine asset has unsupported archive or digest: {filename}")
    if executable is not None and (
        not isinstance(executable, str) or not _is_safe_relative(executable)
    ):
        raise EngineError(f"engine asset has unsafe executable path: {executable!r}")
    return EngineAsset(
        os_name,
        backend,
        role,
        filename,
        url,
        digest,
        cast(ArchiveKind, archive),
        executable,
    )


def _load_assets(lock: JsonObject) -> tuple[EngineAsset, ...]:
    """Load assets only after the lock declares its matrix complete."""
    if lock.get("assets_complete") is not True:
        raise EngineError("engine.lock assets are incomplete; managed installation is unavailable")
    values = lock.get("assets")
    if not isinstance(values, list):
        raise EngineError("engine.lock assets must be an array")
    return tuple(_parse_asset(value) for value in values)


def select_assets(
    lock: JsonObject, platform_key: PlatformKey, backend: Backend
) -> tuple[EngineAsset, ...]:
    """Select an exact verified OS/backend set and reject missing or extra roles."""
    selected = tuple(
        asset
        for asset in _load_assets(lock)
        if asset.os_name == platform_key and asset.backend == backend
    )
    roles = {asset.role for asset in selected}
    expected = _REQUIRED_ROLES[(platform_key, backend)]
    if roles != expected or len(selected) != len(expected):
        raise EngineError(
            f"engine.lock has no exact {platform_key}/{backend} asset set; "
            f"expected roles {sorted(expected)}"
        )
    return selected


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _content_length(response: httpx.Response) -> int | None:
    """Read optional response length for UX without weakening byte verification."""
    value = response.headers.get("Content-Length")
    try:
        total = int(value) if value is not None else None
    except ValueError:
        return None
    return total if total is not None and total >= 0 else None


def _redirect_target(response: httpx.Response) -> str | None:
    """Return a validated HTTPS redirect target or identify a final HTTPS response."""
    response_url = str(response.url)
    if urlparse(response_url).scheme != "https":
        raise EngineError(f"download redirected away from HTTPS: {response_url}")
    if not response.is_redirect:
        return None
    location = response.headers.get("Location")
    if location is None:
        raise EngineError(f"download redirect has no location: {response_url}")
    return urljoin(response_url, location)


@contextmanager
def _https_stream(url: str, timeout: httpx.Timeout) -> Iterator[httpx.Response]:
    """Open one response while refusing every non-HTTPS redirect before following it."""
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        if urlparse(current).scheme != "https":
            raise EngineError(f"download redirected away from HTTPS: {current}")
        with httpx.stream("GET", current, follow_redirects=False, timeout=timeout) as response:
            target = _redirect_target(response)
            if target is not None:
                current = target
                continue
            response.raise_for_status()
            yield response
            return
    raise EngineError(f"download exceeded {_MAX_REDIRECTS} redirects: {url}")


def _write_response(
    response: httpx.Response, partial: Path, progress: TransferProgressCallback | None
) -> tuple[str, int | None, int]:
    """Write one final response to a new partial file and return its measured identity."""
    digest = hashlib.sha256()
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
    return digest.hexdigest(), total, completed


def _stream_to_file(
    asset: RemoteFile, partial: Path, progress: TransferProgressCallback | None
) -> str:
    """Stream one HTTPS response into a partial file and report measured transfer bytes."""
    timeout = httpx.Timeout(60.0, connect=10.0)
    with _https_stream(asset.url, timeout) as response:
        digest, total, completed = _write_response(response, partial, progress)
    if progress is not None and total is None:
        progress(TransferProgress(completed, completed))
    return digest


def download_asset(
    asset: EngineAsset,
    cache_root: Path,
    progress: TransferProgressCallback | None = None,
) -> Path:
    """Return a verified cached engine archive, reporting bytes for progress and ETA."""
    return download_file(RemoteFile(asset.filename, asset.url, asset.sha256), cache_root, progress)


def _is_already_verified(
    target: Path, asset: RemoteFile, progress: TransferProgressCallback | None
) -> bool:
    """Report whether the destination already holds this exact file, clearing what it must not.

    A symlink or a non-regular file under the target name is removed or refused before any
    download, so a publish by rename can never follow a link out of the managed root.
    """
    if target.is_symlink():
        target.unlink()
    if target.is_file() and _file_sha256(target) == asset.sha256:
        if progress is not None:
            size = target.stat().st_size
            progress(TransferProgress(size, size, True))
        return True
    if target.exists() and not target.is_file():
        raise EngineError(f"managed cache target is not a regular file: {target}")
    if target.exists():
        target.unlink()
    return False


def download_file(
    asset: RemoteFile,
    cache_root: Path,
    progress: TransferProgressCallback | None = None,
) -> Path:
    """Return one verified file in the destination root, downloading it only when needed.

    Engine archives and model weights share this transfer because they share the same
    requirements: HTTPS only, a mandatory digest, a partial file that is never mistaken for a
    complete one, and an atomic rename that publishes the result (specification section 5.10).
    """
    partial = cache_root / f".{asset.filename}-{uuid4().hex}.part"
    try:
        if cache_root.is_symlink():
            raise EngineError(f"managed cache root must not be a symlink: {cache_root}")
        cache_root.mkdir(parents=True, exist_ok=True)
        target = cache_root / asset.filename
        if _is_already_verified(target, asset, progress):
            return target
        digest = _stream_to_file(asset, partial, progress)
        if digest != asset.sha256:
            raise EngineError(
                f"checksum mismatch for {asset.filename}: expected {asset.sha256}, got {digest}"
            )
        partial.replace(target)
        return target
    except BaseException as error:
        with suppress(FileNotFoundError):
            partial.unlink()
        if isinstance(error, EngineError):
            raise
        if isinstance(error, (OSError, httpx.HTTPError)):
            raise EngineError(f"download failed for {asset.url}: {error}") from error
        raise


@dataclass(slots=True)
class _ByteTracker:
    """Track extracted bytes across all regular members in one archive."""

    total_bytes: int
    progress: TransferProgressCallback | None
    completed_bytes: int = 0

    def start(self) -> None:
        """Report the known uncompressed archive size before copying members."""
        if self.progress is not None:
            self.progress(TransferProgress(0, self.total_bytes))

    def copy(self, source: BinaryIO, output: BinaryIO) -> None:
        """Copy one member in bounded chunks and report cumulative extracted bytes."""
        while chunk := source.read(_CHUNK_SIZE):
            output.write(chunk)
            self.completed_bytes += len(chunk)
            if self.progress is not None:
                self.progress(TransferProgress(self.completed_bytes, self.total_bytes))


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
        or _has_unsafe_windows_component(posix.parts)
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
        tracker = _ByteTracker(sum(member.file_size for member in members), request.progress)
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


@dataclass(slots=True)
class _TarExtraction:
    """Hold one archive's validated member index, progress, and deferred links."""

    request: ExtractionRequest
    archive: tarfile.TarFile
    indexed: dict[str, tarfile.TarInfo]
    tracker: _ByteTracker
    symlinks: list[tarfile.TarInfo]

    def extract_member(self, member: tarfile.TarInfo) -> None:
        """Extract or defer one validated member without nesting the archive traversal."""
        target = _target_path(self.request.destination, member.name)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            return
        if member.issym():
            _safe_symlink_target(self.request.destination, member, self.indexed)
            self.symlinks.append(member)
            return
        if not member.isfile():
            raise EngineError(f"non-regular archive member: {member.name!r}")
        self._extract_file(member, target)

    def _extract_file(self, member: tarfile.TarInfo, target: Path) -> None:
        """Copy one regular member and restore only its declared permission bits."""
        source = self.archive.extractfile(member)
        if source is None:
            raise EngineError(f"cannot read archive member: {member.name!r}")
        _prepare_file(target, member.name)
        with source, target.open("xb") as output:
            self.tracker.copy(source, output)
        target.chmod(member.mode & 0o777)

    def create_symlinks(self) -> None:
        """Create already validated internal links after every regular file exists."""
        for member in self.symlinks:
            _create_tar_symlink(self.request.destination, member, self.indexed)


def _extract_tar(request: ExtractionRequest) -> None:
    """Extract safe tar members while reporting their total regular-file bytes."""
    with tarfile.open(request.archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        indexed = {_member_key(member.name): member for member in members}
        total_bytes = sum(member.size for member in members if member.isfile())
        tracker = _ByteTracker(total_bytes, request.progress)
        tracker.start()
        extraction = _TarExtraction(request, archive, indexed, tracker, [])
        for member in members:
            extraction.extract_member(member)
        extraction.create_symlinks()


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
