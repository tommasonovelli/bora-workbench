"""Strict TOML and environment configuration for bora-workbench 0.1.

Strict means that an unknown key or a malformed value is an error, never a silent fallback: a typo
must be reported instead of quietly launching the engine with a default the user never chose.
The whole contract — keys, variables, constraints, and the environment > file > code-default
precedence — is fixed by specification section 5.2, with the no-fallback rule in section 5.11.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bora_workbench.paths import config_dir

DEFAULT_MODEL = "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M"
DEFAULT_LLAMA_PORT = 8080
DEFAULT_OPEN_BROWSER = True

_ALLOWED_KEYS = {"model", "model_path", "llama_port", "engine_path", "open_browser"}
_ENVIRONMENT_KEYS = {
    "model": "BORA_MODEL",
    "model_path": "BORA_MODEL_PATH",
    "llama_port": "BORA_LLAMA_PORT",
    "engine_path": "BORA_ENGINE_PATH",
    "open_browser": "BORA_OPEN_BROWSER",
}
_TRUE_VALUES = {"true", "1", "yes", "on"}
_FALSE_VALUES = {"false", "0", "no", "off"}


class ConfigError(ValueError):
    """Report expected, actionable configuration errors to the CLI boundary."""


@dataclass(frozen=True, slots=True)
class Config:
    """The resolved configuration, frozen once precedence and validation have been applied."""

    model: str = DEFAULT_MODEL
    model_path: Path | None = None
    llama_port: int = DEFAULT_LLAMA_PORT
    engine_path: Path | None = None
    open_browser: bool = DEFAULT_OPEN_BROWSER


def _validate_model(value: Any, *, source: str) -> str:
    """Return the model identifier, rejecting anything that is not a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{source}: 'model' must be a non-empty string")
    return value.strip()


def _validate_port(value: Any, *, source: str) -> int:
    """Return a port in the 1-65535 range, rejecting any other value."""
    # `bool` subclasses `int` in Python, so `llama_port = true` would otherwise be accepted and
    # silently bind the engine to port 1.
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ConfigError(f"{source}: 'llama_port' must be an integer between 1 and 65535")
    return value


def _validate_boolean(value: Any, *, source: str) -> bool:
    """Return a real TOML boolean, rejecting strings such as `"yes"`."""
    if not isinstance(value, bool):
        raise ConfigError(f"{source}: 'open_browser' must be a boolean")
    return value


def _validate_file_path(value: Any, key: str, source: str) -> Path:
    """Return the expanded optional path declared for `key` in the configuration file.

    The value is only expanded, never resolved or probed on disk, because a physical path stays
    declarative here and is checked by the operation that uses it (specification section 5.2).
    """
    if not isinstance(value, str):
        raise ConfigError(f"{source}: {key!r} must be a string")
    if not value.strip():
        raise ConfigError(f"{source}: {key!r} must not be empty")
    return Path(value).expanduser()


def _environment_path_override(value: str) -> Path | None:
    """Return the expanded path an environment variable names, or None when it is blank.

    An empty variable means "unset the value the file supplied" rather than "invalid": it is the
    only way to drop an optional path without editing `config.toml` (specification section 5.2).
    """
    if not value.strip():
        return None
    return Path(value).expanduser()


def _validate_file_values(values: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    """Validate every key of a parsed TOML file and return the accepted values.

    Unknown keys are rejected rather than ignored, which turns a typo or a key belonging to a later
    milestone into an actionable error instead of a setting that only appears to work.
    """
    unknown = sorted(set(values) - _ALLOWED_KEYS)
    if unknown:
        names = ", ".join(repr(name) for name in unknown)
        raise ConfigError(f"{source}: unknown configuration key(s): {names}")

    validated: dict[str, Any] = {}
    if "model" in values:
        validated["model"] = _validate_model(values["model"], source=source)
    if "model_path" in values:
        validated["model_path"] = _validate_file_path(values["model_path"], "model_path", source)
    if "llama_port" in values:
        validated["llama_port"] = _validate_port(values["llama_port"], source=source)
    if "engine_path" in values:
        validated["engine_path"] = _validate_file_path(values["engine_path"], "engine_path", source)
    if "open_browser" in values:
        validated["open_browser"] = _validate_boolean(values["open_browser"], source=source)
    return validated


def _parse_environment_port(value: str, *, variable: str) -> int:
    """Parse a port from an environment string, which carries no TOML type information."""
    # `int()` also accepts a sign, digit separators such as "8_080", and non-ASCII digits, so the
    # string is screened down to plain decimal digits before it is converted.
    if not value or not value.isascii() or not value.isdecimal():
        raise ConfigError(f"environment variable {variable} must be an integer between 1 and 65535")
    return _validate_port(int(value), source=f"environment variable {variable}")


def _parse_environment_boolean(value: str, *, variable: str) -> bool:
    """Parse the case-insensitive boolean spellings allowed for environment variables."""
    normalized = value.casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    allowed = "true/false, 1/0, yes/no, on/off"
    raise ConfigError(f"environment variable {variable} must be one of: {allowed}")


def _environment_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    """Collect and validate the overrides supplied through the environment."""
    overrides: dict[str, Any] = {}
    for key, variable in _ENVIRONMENT_KEYS.items():
        if variable not in environ:
            continue
        value = environ[variable]
        if key == "model":
            overrides[key] = _validate_model(value, source=f"environment variable {variable}")
        elif key in ("model_path", "engine_path"):
            overrides[key] = _environment_path_override(value)
        elif key == "llama_port":
            overrides[key] = _parse_environment_port(value, variable=variable)
        else:
            overrides[key] = _parse_environment_boolean(value, variable=variable)
    return overrides


def _read_toml(path: Path) -> dict[str, Any]:
    """Read and validate the configuration file, treating an absent file as first-run defaults."""
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
    """Load config using environment > TOML file > code defaults precedence.

    The file is validated in full before any override is applied, so an invalid `config.toml` is
    reported even when an environment variable would have replaced the offending key: the error must
    stay reproducible once that variable is gone.
    """
    config_path = config_dir() / "config.toml" if path is None else path
    environment = os.environ if environ is None else environ

    # Each layer overwrites the previous one, so the update order is the precedence rule itself;
    # a key neither layer supplies keeps the code default declared on `Config`.
    values = _read_toml(config_path)
    values.update(_environment_overrides(environment))
    return Config(**values)
