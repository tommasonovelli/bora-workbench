"""Public per-OS paths for bora-workbench.

These functions compute paths only: they never create directories. Creation belongs to the operation
that owns the data, which is also what keeps importing the package free of side effects
(specification sections 4.3 and 5.11).

The exact layout per operating system is fixed by specification section 5.2. This is one of the four
modules allowed to branch on the operating system (specification section 4.1).
"""

from __future__ import annotations

import os
import platform
from pathlib import Path, PurePosixPath, PureWindowsPath

_APP_NAME = "bora-workbench"


def _system_name() -> str:
    """Return the lowercased operating system name that selects the path layout.

    Every branch below routes through this single function so that tests can simulate an operating
    system by replacing it, instead of depending on the host (specification section 5.2).
    """
    return platform.system().lower()


def _is_absolute(value: str, *, windows: bool) -> bool:
    """Report whether a raw environment value is absolute under the target platform's rules.

    The target platform is passed in rather than inferred from `Path`, because the host is not
    always the platform being computed for: on Linux, `Path` would read a Windows value such as
    `C:\\Users\\Tester` as relative and silently discard it.
    """
    if windows:
        return PureWindowsPath(value).is_absolute()
    return PurePosixPath(value).is_absolute()


def _environment_path(variable: str, fallback: Path, *, windows: bool) -> Path:
    """Return the directory named by an environment variable, or the fallback.

    A variable that is absent, empty, or relative falls back instead of failing: the XDG Base
    Directory Specification mandates this for the XDG variables, and specification section 5.2
    extends the same treatment to APPDATA and LOCALAPPDATA. This is a deliberate exception to the
    project rule that an invalid value is an error.
    """
    raw_value = os.environ.get(variable)
    if not raw_value or not _is_absolute(raw_value, windows=windows):
        return fallback
    return Path(raw_value)


def _windows_local_root() -> Path:
    """Return the machine-local Windows root shared by the data, cache, and state directories.

    Windows collapses those three roots into LOCALAPPDATA, so each of them adds its own
    subdirectory below this one; XDG already hands out three distinct roots (specification
    section 5.2).
    """
    fallback = Path.home() / "AppData" / "Local"
    return _environment_path("LOCALAPPDATA", fallback, windows=True) / _APP_NAME


def config_dir() -> Path:
    """Return the directory holding the user's `config.toml`, without creating it.

    Configuration is the only root placed under APPDATA: it is the one that Windows roams with the
    user profile, while data, cache, and state stay machine-local under LOCALAPPDATA.
    """
    home = Path.home()
    if _system_name() == "windows":
        base = _environment_path("APPDATA", home / "AppData" / "Roaming", windows=True)
    else:
        base = _environment_path("XDG_CONFIG_HOME", home / ".config", windows=False)
    return base / _APP_NAME


def data_dir() -> Path:
    """Return the managed data directory without creating it."""
    if _system_name() == "windows":
        return _windows_local_root() / "data"
    base = _environment_path("XDG_DATA_HOME", Path.home() / ".local" / "share", windows=False)
    return base / _APP_NAME


def cache_dir() -> Path:
    """Return the cache directory without creating it."""
    if _system_name() == "windows":
        return _windows_local_root() / "cache"
    base = _environment_path("XDG_CACHE_HOME", Path.home() / ".cache", windows=False)
    return base / _APP_NAME


def state_dir() -> Path:
    """Return the runtime state directory without creating it."""
    if _system_name() == "windows":
        return _windows_local_root() / "state"
    base = _environment_path("XDG_STATE_HOME", Path.home() / ".local" / "state", windows=False)
    return base / _APP_NAME
