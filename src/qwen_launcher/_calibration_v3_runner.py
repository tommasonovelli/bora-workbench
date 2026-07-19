"""Coordinate calibration/v3 modes, evidence retention, and candidate-record activation."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from qwen_launcher._calibration_evidence import preserve_evidence
from qwen_launcher._calibration_ram import RamError
from qwen_launcher._calibration_record import (
    RecordError,
    build_record,
    candidate_record_path,
    promote_candidate,
    write_record,
)
from qwen_launcher._calibration_v3_mode import mode_request, run_mode
from qwen_launcher._calibration_v3_types import ModeCalibration, V3Outcome, V3RunOptions
from qwen_launcher._calibration_vram import VramEnvironmentError
from qwen_launcher.calibration import CalibrationRunError, CalibrationTarget
from qwen_launcher.paths import data_dir


def _preserve_on_failure(root: Path, runtime_root: Path, run_id: str) -> None:
    """Retain the failed run's logs as the latest evidence instead of deleting diagnostics."""
    if runtime_root.exists():
        preserve_evidence(root, runtime_root, run_id)


def _run_modes(
    target: CalibrationTarget, runtime_root: Path, options: V3RunOptions
) -> tuple[ModeCalibration, ...]:
    """Run selected modes and invalidate the whole run if driver identity changes."""
    calibrations: list[ModeCalibration] = []
    drivers: set[str] = set()
    for mode in target.modes:
        request = mode_request(target, mode, (runtime_root, options))
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


def run_calibration_v3(
    target: CalibrationTarget,
    options: V3RunOptions | None = None,
    destination_root: Path | None = None,
) -> V3Outcome:
    """Search, retain evidence, write candidates, and optionally activate each selected mode."""
    selected = options or V3RunOptions()
    root = data_dir() / "calibration" if destination_root is None else destination_root
    run_id = uuid4().hex
    runtime_root = root / f".runtime-{run_id}"
    runtime_root.mkdir(parents=True, exist_ok=False)
    try:
        calibrations = _run_modes(target, runtime_root, selected)
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
        return V3Outcome(calibrations, candidates, active, evidence_path)
    except (OSError, RecordError, ValueError) as error:
        raise CalibrationRunError(str(error)) from error
