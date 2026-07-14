"""Strict TOML and environment configuration for qwen-launcher 0.1."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qwen_launcher.paths import config_dir

DEFAULT_MODEL = "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M"
DEFAULT_LLAMA_PORT = 8080
DEFAULT_OPEN_BROWSER = True

_ALLOWED_KEYS = {"model", "llama_port", "engine_path", "open_browser"}
_ENVIRONMENT_KEYS = {
    "model": "QWEN_LAUNCHER_MODEL",
    "llama_port": "QWEN_LAUNCHER_LLAMA_PORT",
    "engine_path": "QWEN_LAUNCHER_ENGINE_PATH",
    "open_browser": "QWEN_LAUNCHER_OPEN_BROWSER",
}
_TRUE_VALUES = {"true", "1", "yes", "on"}
_FALSE_VALUES = {"false", "0", "no", "off"}


class ConfigError(ValueError):
    """Raised for expected, actionable configuration errors."""


@dataclass(frozen=True, slots=True)
class Config:
    model: str = DEFAULT_MODEL
    llama_port: int = DEFAULT_LLAMA_PORT
    engine_path: Path | None = None
    open_browser: bool = DEFAULT_OPEN_BROWSER


def _validate_model(value: Any, *, source: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{source}: 'model' must be a non-empty string")
    return value.strip()


def _validate_port(value: Any, *, source: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ConfigError(f"{source}: 'llama_port' must be an integer between 1 and 65535")
    return value


def _validate_engine_path(value: Any, *, source: str, allow_empty: bool = False) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{source}: 'engine_path' must be a string")
    if not value.strip():
        if allow_empty:
            return None
        raise ConfigError(f"{source}: 'engine_path' must not be empty")
    return Path(value).expanduser()


def _validate_boolean(value: Any, *, source: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{source}: 'open_browser' must be a boolean")
    return value


def _validate_file_values(values: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    unknown = sorted(set(values) - _ALLOWED_KEYS)
    if unknown:
        names = ", ".join(repr(name) for name in unknown)
        raise ConfigError(f"{source}: unknown configuration key(s): {names}")

    validated: dict[str, Any] = {}
    if "model" in values:
        validated["model"] = _validate_model(values["model"], source=source)
    if "llama_port" in values:
        validated["llama_port"] = _validate_port(values["llama_port"], source=source)
    if "engine_path" in values:
        validated["engine_path"] = _validate_engine_path(values["engine_path"], source=source)
    if "open_browser" in values:
        validated["open_browser"] = _validate_boolean(values["open_browser"], source=source)
    return validated


def _parse_environment_port(value: str, *, variable: str) -> int:
    if not value or not value.isascii() or not value.isdecimal():
        raise ConfigError(f"environment variable {variable} must be an integer between 1 and 65535")
    return _validate_port(int(value), source=f"environment variable {variable}")


def _parse_environment_boolean(value: str, *, variable: str) -> bool:
    normalized = value.casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    allowed = "true/false, 1/0, yes/no, on/off"
    raise ConfigError(f"environment variable {variable} must be one of: {allowed}")


def _environment_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key, variable in _ENVIRONMENT_KEYS.items():
        if variable not in environ:
            continue
        value = environ[variable]
        if key == "model":
            overrides[key] = _validate_model(value, source=f"environment variable {variable}")
        elif key == "llama_port":
            overrides[key] = _parse_environment_port(value, variable=variable)
        elif key == "engine_path":
            overrides[key] = _validate_engine_path(
                value, source=f"environment variable {variable}", allow_empty=True
            )
        else:
            overrides[key] = _parse_environment_boolean(value, variable=variable)
    return overrides


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as config_file:
            parsed = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read configuration file {path}: {error}") from error
    return _validate_file_values(parsed, source=str(path))


def load_config(
    path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Config:
    """Load config using environment > TOML file > code defaults precedence."""
    config_path = config_dir() / "config.toml" if path is None else path
    environment = os.environ if environ is None else environ

    values: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "llama_port": DEFAULT_LLAMA_PORT,
        "engine_path": None,
        "open_browser": DEFAULT_OPEN_BROWSER,
    }
    values.update(_read_toml(config_path))
    values.update(_environment_overrides(environment))
    return Config(**values)
