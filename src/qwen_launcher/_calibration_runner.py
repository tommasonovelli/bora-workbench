"""Execute isolated fresh-process calibration trials for every explicit candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_port import select_trial_port
from qwen_launcher._calibration_process import StartFailure, StartSpec, run_start
from qwen_launcher._calibration_types import (
    CandidateTrial,
    ModeTrials,
    TrialResult,
    discard_reason,
    select_candidate,
)
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationSettings,
    CalibrationTarget,
    Candidate,
)
from qwen_launcher.profiles import LaunchPlan, Mode


@dataclass(slots=True)
class _CandidateProgress:
    """Collect partial evidence needed for either a valid or discarded candidate result."""

    candidate: Candidate
    root: Path
    summaries: list[VramSummary]
    successful: int = 0
    benchmark: BenchmarkResult | None = None


@dataclass(frozen=True, slots=True)
class _TrialContext:
    """Group immutable target, settings, and isolated runtime root for trial helpers."""

    target: CalibrationTarget
    settings: CalibrationSettings
    runtime_root: Path


def _plan(target: CalibrationTarget, mode: Mode, candidate: Candidate) -> LaunchPlan:
    """Build a candidate-specific plan while retaining mode behavior and verified artifacts."""
    return LaunchPlan(
        mode,
        target.config.model,
        target.model_path,
        target.mmproj_path if mode.services.vision else None,
        select_trial_port(target.config.llama_port),
        None,
        candidate.ctx,
        candidate.n_cpu_moe,
        target.hardware.backend,
        target.hardware.gpu_index,
        (),
    )


def _logs(root: Path) -> tuple[Path, ...]:
    """Return all process logs below one candidate run tree in deterministic order."""
    return tuple(sorted(root.glob("start-*/logs/*.log")))


def _combine_vram(summaries: list[VramSummary]) -> VramSummary | None:
    """Combine all stable-start measurements into conservative candidate evidence."""
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


def _baseline_drifted(progress: _CandidateProgress, tolerance_gib: float | None) -> bool:
    """Return whether stable-start baselines span more than the explicit tolerance."""
    if tolerance_gib is None or len(progress.summaries) < 2:
        return False
    baselines = [summary.baseline_used_gib for summary in progress.summaries]
    return max(baselines) - min(baselines) > tolerance_gib


def _drift_error() -> CalibrationError:
    """Build the candidate-level diagnosis for excessive baseline drift."""
    return CalibrationError("GPU baseline drift exceeded release tolerance between stable starts")


def _discarded(progress: _CandidateProgress, error: Exception) -> CandidateTrial:
    """Build one discarded result from all partial process and VRAM evidence."""
    logs = _logs(progress.root)
    return CandidateTrial(
        progress.candidate,
        "discarded",
        discard_reason(error, logs),
        progress.successful,
        None,
        _combine_vram(progress.summaries),
        logs,
    )


def _valid(progress: _CandidateProgress) -> CandidateTrial:
    """Build one valid candidate only after its final benchmark completed."""
    if progress.benchmark is None:
        raise CalibrationError("final stable start produced no benchmark/v1 result")
    return CandidateTrial(
        progress.candidate,
        "valid",
        None,
        progress.successful,
        progress.benchmark,
        _combine_vram(progress.summaries),
        _logs(progress.root),
    )


def _run_candidate(context: _TrialContext, mode: Mode, candidate: Candidate) -> CandidateTrial:
    """Run required stable starts, discarding only this candidate on expected failure."""
    target = context.target
    settings = context.settings
    root = context.runtime_root / mode.id / candidate.id
    plan = _plan(target, mode, candidate)
    progress = _CandidateProgress(candidate, root, [])
    try:
        for index in range(settings.stable_start_runs):
            start_root = root / f"start-{index + 1}"
            spec = StartSpec(plan, start_root, index + 1 == settings.stable_start_runs)
            measured, vram = run_start(target, settings, spec)
            progress.successful += 1
            progress.benchmark = measured or progress.benchmark
            if vram is not None:
                progress.summaries.append(vram)
                if _baseline_drifted(progress, settings.vram_release_tolerance_gib):
                    raise _drift_error()
        return _valid(progress)
    except KeyboardInterrupt:
        raise
    except StartFailure as failure:
        if failure.vram is not None:
            progress.summaries.append(failure.vram)
        if _baseline_drifted(progress, settings.vram_release_tolerance_gib):
            return _discarded(progress, _drift_error())
        if target.hardware.backend == "cuda" and not progress.summaries:
            raise CalibrationError(
                f"cannot preserve CUDA failure evidence: {failure.error}"
            ) from failure
        return _discarded(progress, failure.error)
    except Exception as error:
        return _discarded(progress, error)


def run_trials(
    target: CalibrationTarget, settings: CalibrationSettings, runtime_root: Path
) -> TrialResult:
    """Run modes and candidates in declared order without modifying production service state."""
    context = _TrialContext(target, settings, runtime_root)
    modes: list[ModeTrials] = []
    for mode in target.modes:
        trials = tuple(
            _run_candidate(context, mode, candidate) for candidate in settings.candidates
        )
        modes.append(ModeTrials(mode, trials, select_candidate(trials)))
    drivers = {
        trial.vram.driver_version
        for mode in modes
        for trial in mode.candidates
        if trial.vram is not None
    }
    if len(drivers) > 1:
        raise CalibrationError("GPU driver version changed during calibration")
    return TrialResult(tuple(modes), next(iter(drivers), None))
