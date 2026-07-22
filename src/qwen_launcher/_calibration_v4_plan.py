"""Build candidate-specific launch plans for calibration/v4 trials."""

from __future__ import annotations

from typing import Protocol

from qwen_launcher._calibration_port import select_trial_port
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.profiles import LaunchPlan, Mode


class ModeRun(Protocol):
    """Expose only mode-run fields needed to build one trial plan."""

    target: CalibrationTarget
    mode: Mode


def build_plan(run: ModeRun, ctx: int, n_cpu_moe: int | None) -> LaunchPlan:
    """Build a candidate plan retaining mode behavior and verified artifacts."""
    target = run.target
    return LaunchPlan(
        run.mode,
        target.config.model,
        target.model_path,
        target.mmproj_path if run.mode.services.vision else None,
        select_trial_port(target.config.llama_port),
        None,
        ctx,
        n_cpu_moe,
        target.hardware.backend,
        target.hardware.gpu_index,
        (),
    )
