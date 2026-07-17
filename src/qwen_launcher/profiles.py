"""Load shared profile seeds and build immutable baseline or local launch plans."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal

from qwen_launcher.config import Config
from qwen_launcher.hardware import HardwareInfo


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
    """Hold immutable validated modes and profiles loaded from one resource root."""

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


DEFAULT_MODEL_MIN_TOTAL_GIB = 28.0
DEFAULT_MODEL_MIN_AVAILABLE_GIB = 24.0


def load_catalog(root: Traversable | None = None) -> Catalog:
    """Validate and load package content, refusing any validation error."""
    from qwen_launcher._profile_loading import load_catalog_from_root

    return load_catalog_from_root(root)


def enforce_memory_gate(config: Config, hardware: HardwareInfo, *, force: bool) -> None:
    """Enforce the default-model total and available RAM gate from section 5.5."""
    from qwen_launcher._profile_matching import enforce_memory_gate_for_launch

    enforce_memory_gate_for_launch(config, hardware, force=force)


def build_launch_plan(
    request: LaunchRequest, catalog: Catalog, hardware: HardwareInfo
) -> LaunchPlan:
    """Build the verified baseline while shared profiles remain reference-only seeds."""
    from qwen_launcher._profile_matching import build_plan

    return build_plan(request, catalog, hardware)
