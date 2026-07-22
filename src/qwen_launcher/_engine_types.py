"""Define narrow immutable models shared by managed-engine operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ArchiveKind = Literal["zip", "tar.gz"]
Backend = Literal["cpu", "cuda"]
InstallStage = Literal["asset", "extract", "compile", "verify", "activate"]
InstallProgress = Callable[[InstallStage, str | None], None]
PlatformKey = Literal["ubuntu", "windows"]
Role = Literal["server", "cuda-runtime", "source"]


class EngineError(RuntimeError):
    """Report an absent, incompatible, or unsafe engine artifact."""


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """Hold physical model files without changing their declarative identity."""

    model_path: Path
    mmproj_path: Path | None


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
class EngineStatus:
    """Describe the active managed engine and its compatibility with the lock."""

    is_active: bool
    release: str | None
    backend: str | None
    executable: Path | None
    is_compatible: bool
    differences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InstallRequest:
    """Group the roots and target selected by the public engine module."""

    platform_key: PlatformKey
    backend: Backend
    force: bool
    engine_root: Path
    cache_root: Path
    lock: dict[str, object]
    notice_resources: tuple[str, ...]
    set_executable_mode: bool
    progress: InstallProgress | None = None


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Report the selected installation and whether this invocation changed it."""

    status: EngineStatus
    was_installed: bool
