"""Apply exact profile matching and the verified Step 3 fallback envelope."""

from __future__ import annotations

from math import inf

from qwen_launcher.config import DEFAULT_MODEL, Config
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import (
    Catalog,
    Envelope,
    GibRange,
    LaunchPlan,
    LaunchRequest,
    PlanError,
    Profile,
)

_FALLBACK_CTX = 8192
_FALLBACK_CUDA_N_CPU_MOE = 48


def _contains(memory_range: GibRange, value: float) -> bool:
    """Return whether an exact measurement belongs to an inclusive nominal class."""
    maximum = memory_range.maximum_gib
    return memory_range.minimum_gib <= value and (maximum is None or value <= maximum)


def _profile_applies(profile: Profile, request: LaunchRequest, hardware: HardwareInfo) -> bool:
    """Require exact identity, engine, mode, backend, OS, RAM, and VRAM compatibility."""
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


def _select_profile(
    request: LaunchRequest, catalog: Catalog, hardware: HardwareInfo
) -> tuple[Profile | None, tuple[str, ...]]:
    """Select the most specific applicable profile and diagnose an id-only tie."""
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


def enforce_memory_gate_for_launch(config: Config, hardware: HardwareInfo, *, force: bool) -> None:
    """Reject insufficient RAM only for the pinned default model unless force bypasses this gate."""
    from qwen_launcher.profiles import (
        DEFAULT_MODEL_MIN_AVAILABLE_GIB,
        DEFAULT_MODEL_MIN_TOTAL_GIB,
    )

    if config.model != DEFAULT_MODEL or force:
        return
    total_ok = hardware.ram_total_gib >= DEFAULT_MODEL_MIN_TOTAL_GIB
    available_ok = hardware.ram_available_gib >= DEFAULT_MODEL_MIN_AVAILABLE_GIB
    if total_ok and available_ok:
        return
    message = (
        "the default model requires at least 28 GiB total RAM and 24 GiB available RAM; "
        "free memory or pass --force to bypass only this memory gate"
    )
    raise PlanError(message)


def _fallback(request: LaunchRequest, hardware: HardwareInfo) -> tuple[Envelope, tuple[str, ...]]:
    """Return the verified spike baseline while making its uncalibrated status explicit."""
    n_cpu_moe = _FALLBACK_CUDA_N_CPU_MOE if hardware.backend == "cuda" else None
    if request.config.model == DEFAULT_MODEL:
        warning = "No calibrated profile matched; using the verified, non-optimized baseline."
    else:
        warning = (
            "This model has no calibrated profile; using the default model's baseline without "
            "performance or compatibility guarantees."
        )
    return Envelope(_FALLBACK_CTX, n_cpu_moe, None), (warning,)


def build_plan(request: LaunchRequest, catalog: Catalog, hardware: HardwareInfo) -> LaunchPlan:
    """Fuse one valid mode with an exact profile or the declared fallback envelope."""
    mode = catalog.mode(request.mode_id)
    if mode is None:
        valid = ", ".join(item.id for item in catalog.modes)
        raise PlanError(f"unknown mode {request.mode_id!r}; valid modes: {valid}")
    profile, warnings = _select_profile(request, catalog, hardware)
    if profile is None:
        envelope, fallback_warnings = _fallback(request, hardware)
        warnings += fallback_warnings
    else:
        envelope = profile.envelope_for(request.mode_id)
        if envelope is None:  # Defensive: _profile_applies already excludes this case.
            raise PlanError(f"profile {profile.id!r} does not cover mode {request.mode_id!r}")
    return LaunchPlan(
        mode,
        request.config.model,
        request.model_path,
        request.mmproj_path,
        request.config.llama_port,
        None if profile is None else profile.id,
        envelope.ctx,
        envelope.n_cpu_moe,
        hardware.backend,
        hardware.gpu_index,
        hardware.warnings + warnings,
    )
