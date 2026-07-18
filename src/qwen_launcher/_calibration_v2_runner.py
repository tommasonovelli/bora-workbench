"""Coordinate the adaptive calibration/v2 search and its per-mode local records.

Per mode, the runner predicts the axis domain from GGUF metadata, descends the approved context
scale only when the most prudent envelope is infeasible, screens by measured bisection, confirms
the finalists with stable starts plus benchmark/v1, selects with the noise-robust rule, and writes
the local record atomically for immediate reuse (D-038; design document section 3).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from uuid import uuid4

from qwen_launcher._calibration_gguf import GgufError, read_block_count
from qwen_launcher._calibration_ram import RamError
from qwen_launcher._calibration_record import build_record, write_record
from qwen_launcher._calibration_v2_confirm import build_plan, confirm_finalist
from qwen_launcher._calibration_v2_process import TrialFailure, TrialSpec, run_trial
from qwen_launcher._calibration_v2_search import (
    ProbeMeasurement,
    ScreeningPlan,
    ScreeningResult,
    screen,
    select_candidate_index,
)
from qwen_launcher._calibration_v2_types import (
    CONTEXT_SCALE,
    CPU_BASELINE_CTX,
    MODE_PROBE_CAP,
    SELECTION_CPU_BASELINE,
    FinalistEvidence,
    ModeCalibration,
    ProbeRecord,
    SelectionCandidate,
    V2Outcome,
)
from qwen_launcher._calibration_vram import VramEnvironmentError
from qwen_launcher.calibration import CalibrationError, CalibrationTarget
from qwen_launcher.paths import data_dir
from qwen_launcher.profiles import Mode


@dataclass(slots=True)
class _ModeRun:
    """Track one mode's probe budget, evidence, and observed driver identity."""

    target: CalibrationTarget
    mode: Mode
    runtime_root: Path
    domain_maximum: int
    seed: int | None
    probes: list[ProbeRecord] = field(default_factory=list)
    drivers: set[str] = field(default_factory=set)


def _probe_reason(root: Path, failure: TrialFailure) -> str:
    """Classify one infeasible probe, preserving OOM evidence from its process logs."""
    from qwen_launcher._calibration_types import discard_reason

    return discard_reason(failure.error, tuple(sorted(root.glob("logs/*.log"))))


def run_probe(run: _ModeRun, ctx: int, value: int) -> ProbeMeasurement:
    """Run one fresh screening probe and record its measured outcome (design §3.2)."""
    root = run.runtime_root / run.mode.id / f"probe-ctx{ctx}-n{value}"
    spec = TrialSpec(build_plan(run, ctx, value), root, False)
    try:
        measured = run_trial(run.target, spec)
    except TrialFailure as failure:
        peak = None if failure.vram is None else failure.vram.peak_used_gib
        if failure.vram is not None:
            run.drivers.add(failure.vram.driver_version)
        run.probes.append(ProbeRecord(ctx, value, False, _probe_reason(root, failure), peak))
        return ProbeMeasurement(False, peak)
    peak = None if measured.vram is None else measured.vram.peak_used_gib
    if measured.vram is not None:
        run.drivers.add(measured.vram.driver_version)
    run.probes.append(ProbeRecord(ctx, value, True, None, peak))
    return ProbeMeasurement(True, peak)


def _screen_context(run: _ModeRun) -> tuple[int, ScreeningResult]:
    """Descend the approved context scale until the most prudent envelope is feasible."""
    for ctx in CONTEXT_SCALE:
        if len(run.probes) >= MODE_PROBE_CAP:
            break
        prudent = run_probe(run, ctx, run.domain_maximum)
        if not prudent.is_feasible:
            continue
        budget = MODE_PROBE_CAP - len(run.probes)
        plan = ScreeningPlan(run.domain_maximum, prudent.peak_used_gib, run.seed, budget)
        return ctx, screen(partial(run_probe, run, ctx), plan)
    raise CalibrationError(
        f"mode {run.mode.id}: no feasible envelope found within {MODE_PROBE_CAP} probes on the "
        "approved context scale; free VRAM or stop concurrent workloads, then retry"
    )


