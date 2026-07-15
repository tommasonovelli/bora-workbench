"""Access package resources without assuming that they are physical files."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


def resource_root() -> Traversable:
    """Return the package resource root as a Traversable."""
    return files(__package__)


def resource(relative_path: str) -> Traversable:
    """Return one resource while rejecting absolute and parent-relative paths."""
    posix_path = PurePosixPath(relative_path)
    windows_path = PureWindowsPath(relative_path)
    parts = posix_path.parts
    is_unsafe = (
        not parts
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in parts
        or ".." in windows_path.parts
    )
    if is_unsafe:
        raise ValueError("resource path must be relative and cannot contain '..'")
    return resource_root().joinpath(*parts)


def read_text(relative_path: str) -> str:
    """Read a UTF-8 text resource."""
    return resource(relative_path).read_text(encoding="utf-8")


def read_json(relative_path: str) -> Any:
    """Read and decode a UTF-8 JSON resource."""
    return json.loads(read_text(relative_path))


def resource_as_file(relative_path: str) -> AbstractContextManager[Path]:
    """Materialize a resource only for the duration of a context manager."""
    return as_file(resource(relative_path))
