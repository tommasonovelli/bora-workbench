"""Turn the most specific shared profile seed into a probe-ordering hint only.

Shared profiles may reorder the probes of the same complete local search; they never narrow the
domain and never become the final envelope (D-035; design document section 3, step 7). Values at
or above the metadata-verified maximum are aliases of it and carry no ordering information.
"""

from __future__ import annotations

from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.profiles import LaunchRequest, Mode


def seed_probe_value(target: CalibrationTarget, mode: Mode) -> int | None:
    """Return the seed's ``n_cpu_moe`` for probe ordering, or None without a usable seed."""
    from qwen_launcher._profile_matching import select_seed_profile

    request = LaunchRequest(target.config, mode.id, target.model_path, target.mmproj_path)
    profile, _warnings = select_seed_profile(request, target.catalog, target.hardware)
    if profile is None:
        return None
    envelope = profile.envelope_for(mode.id)
    if envelope is None or envelope.n_cpu_moe is None or envelope.n_cpu_moe < 0:
        return None
    return envelope.n_cpu_moe
