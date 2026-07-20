"""Apply local-record reuse, seed matching, and the verified fallback envelope."""

from __future__ import annotations

from math import inf
from typing import TYPE_CHECKING, cast

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

if TYPE_CHECKING:
    from qwen_launcher._calibration_reuse import RecordEvaluation

_FALLBACK_CTX = 8192
_FALLBACK_CUDA_N_CPU_MOE = 48


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


def select_seed_profile(
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
            "Run `qwen-launcher calibrate` to optimize this machine."
        )
    else:
        warning = (
            "This model has no local calibration record; using the default model's baseline "
            "without performance or compatibility guarantees."
        )
    return Envelope(_FALLBACK_CTX, n_cpu_moe, None), (warning,)


def _record_evaluation(request: LaunchRequest, hardware: HardwareInfo) -> RecordEvaluation:
    """Evaluate the mode's local record against the current lock identity (section 5.5)."""
    from qwen_launcher._calibration_reuse import ReuseQuery, evaluate_record
    from qwen_launcher.engine import load_engine_lock

    query = ReuseQuery(request.config, request.mode_id, hardware, load_engine_lock())
    return evaluate_record(query)


def build_plan(request: LaunchRequest, catalog: Catalog, hardware: HardwareInfo) -> LaunchPlan:
    """Prefer a compatible local record, otherwise the verified baseline (section 5.5).

    Shared seeds never become the envelope because D-034 forbids treating them as locally
    calibrated; only an active record produced by calibration/v3 on this machine may steer the plan.
    """
    mode = catalog.mode(request.mode_id)
    if mode is None:
        valid = ", ".join(item.id for item in catalog.modes)
        raise PlanError(f"unknown mode {request.mode_id!r}; valid modes: {valid}")
    evaluation = _record_evaluation(request, hardware)
    seed, warnings = select_seed_profile(request, catalog, hardware)
    if evaluation.status == "valid":
        profile_id = "local-calibration-record"
        envelope = Envelope(cast(int, evaluation.ctx), evaluation.n_cpu_moe, None)
        warnings = ()
    else:
        profile_id = None
        envelope, fallback_warnings = _fallback(request, hardware)
        warnings += fallback_warnings
        if evaluation.status != "missing":
            warnings += evaluation.diagnostics
        if seed is not None:
            warnings += (
                f"Shared profile {seed.id!r} is reference-only; local calibration is required.",
            )
    return LaunchPlan(
        mode,
        request.config.model,
        request.model_path,
        request.mmproj_path,
        request.config.llama_port,
        profile_id,
        envelope.ctx,
        envelope.n_cpu_moe,
        hardware.backend,
        hardware.gpu_index,
        hardware.warnings + warnings,
    )
