"""Parse and select only complete asset sets declared by ``engine.lock``."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import cast
from urllib.parse import urlparse

from qwen_launcher._engine_types import (
    ArchiveKind,
    Backend,
    EngineAsset,
    EngineError,
    PlatformKey,
    Role,
)

JsonObject = dict[str, object]
_ALLOWED_ROLES = {"server", "cuda-runtime", "source"}
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_ROLES = {
    ("ubuntu", "cpu"): {"server"},
    ("ubuntu", "cuda"): {"source"},
    ("windows", "cpu"): {"server"},
    ("windows", "cuda"): {"server", "cuda-runtime"},
}


def _is_safe_relative(value: str) -> bool:
    """Reject archive-controlled absolute, drive-relative, and parent paths."""
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return bool(posix.parts) and not (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
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


def load_assets(lock: JsonObject) -> tuple[EngineAsset, ...]:
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
        for asset in load_assets(lock)
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
