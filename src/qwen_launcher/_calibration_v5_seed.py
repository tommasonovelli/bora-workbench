"""Resolve shared evidence into a probe-ordering hint only.

Reference reports and historical profiles may reorder the same complete local search; they never
narrow its metadata-derived domain and never become the final envelope (D-035 and D-047).
"""

from __future__ import annotations

from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.profiles import LaunchRequest, Mode


def _reference_seed(target: CalibrationTarget, mode: Mode, domain_maximum: int) -> int | None:
    """Select an exact model/engine/backend v3 evidence seed in deterministic report order."""
    matches = sorted(
        (
            seed
            for seed in target.catalog.calibration_seeds
            if seed.model == target.config.model
            and seed.engine == target.lock["release"]
            and seed.backend == target.hardware.backend
            and seed.mode_id == mode.id
            and 0 <= seed.n_cpu_moe < domain_maximum
        ),
        key=lambda seed: seed.report_id,
    )
    return matches[0].n_cpu_moe if matches else None


def _profile_seed(target: CalibrationTarget, mode: Mode, domain_maximum: int) -> int | None:
    """Fall back to a compatible historical profile while preserving ordering-only semantics."""
    from qwen_launcher._profile_matching import select_seed_profile

    request = LaunchRequest(target.config, mode.id, target.model_path, target.mmproj_path)
    profile, _warnings = select_seed_profile(request, target.catalog, target.hardware)
    if profile is None:
        return None
    envelope = profile.envelope_for(mode.id)
    if envelope is None or envelope.n_cpu_moe is None:
        return None
    value = envelope.n_cpu_moe
    return value if 0 <= value < domain_maximum else None


def seed_probe_value(target: CalibrationTarget, mode: Mode, domain_maximum: int) -> int | None:
    """Return one ordering hint without changing the complete metadata-derived domain."""
    reference = _reference_seed(target, mode, domain_maximum)
    return reference if reference is not None else _profile_seed(target, mode, domain_maximum)
