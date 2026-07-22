"""Confirm and select one calibration/v4 mode after adaptive screening."""

from __future__ import annotations

from pathlib import Path

from qwen_launcher._calibration_gguf import GgufError, read_block_count
from qwen_launcher._calibration_gpu_contexts import GpuContextBaseline
from qwen_launcher._calibration_v4_confirm import confirm_finalists
from qwen_launcher._calibration_v4_screening import (
    ModeRunRequest,
    _ModeRun,
    create_mode_run,
    screen_context,
)
from qwen_launcher._calibration_v4_search import ScreeningResult, select_candidate_index
from qwen_launcher._calibration_v4_types import (
    CPU_BASELINE_CTX,
    EXPERT_CONTEXT_TARGETS,
    MODE_PROBE_CAP,
    RELEASE_TOLERANCE_GIB,
    SELECTION_CPU_BASELINE,
    FinalistEvidence,
    ModeCalibration,
    SelectionCandidate,
    V4RunOptions,
)
from qwen_launcher.calibration import CalibrationRunError, CalibrationTarget
from qwen_launcher.profiles import Mode


def _round_medians(finalist: FinalistEvidence) -> tuple[float, ...]:
    """Derive paired round medians from complete benchmark/v1 sessions."""
    values = []
    for session in finalist.sessions:
        if session.benchmark is None:
            raise ValueError("valid finalist session has no benchmark")
        values.append(session.benchmark.tok_s.median)
    return tuple(values)


def _selection_candidate(finalist: FinalistEvidence) -> SelectionCandidate:
    """Project one valid finalist onto paired medians and deterministic tie-break fields."""
    free = None if finalist.vram is None else finalist.vram.minimum_free_gib
    return SelectionCandidate(_round_medians(finalist), free, finalist.n_cpu_moe)


def _select_cuda(run: _ModeRun, ctx: int, screening: ScreeningResult) -> ModeCalibration:
    """Confirm the measured boundary and apply paired selection to valid finalists."""
    values = [screening.boundary]
    if screening.boundary < run.domain_maximum:
        values.append(screening.boundary + 1)
    run.finalist_values = tuple(values)
    confirmation = confirm_finalists(run, ctx)
    valid_pairs = [
        (index, finalist)
        for index, finalist in enumerate(confirmation.finalists)
        if finalist.outcome == "valid"
    ]
    if not valid_pairs:
        reasons = "; ".join(item.discard_reason or "unknown" for item in confirmation.finalists)
        raise CalibrationRunError(
            f"mode {run.mode.id}: no finalist passed confirmation ({reasons})"
        )
    candidates = tuple(_selection_candidate(item[1]) for item in valid_pairs)
    drift = confirmation.baseline_drift_gib
    selected, rule, winners = select_candidate_index(
        candidates,
        has_baseline_drift=bool(drift and drift > RELEASE_TOLERANCE_GIB),
    )
    original_winners = tuple(None if item is None else valid_pairs[item][0] for item in winners)
    return ModeCalibration(
        run.mode,
        ctx,
        run.options.target_ctx,
        tuple(run.probes),
        screening.did_degrade,
        confirmation.finalists,
        valid_pairs[selected][1],
        rule,
        original_winners,
        drift,
    )


def _cuda_mode(request: ModeRunRequest) -> tuple[ModeCalibration, set[str]]:
    """Screen, confirm in ABBA order, and select one CUDA mode at fixed context."""
    run = create_mode_run(request)
    ctx, screening = screen_context(run)
    if screening.is_budget_exhausted:
        raise CalibrationRunError(
            f"mode {run.mode.id}: screening exhausted the {MODE_PROBE_CAP}-probe cap before "
            "proving the boundary; the non-optimized baseline remains active"
        )
    return _select_cuda(run, ctx, screening), run.drivers


def _cpu_mode(request: ModeRunRequest) -> tuple[ModeCalibration, set[str]]:
    """Confirm the engine's CPU baseline twice with a benchmark in each round."""
    run = create_mode_run(request)
    ctx = run.options.target_ctx or CPU_BASELINE_CTX
    if ctx not in EXPERT_CONTEXT_TARGETS:
        allowed = ", ".join(str(value) for value in EXPERT_CONTEXT_TARGETS)
        raise CalibrationRunError(f"target context must be one of: {allowed}")
    run.finalist_values = (None,)
    confirmation = confirm_finalists(run, ctx)
    finalist = confirmation.finalists[0]
    if finalist.outcome != "valid":
        raise CalibrationRunError(
            f"mode {run.mode.id}: CPU baseline failed ({finalist.discard_reason})"
        )
    calibration = ModeCalibration(
        run.mode,
        ctx,
        run.options.target_ctx,
        (),
        False,
        (finalist,),
        finalist,
        SELECTION_CPU_BASELINE,
        (None, None),
        None,
    )
    return calibration, run.drivers


def run_mode(request: ModeRunRequest) -> tuple[ModeCalibration, set[str]]:
    """Predict the legal axis and run one mode without applying another host's winner."""
    if request.target.hardware.backend == "cpu":
        return _cpu_mode(request)
    try:
        block_count = read_block_count(request.target.model_path)
    except GgufError as error:
        raise CalibrationRunError(str(error)) from error
    from qwen_launcher._calibration_v4_seed import seed_probe_value

    seed = seed_probe_value(request.target, request.mode, block_count)
    predicted = ModeRunRequest(
        request.target,
        request.mode,
        request.runtime_root,
        block_count,
        seed,
        request.gpu_context_baseline,
        request.options,
    )
    return _cuda_mode(predicted)


def mode_request(
    target: CalibrationTarget,
    mode: Mode,
    run_context: tuple[Path, V4RunOptions, GpuContextBaseline | None],
) -> ModeRunRequest:
    """Group runner inputs before model metadata predicts the CUDA domain."""
    runtime_root, options, baseline = run_context
    return ModeRunRequest(target, mode, runtime_root, 0, None, baseline, options)
