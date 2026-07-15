"""Load validated resources immutably; matching and fallback remain reserved for Step 3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import Literal, cast

from qwen_launcher.resources import resource_root

JsonObject = dict[str, object]


class ContentError(RuntimeError):
    """Report packaged content that cannot safely become a runtime catalog."""


@dataclass(frozen=True, slots=True)
class ModeServices:
    """Describe services explicitly enabled by a mode."""

    ui: bool
    vision: bool


@dataclass(frozen=True, slots=True)
class Sampling:
    """Hold the mode-owned sampling parameters."""

    temp: float
    top_p: float
    top_k: int


@dataclass(frozen=True, slots=True)
class Mode:
    """Represent one validated launcher behavior mode."""

    id: str
    description: str
    services: ModeServices
    sampling: Sampling


@dataclass(frozen=True, slots=True)
class GibRange:
    """Represent an inclusive nominal GiB class with an optional upper bound."""

    minimum_gib: float
    maximum_gib: float | None


@dataclass(frozen=True, slots=True)
class TokenRate:
    """Represent an ordered benchmark/v1 token-rate summary."""

    minimum: float
    median: float
    maximum: float


@dataclass(frozen=True, slots=True)
class ProfileMatch:
    """Hold hardware constraints used later by Step 3 matching."""

    backend: Literal["cuda", "cpu"]
    vram_gib: GibRange
    ram_gib: GibRange
    operating_systems: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Envelope:
    """Hold one calibrated mode envelope without behavior-owned settings."""

    ctx: int
    n_cpu_moe: int | None
    tok_s: TokenRate | None


@dataclass(frozen=True, slots=True)
class Profile:
    """Represent one validated profile and its engine compatibility state."""

    id: str
    model: str
    engine: str
    measured_on: str
    calibration_report: str
    match: ProfileMatch
    modes: tuple[tuple[str, Envelope], ...]
    is_engine_compatible: bool

    def envelope_for(self, mode_id: str) -> Envelope | None:
        """Return the envelope for one mode without performing hardware matching."""
        return next((value for name, value in self.modes if name == mode_id), None)


@dataclass(frozen=True, slots=True)
class Catalog:
    """Hold immutable validated modes and profiles loaded from one resource root."""

    modes: tuple[Mode, ...]
    profiles: tuple[Profile, ...]

    def mode(self, mode_id: str) -> Mode | None:
        """Return one mode by identifier, or None when it does not exist."""
        return next((mode for mode in self.modes if mode.id == mode_id), None)


def _read_object(file: Traversable) -> JsonObject:
    """Decode one already validated JSON object from a Traversable."""
    return cast(JsonObject, json.loads(file.read_text(encoding="utf-8")))


def _range(values: object) -> GibRange:
    """Construct an immutable GiB range from validated JSON values."""
    minimum, maximum = cast(list[float | None], values)
    return GibRange(float(cast(float, minimum)), None if maximum is None else float(maximum))


def _token_rate(value: object) -> TokenRate:
    """Construct a token-rate summary from a validated JSON object."""
    rates = cast(JsonObject, value)
    return TokenRate(float(rates["min"]), float(rates["median"]), float(rates["max"]))


def _envelope(value: object) -> Envelope:
    """Construct one immutable performance envelope."""
    raw = cast(JsonObject, value)
    tok_s = _token_rate(raw["tok_s"]) if "tok_s" in raw else None
    n_cpu_moe = cast(int | None, raw.get("n_cpu_moe"))
    return Envelope(cast(int, raw["ctx"]), n_cpu_moe, tok_s)


def _mode(file: Traversable) -> Mode:
    """Construct a runtime mode from one validated mode resource."""
    raw = _read_object(file)
    services = cast(JsonObject, raw["services"])
    sampling = cast(JsonObject, raw["sampling"])
    return Mode(
        cast(str, raw["id"]),
        cast(str, raw["description"]),
        ModeServices(cast(bool, services["ui"]), cast(bool, services["vision"])),
        Sampling(float(sampling["temp"]), float(sampling["top_p"]), cast(int, sampling["top_k"])),
    )


def _profile(file: Traversable, engine_release: str) -> Profile:
    """Construct a runtime profile and mark lock-release divergence."""
    raw = _read_object(file)
    match = cast(JsonObject, raw["match"])
    raw_modes = cast(JsonObject, raw["modes"])
    profile_match = ProfileMatch(
        cast(Literal["cuda", "cpu"], match["backend"]),
        _range(match["vram_gib"]),
        _range(match["ram_gib"]),
        tuple(cast(list[str], match.get("os", []))),
    )
    modes = tuple((name, _envelope(value)) for name, value in sorted(raw_modes.items()))
    profile_engine = cast(str, raw["engine"])
    return Profile(
        cast(str, raw["id"]),
        cast(str, raw["model"]),
        profile_engine,
        cast(str, raw["measured_on"]),
        cast(str, raw["calibration_report"]),
        profile_match,
        modes,
        profile_engine == engine_release,
    )


def _json_files(directory: Traversable) -> tuple[Traversable, ...]:
    """Return sorted JSON children, treating an absent directory as an empty catalog."""
    if not directory.is_dir():
        return ()
    children = (item for item in directory.iterdir() if item.name.endswith(".json"))
    return tuple(sorted(children, key=lambda item: item.name))


def load_catalog(root: Traversable | None = None) -> Catalog:
    """Validate and load package content, refusing any validation error."""
    from qwen_launcher.validation import validate_resources

    selected_root = resource_root() if root is None else root
    result = validate_resources(selected_root)
    if result.errors:
        issue = result.errors[0]
        raise ContentError(f"{issue.file}:{issue.field_path}: {issue.message}")
    engine_release = cast(str, _read_object(selected_root.joinpath("engine.lock"))["release"])
    content = selected_root.joinpath("content")
    modes = tuple(_mode(file) for file in _json_files(content.joinpath("modes")))
    profiles = tuple(
        _profile(file, engine_release) for file in _json_files(content.joinpath("profiles"))
    )
    return Catalog(modes, profiles)
