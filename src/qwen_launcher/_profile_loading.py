"""Construct immutable runtime content after complete resource validation."""

from __future__ import annotations

import json
from importlib.resources.abc import Traversable
from typing import Literal, cast

from qwen_launcher.profiles import (
    Catalog,
    ContentError,
    Envelope,
    GibRange,
    Mode,
    ModeServices,
    Profile,
    ProfileMatch,
    Sampling,
    TokenRate,
)
from qwen_launcher.resources import resource_root

JsonObject = dict[str, object]


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
    return Envelope(cast(int, raw["ctx"]), cast(int | None, raw.get("n_cpu_moe")), tok_s)


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
    """Construct a shared seed and mark lock-release divergence."""
    raw = _read_object(file)
    match = cast(JsonObject, raw["match"])
    raw_modes = cast(JsonObject, raw["modes"])
    profile_match = ProfileMatch(
        cast(Literal["cuda", "cpu"], match["backend"]),
        _range(match["vram_gib"]),
        _range(match["ram_gib"]),
        tuple(cast(list[str], match.get("os", []))),
    )
    profile_engine = cast(str, raw["engine"])
    return Profile(
        cast(str, raw["id"]),
        cast(str, raw["model"]),
        profile_engine,
        cast(str, raw["measured_on"]),
        cast(str, raw["calibration_report"]),
        profile_match,
        tuple((name, _envelope(value)) for name, value in sorted(raw_modes.items())),
        profile_engine == engine_release,
    )


def _json_files(directory: Traversable) -> tuple[Traversable, ...]:
    """Return sorted JSON children, treating an absent directory as an empty catalog."""
    if not directory.is_dir():
        return ()
    children = (item for item in directory.iterdir() if item.name.endswith(".json"))
    return tuple(sorted(children, key=lambda item: item.name))


def load_catalog_from_root(root: Traversable | None = None) -> Catalog:
    """Validate one resource root before constructing its immutable runtime catalog."""
    from qwen_launcher.validation import validate_resources

    selected_root = resource_root() if root is None else root
    result = validate_resources(selected_root)
    if result.errors:
        issue = result.errors[0]
        raise ContentError(f"{issue.file}:{issue.field_path}: {issue.message}")
    release = cast(str, _read_object(selected_root.joinpath("engine.lock"))["release"])
    content = selected_root.joinpath("content")
    modes = tuple(_mode(file) for file in _json_files(content.joinpath("modes")))
    profiles = tuple(_profile(file, release) for file in _json_files(content.joinpath("profiles")))
    return Catalog(modes, profiles)