def _selection_candidate(finalist: FinalistEvidence) -> SelectionCandidate:
    """Project one valid finalist onto the fields the selection rule reads."""
    assert finalist.benchmark is not None
    free = None if finalist.vram is None else finalist.vram.minimum_free_gib
    return SelectionCandidate(
        finalist.benchmark.tok_s.median,
        max(finalist.benchmark.measured_tok_s),
        free,
        finalist.n_cpu_moe,
    )


def _cuda_mode(run: _ModeRun) -> ModeCalibration:
    """Screen, confirm, and select one CUDA mode at a single comparable context."""
    ctx, screening = _screen_context(run)
    values = [screening.boundary]
    if screening.boundary < run.domain_maximum:
        values.append(screening.boundary + 1)
    finalists = tuple(confirm_finalist(run, ctx, value) for value in values)
    valid = tuple(finalist for finalist in finalists if finalist.outcome == "valid")
    if not valid:
        reasons = "; ".join(finalist.discard_reason or "unknown" for finalist in finalists)
        raise CalibrationError(
            f"mode {run.mode.id}: no finalist passed confirmation ({reasons}); "
            "the non-optimized baseline remains active"
        )
    index, rule = select_candidate_index(tuple(_selection_candidate(f) for f in valid))
    return ModeCalibration(
        run.mode, ctx, tuple(run.probes), screening.did_degrade, finalists, valid[index], rule
    )


def _cpu_mode(run: _ModeRun) -> ModeCalibration:
    """Confirm the engine's auto-configured CPU baseline honestly (design §3, step 8)."""
    finalist = confirm_finalist(run, CPU_BASELINE_CTX, None)
    if finalist.outcome != "valid":
        raise CalibrationError(
            f"mode {run.mode.id}: the CPU baseline failed confirmation "
            f"({finalist.discard_reason}); the non-optimized baseline remains active"
        )
    return ModeCalibration(
        run.mode, CPU_BASELINE_CTX, (), False, (finalist,), finalist, SELECTION_CPU_BASELINE
    )


def _mode_run(target: CalibrationTarget, mode: Mode, runtime_root: Path) -> _ModeRun:
    """Predict the mode's axis domain and seed-only probe ordering (design §3, steps 1 and 7)."""
    if target.hardware.backend == "cpu":
        return _ModeRun(target, mode, runtime_root, 0, None)
    try:
        block_count = read_block_count(target.model_path)
    except GgufError as error:
        raise CalibrationError(str(error)) from error
    from qwen_launcher._calibration_v2_seed import seed_probe_value

    return _ModeRun(target, mode, runtime_root, block_count, seed_probe_value(target, mode))


def run_calibration_v2(
    target: CalibrationTarget, destination_root: Path | None = None
) -> V2Outcome:
    """Search, confirm, select, and atomically record every selected mode (D-038)."""
    root = (data_dir() / "calibration") if destination_root is None else destination_root
    runtime_root = root / f".runtime-{uuid4().hex}"
    calibrations: list[ModeCalibration] = []
    paths: list[Path] = []
    drivers: set[str] = set()
    try:
        for mode in target.modes:
            run = _mode_run(target, mode, runtime_root)
            is_cpu = target.hardware.backend == "cpu"
            calibration = _cpu_mode(run) if is_cpu else _cuda_mode(run)
            drivers |= run.drivers
            if len(drivers) > 1:
                raise CalibrationError("GPU driver version changed during calibration")
            document = build_record(target, calibration)
            paths.append(write_record(document, root / "records" / f"{mode.id}.json"))
            calibrations.append(calibration)
        return V2Outcome(tuple(calibrations), tuple(paths))
    except (VramEnvironmentError, RamError) as error:
        raise CalibrationError(f"calibration run invalidated: {error}") from error
    except OSError as error:
        raise CalibrationError(str(error)) from error
    finally:
        shutil.rmtree(runtime_root, ignore_errors=True)
