"""Collect calibration/v3 screening probes and find one fixed-context boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path

from qwen_launcher._calibration_gpu_contexts import GpuContextBaseline
from qwen_launcher._calibration_v3_plan import build_plan
from qwen_launcher._calibration_v3_process import TrialFailure, TrialSpec, run_trial
from qwen_launcher._calibration_v3_search import (
    ProbeMeasurement,
    ScreeningPlan,
    ScreeningResult,
    screen,
)
from qwen_launcher._calibration_v3_types import (
    CONTEXT_SCALE,
    MODE_PROBE_CAP,
    VRAM_RESERVE_GIB,
    ProbeRecord,
    ProgressEvent,
    TrialEvidence,
    TrialOrder,
    V3RunOptions,
)
from qwen_launcher.calibration import CalibrationRunError, CalibrationTarget
from qwen_launcher.profiles import Mode


@dataclass(frozen=True, slots=True)
class ModeRunRequest:
    """Group one mode's immutable target, runtime location, prediction, and options."""

    target: CalibrationTarget
    mode: Mode
    runtime_root: Path
    domain_maximum: int
    seed: int | None
    gpu_context_baseline: GpuContextBaseline | None
    options: V3RunOptions


@dataclass(slots=True)
class _ModeRun:
    """Track one mode's budget, evidence, timing estimate, and driver identity."""

    target: CalibrationTarget
    mode: Mode
    runtime_root: Path
    domain_maximum: int
    seed: int | None
    gpu_context_baseline: GpuContextBaseline | None
    options: V3RunOptions
    probes: list[ProbeRecord] = field(default_factory=list)
    drivers: set[str] = field(default_factory=set)
    trial_durations: list[float] = field(default_factory=list)
    finalist_values: tuple[int | None, ...] = ()

    def note_duration(self, evidence: TrialEvidence) -> None:
        """Learn one process duration from its stored UTC boundaries."""
        started = datetime.fromisoformat(evidence.started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(evidence.finished_at.replace("Z", "+00:00"))
        self.trial_durations.append(max(0.0, (finished - started).total_seconds()))

    def report_progress(self, phase: str, completed: int, total: int) -> None:
        """Emit phase progress and an estimate only after two local process durations."""
        callback = self.options.progress
        if callback is None:
            return
        estimate = None
        if len(self.trial_durations) >= 2:
            average = sum(self.trial_durations) / len(self.trial_durations)
            estimate = average * max(0, total - completed)
        callback(ProgressEvent(self.mode.id, phase, completed, total, estimate))


def create_mode_run(request: ModeRunRequest) -> _ModeRun:
    """Create mutable mode state from one grouped request."""
    return _ModeRun(
        request.target,
        request.mode,
        request.runtime_root,
        request.domain_maximum,
        request.seed,
        request.gpu_context_baseline,
        request.options,
    )


def _probe_reason(root: Path, failure: TrialFailure) -> str:
    """Classify one infeasible probe, preserving OOM evidence from its process logs."""
    from qwen_launcher._calibration_types import discard_reason

    return discard_reason(failure.error, tuple(sorted(root.glob("logs/*.log"))))


def run_probe(run: _ModeRun, ctx: int, value: int) -> ProbeMeasurement:
    """Run one fresh screening probe and record reduced per-process evidence."""
    sequence = len(run.probes) + 1
    root = run.runtime_root / run.mode.id / f"probe-{sequence}-ctx{ctx}-n{value}"
    order = TrialOrder("screening", sequence)
    spec = TrialSpec(
        build_plan(run, ctx, value),
        root,
        False,
        run.runtime_root,
        order,
        run.gpu_context_baseline,
    )
    try:
        measured = run_trial(run.target, spec)
    except TrialFailure as failure:
        evidence = failure.evidence
        reason = _probe_reason(root, failure)
        is_feasible = False
    else:
        evidence = measured.evidence
        reason = None
        is_feasible = True
    if evidence.vram is not None:
        run.drivers.add(evidence.vram.driver_version)
    run.probes.append(ProbeRecord(ctx, value, is_feasible, reason, evidence))
    run.note_duration(evidence)
    run.report_progress("screening", sequence, MODE_PROBE_CAP)
    peak = None if evidence.vram is None else evidence.vram.peak_used_gib
    return ProbeMeasurement(is_feasible, peak)


def _contexts(options: V3RunOptions) -> tuple[int, ...]:
    """Return the full approved scale or one expert-selected target rung."""
    if options.target_ctx is None:
        return CONTEXT_SCALE
    if options.target_ctx not in CONTEXT_SCALE:
        allowed = ", ".join(str(value) for value in CONTEXT_SCALE)
        raise CalibrationRunError(f"target context must be one of: {allowed}")
    return (options.target_ctx,)


def screen_context(run: _ModeRun) -> tuple[int, ScreeningResult]:
    """Descend context until the prudent envelope is feasible, then screen its axis."""
    for ctx in _contexts(run.options):
        if len(run.probes) >= MODE_PROBE_CAP:
            break
        prudent = run_probe(run, ctx, run.domain_maximum)
        if not prudent.is_feasible:
            continue
        budget = MODE_PROBE_CAP - len(run.probes)
        total_vram = run.target.hardware.vram_total_gib
        assert total_vram is not None
        plan = ScreeningPlan(
            run.domain_maximum,
            prudent.peak_used_gib,
            total_vram - VRAM_RESERVE_GIB,
            run.seed,
            budget,
        )
        return ctx, screen(partial(run_probe, run, ctx), plan)
    target = " at the requested context" if run.options.target_ctx is not None else ""
    raise CalibrationRunError(
        f"mode {run.mode.id}: no feasible envelope found{target} within the "
        f"{MODE_PROBE_CAP}-probe cap; free memory or stop workloads, then retry"
    )
