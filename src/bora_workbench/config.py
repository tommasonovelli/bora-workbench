"""Strict TOML and environment configuration for bora-workbench 0.2.

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
from typing import Any, Literal

from bora_workbench.paths import config_dir

DEFAULT_MODEL = "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M"
DEFAULT_LLAMA_PORT = 8080
# Open WebUI's own default is 8080, which is `llama_port`, so the two managed services would
# collide on a first launch if this default were copied from upstream (D-095).
DEFAULT_WEBUI_PORT = 8081
DEFAULT_OPEN_BROWSER = True

_ALLOWED_KEYS = {
    "model",
    "model_path",
    "llama_port",
    "webui_port",
    "engine_path",
    "open_browser",
}
_ENVIRONMENT_KEYS = {
    "model": "BORA_MODEL",
    "model_path": "BORA_MODEL_PATH",
    "llama_port": "BORA_LLAMA_PORT",
    "webui_port": "BORA_WEBUI_PORT",
    "engine_path": "BORA_ENGINE_PATH",
    "open_browser": "BORA_OPEN_BROWSER",
}
_PORT_KEYS = ("llama_port", "webui_port")
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
    webui_port: int = DEFAULT_WEBUI_PORT
    engine_path: Path | None = None
    open_browser: bool = DEFAULT_OPEN_BROWSER

    def __post_init__(self) -> None:
        """Reject two managed services configured onto one port before either can be started.

        The check lives on the resolved object rather than on either layer, because the collision
        only exists once precedence has picked a winner for both keys (specification section 5.2).
        """
        if self.llama_port == self.webui_port:
            raise ConfigError(
                f"'llama_port' and 'webui_port' must differ; both resolved to {self.llama_port}"
            )


ConfigSource = Literal["environment", "config.toml", "default"]


@dataclass(frozen=True, slots=True)
class ConfigSources:
    """Name the precedence layer that supplied each resolved setting (D-084)."""

    model: ConfigSource
    model_path: ConfigSource
    llama_port: ConfigSource
    webui_port: ConfigSource
    engine_path: ConfigSource
    open_browser: ConfigSource


@dataclass(frozen=True, slots=True)
class ConfigResolution:
    """Pair resolved configuration with its read-only path and provenance."""

    config: Config
    path: Path
    sources: ConfigSources


def _validate_model(value: Any, *, source: str) -> str:
    """Return the model identifier, rejecting anything that is not a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{source}: 'model' must be a non-empty string")
    return value.strip()


def _validate_port(value: Any, key: str, source: str) -> int:
    """Return a port in the 1-65535 range, rejecting any other value."""
    # `bool` subclasses `int` in Python, so `llama_port = true` would otherwise be accepted and
    # silently bind the engine to port 1.
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ConfigError(f"{source}: {key!r} must be an integer between 1 and 65535")
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
    for key in _PORT_KEYS:
        if key in values:
            validated[key] = _validate_port(values[key], key, source)
    if "engine_path" in values:
        validated["engine_path"] = _validate_file_path(values["engine_path"], "engine_path", source)
    if "open_browser" in values:
        validated["open_browser"] = _validate_boolean(values["open_browser"], source=source)
    return validated


def _parse_environment_port(value: str, key: str, variable: str) -> int:
    """Parse a port from an environment string, which carries no TOML type information."""
    # `int()` also accepts a sign, digit separators such as "8_080", and non-ASCII digits, so the
    # string is screened down to plain decimal digits before it is converted.
    if not value or not value.isascii() or not value.isdecimal():
        raise ConfigError(f"environment variable {variable} must be an integer between 1 and 65535")
    return _validate_port(int(value), key, f"environment variable {variable}")


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
        overrides[key] = _environment_value(key, variable, environ[variable])
    return overrides


def _environment_value(key: str, variable: str, value: str) -> Any:
    """Validate one present environment value according to its configuration field."""
    if key == "model":
        return _validate_model(value, source=f"environment variable {variable}")
    if key in ("model_path", "engine_path"):
        return _environment_path_override(value)
    if key in _PORT_KEYS:
        return _parse_environment_port(value, key, variable)
    return _parse_environment_boolean(value, variable=variable)


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


def _config_source(
    key: str, file_values: Mapping[str, Any], overrides: Mapping[str, Any]
) -> ConfigSource:
    """Return the highest-precedence layer that supplied one field."""
    if key in overrides:
        return "environment"
    if key in file_values:
        return "config.toml"
    return "default"


def _config_sources(file_values: Mapping[str, Any], overrides: Mapping[str, Any]) -> ConfigSources:
    """Build explicit per-field provenance for one resolved configuration."""
    return ConfigSources(
        model=_config_source("model", file_values, overrides),
        model_path=_config_source("model_path", file_values, overrides),
        llama_port=_config_source("llama_port", file_values, overrides),
        webui_port=_config_source("webui_port", file_values, overrides),
        engine_path=_config_source("engine_path", file_values, overrides),
        open_browser=_config_source("open_browser", file_values, overrides),
    )


def load_config_details(
    path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ConfigResolution:
    """Resolve validated configuration together with its path and precedence sources."""
    config_path = config_dir() / "config.toml" if path is None else path
    environment = os.environ if environ is None else environ
    file_values = _read_toml(config_path)
    overrides = _environment_overrides(environment)
    values = {**file_values, **overrides}
    return ConfigResolution(Config(**values), config_path, _config_sources(file_values, overrides))


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
    return load_config_details(path, environ=environ).config
