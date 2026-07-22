"""Coordinate calibration/v4 modes, evidence retention, and candidate-record activation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from qwen_launcher._calibration_evidence import preserve_evidence
from qwen_launcher._calibration_gpu_contexts import (
    GpuContextBaseline,
    capture_gpu_context_baseline,
)
from qwen_launcher._calibration_ram import RamError
from qwen_launcher._calibration_record import (
    RecordError,
    build_record,
    candidate_record_path,
    promote_candidate,
    write_record,
)
from qwen_launcher._calibration_v4_mode import mode_request, run_mode
from qwen_launcher._calibration_v4_types import ModeCalibration, V4Outcome, V4RunOptions
from qwen_launcher._calibration_vram import VramEnvironmentError
from qwen_launcher.calibration import CalibrationRunError, CalibrationTarget
from qwen_launcher.paths import data_dir


@dataclass(frozen=True, slots=True)
class _V4RunContext:
    """Group immutable options, runtime path, and the one run-scoped GPU baseline."""

    runtime_root: Path
    options: V4RunOptions
    gpu_context_baseline: GpuContextBaseline | None


def _preserve_on_failure(root: Path, runtime_root: Path, run_id: str) -> None:
    """Retain the failed run's logs as the latest evidence instead of deleting diagnostics."""
    if runtime_root.exists():
        preserve_evidence(root, runtime_root, run_id)


def _run_modes(target: CalibrationTarget, context: _V4RunContext) -> tuple[ModeCalibration, ...]:
    """Run selected modes against one immutable context population and driver identity."""
    calibrations: list[ModeCalibration] = []
    drivers: set[str] = set()
    for mode in target.modes:
        run_context = (context.runtime_root, context.options, context.gpu_context_baseline)
        request = mode_request(target, mode, run_context)
        calibration, mode_drivers = run_mode(request)
        calibrations.append(calibration)
        drivers |= mode_drivers
        if len(drivers) > 1:
            raise CalibrationRunError("GPU driver version changed during calibration")
    return tuple(calibrations)


def _write_candidates(
    target: CalibrationTarget,
    calibrations: tuple[ModeCalibration, ...],
    record_context: tuple[Path, str],
) -> tuple[Path, ...]:
    """Write every validated result as a candidate before any active record changes."""
    records_root, run_id = record_context
    paths = []
    for calibration in calibrations:
        document = build_record(target, calibration, run_id)
        path = candidate_record_path(calibration.mode.id, records_root)
        paths.append(write_record(document, path))
    return tuple(paths)


def _activate(
    calibrations: tuple[ModeCalibration, ...], records_root: Path, is_activate: bool
) -> tuple[Path, ...]:
    """Promote candidates by default while preserving an expert no-activate Gate path."""
    if not is_activate:
        return ()
    return tuple(promote_candidate(item.mode.id, records_root) for item in calibrations)


def _capture_context_baseline(target: CalibrationTarget) -> GpuContextBaseline | None:
    """Fail fast before process work when CUDA context identities cannot be trusted."""
    if target.hardware.backend == "cpu":
        return None
    if target.hardware.gpu_index is None:
        raise CalibrationRunError("CUDA calibration requires a selected GPU index")
    try:
        return capture_gpu_context_baseline(target.hardware.gpu_index)
    except VramEnvironmentError as error:
        raise CalibrationRunError(f"calibration run invalidated: {error}") from error


def run_calibration_v4(
    target: CalibrationTarget,
    options: V4RunOptions | None = None,
    destination_root: Path | None = None,
) -> V4Outcome:
    """Search, retain evidence, write candidates, and optionally activate each selected mode."""
    selected = options or V4RunOptions()
    root = data_dir() / "calibration" if destination_root is None else destination_root
    context_baseline = _capture_context_baseline(target)
    run_id = uuid4().hex
    runtime_root = root / f".runtime-{run_id}"
    runtime_root.mkdir(parents=True, exist_ok=False)
    context = _V4RunContext(runtime_root, selected, context_baseline)
    try:
        calibrations = _run_modes(target, context)
    except (VramEnvironmentError, RamError) as error:
        _preserve_on_failure(root, runtime_root, run_id)
        raise CalibrationRunError(f"calibration run invalidated: {error}") from error
    except BaseException:
        _preserve_on_failure(root, runtime_root, run_id)
        raise
    try:
        evidence_path = preserve_evidence(root, runtime_root, run_id)
        records_root = root / "records"
        candidates = _write_candidates(target, calibrations, (records_root, run_id))
        active = _activate(calibrations, records_root, selected.is_activate)
        return V4Outcome(calibrations, candidates, active, evidence_path)
    except (OSError, RecordError, ValueError) as error:
        raise CalibrationRunError(str(error)) from error
