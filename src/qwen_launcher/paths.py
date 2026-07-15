"""Public per-OS paths for qwen-launcher.

These functions compute paths only: they never create directories.
"""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath

_APP_NAME = "qwen-launcher"


def _system_name() -> str:
    return platform.system().lower()


def _is_absolute(value: str, *, windows: bool) -> bool:
    if windows:
        return PureWindowsPath(value).is_absolute()
    return PurePosixPath(value).is_absolute()


def _environment_path(
    variable: str,
    fallback: Path,
    *,
    windows: bool,
    environ: Mapping[str, str] | None = None,
) -> Path:
    environment = os.environ if environ is None else environ
    raw_value = environment.get(variable)
    if not raw_value or not _is_absolute(raw_value, windows=windows):
        return fallback
    return Path(raw_value)


def config_dir() -> Path:
    """Return the configuration directory without creating it."""
    home = Path.home()
    if _system_name() == "windows":
        base = _environment_path("APPDATA", home / "AppData" / "Roaming", windows=True)
    else:
        base = _environment_path("XDG_CONFIG_HOME", home / ".config", windows=False)
    return base / _APP_NAME


def data_dir() -> Path:
    """Return the managed data directory without creating it."""
    home = Path.home()
    if _system_name() == "windows":
        base = _environment_path("LOCALAPPDATA", home / "AppData" / "Local", windows=True)
        return base / _APP_NAME / "data"
    base = _environment_path("XDG_DATA_HOME", home / ".local" / "share", windows=False)
    return base / _APP_NAME


def cache_dir() -> Path:
    """Return the cache directory without creating it."""
    home = Path.home()
    if _system_name() == "windows":
        base = _environment_path("LOCALAPPDATA", home / "AppData" / "Local", windows=True)
        return base / _APP_NAME / "cache"
    base = _environment_path("XDG_CACHE_HOME", home / ".cache", windows=False)
    return base / _APP_NAME


def state_dir() -> Path:
    """Return the runtime state directory without creating it."""
    home = Path.home()
    if _system_name() == "windows":
        base = _environment_path("LOCALAPPDATA", home / "AppData" / "Local", windows=True)
        return base / _APP_NAME / "state"
    base = _environment_path("XDG_STATE_HOME", home / ".local" / "state", windows=False)
    return base / _APP_NAME
