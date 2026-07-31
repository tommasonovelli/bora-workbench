"""Modes, shared seeds, memory gates, and the `LaunchPlan` of bora-workbench.

The module owns the whole path from packaged content to a launch decision (specification section
4.1): it declares the immutable runtime models, builds them from a fully validated resource root,
and applies the section 5.5 rules that pick an envelope for the current machine.

Shared profiles stay reference-only seeds: D-034 forbids treating a measurement taken on another
machine as a local calibration, so only a supported local record may steer a plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from math import inf
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from bora_workbench.config import DEFAULT_MODEL, Config
from bora_workbench.hardware import HardwareInfo
from bora_workbench.resources import resource_root
from bora_workbench.validation import validate_resources

if TYPE_CHECKING:
    from bora_workbench._calibration_reuse import RecordEvaluation

JsonObject = dict[str, object]

DEFAULT_MODEL_MIN_TOTAL_GIB = 28.0
DEFAULT_MODEL_MIN_AVAILABLE_GIB = 22.0

FALLBACK_CTX = 8192
_FALLBACK_CUDA_N_CPU_MOE = 48


class ContentError(RuntimeError):
    """Report packaged content that cannot safely become a runtime catalog."""


class PlanError(RuntimeError):
    """Report a launch request that cannot produce a safe plan."""


@dataclass(frozen=True, slots=True)
class ModeServices:
    """Describe services explicitly enabled by a mode."""

    ui: bool
    vision: bool


@dataclass(frozen=True, slots=True)
class Sampling:
    """Hold current sampling plus optional mode/v2 contract values."""

    temp: float
    top_p: float
    top_k: int
    min_p: float | None = None
    presence_penalty: float | None = None
    repeat_penalty: float | None = None
    reasoning: Literal["on", "off"] | None = None


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
    """Hold the exact hardware constraints used for profile matching."""

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
    """Represent one validated shared seed and its engine compatibility state."""

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
    """Hold the immutable validated modes and historical profiles of one resource root."""

    modes: tuple[Mode, ...]
    profiles: tuple[Profile, ...]

    def mode(self, mode_id: str) -> Mode | None:
        """Return one mode by identifier, or None when it does not exist."""
        return next((mode for mode in self.modes if mode.id == mode_id), None)


@dataclass(frozen=True, slots=True)
class LaunchRequest:
    """Group user configuration, mode, and already resolved model artifacts."""

    config: Config
    mode_id: str
    model_path: Path
    mmproj_path: Path | None = None


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    """Fuse behavior, envelope, model identity, and selected hardware without ambiguity."""

    mode: Mode
    model: str
    model_path: Path
    mmproj_path: Path | None
    port: int
    profile_id: str | None
    ctx: int
    n_cpu_moe: int | None
    backend: Literal["cuda", "cpu"]
    gpu_index: int | None
    warnings: tuple[str, ...]
    # Alerts are the subset of launch findings that name something this machine cannot currently
    # satisfy, so the CLI can give them the one red channel warnings do not have (D-097).
    alerts: tuple[str, ...] = ()
    speculative: Literal["mtp2", "disabled"] = "mtp2"

    def __post_init__(self) -> None:
        """Reject MTP with vision because D-060 keeps that combination disabled."""
        if self.mode.services.vision and self.speculative != "disabled":
            raise PlanError("vision launch plans require speculative='disabled'")


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


def _sampling(sampling: JsonObject) -> Sampling:
    """Build the full mode/v2 sampling contract, including reasoning (spec section 5.3)."""
    return Sampling(
        float(sampling["temp"]),
        float(sampling["top_p"]),
        cast(int, sampling["top_k"]),
        float(sampling["min_p"]),
        float(sampling["presence_penalty"]),
        float(sampling["repeat_penalty"]),
        cast(Literal["on", "off"], sampling["reasoning"]),
    )


def _mode(file: Traversable) -> Mode:
    """Construct a runtime mode from one validated mode/v2 resource.

    D-064 migrated the three modes to mode/v2, so the loader accepts only that schema and reads the
    extended sampling and reasoning fields (spec section 5.3).
    """
    raw = _read_object(file)
    if raw.get("schema") != "mode/v2":
        raise ContentError(f"{file.name}: mode schema must be 'mode/v2'")
    services = cast(JsonObject, raw["services"])
    return Mode(
        cast(str, raw["id"]),
        cast(str, raw["description"]),
        ModeServices(cast(bool, services["ui"]), cast(bool, services["vision"])),
        _sampling(cast(JsonObject, raw["sampling"])),
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


def load_catalog(root: Traversable | None = None) -> Catalog:
    """Validate one resource root before constructing its immutable runtime catalog."""
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


def _contains(memory_range: GibRange, value: float) -> bool:
    """Return whether an exact measurement belongs to an inclusive nominal class."""
    maximum = memory_range.maximum_gib
    return memory_range.minimum_gib <= value and (maximum is None or value <= maximum)


def _profile_applies(profile: Profile, request: LaunchRequest, hardware: HardwareInfo) -> bool:
    """Require exact compatibility before considering a shared profile as a search seed."""
    if not profile.is_engine_compatible or profile.model != request.config.model:
        return False
    if profile.match.backend != hardware.backend or profile.envelope_for(request.mode_id) is None:
        return False
    if profile.match.operating_systems and hardware.os_name not in profile.match.operating_systems:
        return False
    if not _contains(profile.match.ram_gib, hardware.ram_total_gib):
        return False
    if hardware.backend == "cpu":
        return True
    return hardware.vram_total_gib is not None and _contains(
        profile.match.vram_gib, hardware.vram_total_gib
    )


def _width(memory_range: GibRange) -> float:
    """Return class width, treating an open maximum as less specific than finite ranges."""
    if memory_range.maximum_gib is None:
        return inf
    return memory_range.maximum_gib - memory_range.minimum_gib


def _sort_key(profile: Profile, hardware: HardwareInfo) -> tuple[float, float, int, str]:
    """Build the deterministic CUDA or CPU specificity key from section 5.5."""
    os_rank = 0 if profile.match.operating_systems else 1
    ram_width = _width(profile.match.ram_gib)
    if hardware.backend == "cuda":
        return (_width(profile.match.vram_gib), ram_width, os_rank, profile.id)
    return (ram_width, 0.0, os_rank, profile.id)


def _select_seed_profile(
    request: LaunchRequest, catalog: Catalog, hardware: HardwareInfo
) -> tuple[Profile | None, tuple[str, ...]]:
    """Select the most specific shared seed and diagnose an id-only tie (section 5.5)."""
    matches = [
        profile for profile in catalog.profiles if _profile_applies(profile, request, hardware)
    ]
    if not matches:
        return None, ()
    matches.sort(key=lambda profile: _sort_key(profile, hardware))
    warning: tuple[str, ...] = ()
    if len(matches) > 1:
        first = _sort_key(matches[0], hardware)[:-1]
        second = _sort_key(matches[1], hardware)[:-1]
        if first == second:
            warning = ("Multiple equally specific profiles matched; selected by profile id.",)
    return matches[0], warning


def enforce_memory_gate(config: Config, hardware: HardwareInfo, *, force: bool) -> None:
    """Reject insufficient RAM only for the pinned default model unless force bypasses this gate.

    Only the default model carries measured thresholds, so section 5.5 applies the gate to it alone
    instead of guessing requirements for a model the project never measured.
    """
    if config.model != DEFAULT_MODEL or force:
        return
    total_ok = hardware.ram_total_gib >= DEFAULT_MODEL_MIN_TOTAL_GIB
    available_ok = hardware.ram_available_gib >= DEFAULT_MODEL_MIN_AVAILABLE_GIB
    if total_ok and available_ok:
        return
    message = (
        "the default model requires at least 28 GiB total RAM and 22 GiB available RAM; "
        "free memory or pass --force to bypass only this memory gate"
    )
    raise PlanError(message)


def _fallback(request: LaunchRequest, hardware: HardwareInfo) -> tuple[Envelope, tuple[str, ...]]:
    """Return the verified spike baseline while making its uncalibrated status explicit."""
    n_cpu_moe = _FALLBACK_CUDA_N_CPU_MOE if hardware.backend == "cuda" else None
    if request.config.model == DEFAULT_MODEL:
        warning = (
            "No local calibration record matched; using the non-optimized baseline. "
            "Run `bora calibrate` to optimize this machine."
        )
    else:
        warning = (
            "This model has no local calibration record; using the default model's baseline "
            "without performance or compatibility guarantees."
        )
    return Envelope(FALLBACK_CTX, n_cpu_moe, None), (warning,)


@dataclass(frozen=True, slots=True)
class EnvelopeChoice:
    """Hold the envelope a launch will use together with everything the operator must be told."""

    profile_id: str | None
    envelope: Envelope
    warnings: tuple[str, ...] = ()
    alerts: tuple[str, ...] = ()


def _shortage_alerts(mode_id: str, evaluation: RecordEvaluation) -> tuple[str, ...]:
    """Report a measured cell refused for lack of free memory rather than dropping it quietly.

    The fallback is otherwise indistinguishable from never having calibrated, and the context it
    imposes is what a connected chat interface then reports as its own limit (D-097).
    """
    if evaluation.status != "insufficient-headroom":
        return ()
    measured = "" if evaluation.ctx is None else f" measured at ctx {evaluation.ctx}"
    headline = (
        f"the calibrated {mode_id} profile{measured} needs more free memory than this machine "
        f"has now, so {mode_id} launches at the baseline ctx {FALLBACK_CTX} instead"
    )
    advice = "Close applications holding RAM or VRAM, then start this mode again."
    return (headline, *evaluation.diagnostics, advice)


def _record_evaluation(
    request: LaunchRequest, mode: Mode, hardware: HardwareInfo
) -> RecordEvaluation:
    """Evaluate the mode's local record against the current lock identity (section 5.5).

    Both imports stay local: `engine` reads `LaunchPlan` from this module, and the calibration
    layer sits above it, so importing either at module scope would be a cycle or an inversion.
    """
    from bora_workbench._calibration_reuse import ReuseQuery, evaluate_record
    from bora_workbench.engine import load_engine_lock

    query = ReuseQuery(request.config, mode, hardware, load_engine_lock())
    return evaluate_record(query)


def _resolve_envelope(
    request: LaunchRequest, catalog: Catalog, hardware: HardwareInfo
) -> EnvelopeChoice:
    """Prefer a compatible local record, otherwise the verified baseline (section 5.5).

    Shared seeds never become the envelope because D-034 forbids treating them as locally
    calibrated; only a supported active local calibration record may steer the plan, so a matched
    seed only contributes a warning. A record refused for memory reports through the alert channel
    alone, because the generic "no record matched" warning would then be untrue (D-097).
    """
    mode = catalog.mode(request.mode_id)
    assert mode is not None
    evaluation = _record_evaluation(request, mode, hardware)
    seed, warnings = _select_seed_profile(request, catalog, hardware)
    if evaluation.status == "valid":
        envelope = Envelope(cast(int, evaluation.ctx), evaluation.n_cpu_moe, None)
        return EnvelopeChoice("local-calibration-record", envelope)
    envelope, fallback_warnings = _fallback(request, hardware)
    alerts = _shortage_alerts(mode.id, evaluation)
    if not alerts:
        warnings += fallback_warnings
        if evaluation.status != "missing":
            warnings += evaluation.diagnostics
    if seed is not None:
        warnings += (
            f"Shared profile {seed.id!r} is reference-only; local calibration is required.",
        )
    return EnvelopeChoice(None, envelope, warnings, alerts)


def build_launch_plan(
    request: LaunchRequest, catalog: Catalog, hardware: HardwareInfo
) -> LaunchPlan:
    """Assemble the immutable plan that fuses mode behavior, envelope, model, and hardware."""
    mode = catalog.mode(request.mode_id)
    if mode is None:
        valid = ", ".join(item.id for item in catalog.modes)
        raise PlanError(f"unknown mode {request.mode_id!r}; valid modes: {valid}")
    choice = _resolve_envelope(request, catalog, hardware)
    return LaunchPlan(
        mode,
        request.config.model,
        request.model_path,
        request.mmproj_path,
        request.config.llama_port,
        choice.profile_id,
        choice.envelope.ctx,
        choice.envelope.n_cpu_moe,
        hardware.backend,
        hardware.gpu_index,
        hardware.warnings + choice.warnings,
        choice.alerts,
        "disabled" if mode.services.vision else "mtp2",
    )
