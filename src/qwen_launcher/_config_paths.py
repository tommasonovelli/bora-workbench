"""Validate optional configuration paths without checking the filesystem."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Report expected, actionable configuration errors to the CLI boundary."""


def validate_model_path(value: Any, *, source: str, allow_empty: bool = False) -> Path | None:
    """Return a model path while keeping it distinct from declarative model identity."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{source}: 'model_path' must be a string")
    if not value.strip():
        if allow_empty:
            return None
        raise ConfigError(f"{source}: 'model_path' must not be empty")
    return Path(value).expanduser()


def validate_engine_path(value: Any, *, source: str, allow_empty: bool = False) -> Path | None:
    """Return an engine path, treating an allowed empty environment value as unset."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{source}: 'engine_path' must be a string")
    if not value.strip():
        if allow_empty:
            return None
        raise ConfigError(f"{source}: 'engine_path' must not be empty")
    return Path(value).expanduser()
