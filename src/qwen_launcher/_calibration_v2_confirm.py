"""Confirm calibration/v2 finalists with stable starts, drift checks, and benchmark/v1.

A screening probe only proves feasibility; a finalist must additionally survive the required fresh
stable starts with bounded baseline drift and complete a full benchmark/v1 with verified VRAM
release (design document section 3, step 3). Failures here discard only the finalist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_v2_process import TrialFailure, TrialSpec, run_trial
from qwen_launcher._calibration_v2_types import (
    RELEASE_TOLERANCE_GIB,
    STABLE_START_RUNS,
    FinalistEvidence,
)
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.profiles import LaunchPlan

if TYPE_CHECKING:
    from qwen_launcher._calibration_v2_runner import _ModeRun

_DRIFT_REASON = "GPU baseline drift exceeded release tolerance between stable starts"


def build_plan(run: _ModeRun, ctx: int, n_cpu_moe: int | None) -> LaunchPlan:
    """Build a candidate-specific plan retaining mode behavior and verified artifacts."""
    target = run.target
    return LaunchPlan(
        run.mode,
        target.config.model,
        target.model_path,
        target.mmproj_path if run.mode.services.vision else None,
        target.config.llama_port,
        None,
        ctx,
        n_cpu_moe,
        target.hardware.backend,
        target.hardware.gpu_index,
        (),
    )


def _combine_vram(summaries: list[VramSummary]) -> VramSummary | None:
    """Combine all stable-start measurements into conservative finalist evidence."""
    if not summaries:
        return None
    baseline = summaries[0]
    return VramSummary(
        baseline.baseline_used_gib,
        max(item.peak_used_gib for item in summaries),
        min(item.minimum_free_gib for item in summaries),
        max(item.release_used_gib for item in summaries),
        baseline.driver_version,
    )


def _combine_ram(summaries: list[RamSummary]) -> RamSummary | None:
    """Combine all stable-start RAM measurements into conservative finalist evidence."""
    if not summaries:
        return None
    return RamSummary(
        summaries[0].baseline_available_gib,
        min(item.minimum_available_gib for item in summaries),
    )


@dataclass(slots=True)
class _Confirmation:
    """Collect partial evidence across the stable starts of one finalist."""

    ctx: int
    n_cpu_moe: int | None
    benchmark: BenchmarkResult | None = None
    vram_summaries: list[VramSummary] = field(default_factory=list)
    ram_summaries: list[RamSummary] = field(default_factory=list)

    def absorb(self, vram: VramSummary | None, ram: RamSummary | None) -> None:
        """Retain whatever monitor evidence one start produced."""
        if vram is not None:
            self.vram_summaries.append(vram)
        if ram is not None:
            self.ram_summaries.append(ram)

    def has_baseline_drift(self) -> bool:
        """Return whether stable-start baselines span more than the declared tolerance."""
        if len(self.vram_summaries) < 2:
            return False
        baselines = [summary.baseline_used_gib for summary in self.vram_summaries]
        return max(baselines) - min(baselines) > RELEASE_TOLERANCE_GIB

    def finished(self, reason: str | None) -> FinalistEvidence:
        """Assemble the finalist result from every collected measurement."""
        return FinalistEvidence(
            self.ctx,
            self.n_cpu_moe,
            "valid" if reason is None else "discarded",
            reason,
            self.benchmark if reason is None else None,
            _combine_vram(self.vram_summaries),
            _combine_ram(self.ram_summaries),
        )


def confirm_finalist(run: _ModeRun, ctx: int, n_cpu_moe: int | None) -> FinalistEvidence:
    """Run the required stable starts for one finalist, discarding it on expected failure."""
    progress = _Confirmation(ctx, n_cpu_moe)
    label = "baseline" if n_cpu_moe is None else f"n{n_cpu_moe}"
    for index in range(STABLE_START_RUNS):
        root = run.runtime_root / run.mode.id / f"final-ctx{ctx}-{label}-start{index + 1}"
        spec = TrialSpec(build_plan(run, ctx, n_cpu_moe), root, index + 1 == STABLE_START_RUNS)
        try:
            measured = run_trial(run.target, spec)
        except TrialFailure as failure:
            progress.absorb(failure.vram, failure.ram)
            if failure.vram is not None:
                run.drivers.add(failure.vram.driver_version)
            return progress.finished(str(failure.error))
        progress.benchmark = measured.benchmark or progress.benchmark
        progress.absorb(measured.vram, measured.ram)
        if measured.vram is not None:
            run.drivers.add(measured.vram.driver_version)
        if progress.has_baseline_drift():
            return progress.finished(_DRIFT_REASON)
    if progress.benchmark is None:
        return progress.finished("final stable start produced no benchmark/v1 result")
    return progress.finished(None)
