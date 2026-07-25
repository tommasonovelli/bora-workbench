"""Present the calibration command and map its failures onto the contractual exit codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import typer
from rich.console import Console

from bora_workbench._calibration_outcomes import UnclassifiableTrialError
from bora_workbench._calibration_record import RecordError, promote_candidate
from bora_workbench._calibration_run import run_calibration
from bora_workbench._calibration_run_types import RunOptions, RunResult
from bora_workbench._calibration_types import (
    CONTEXT_SCALE,
    DEFAULT_PREFERENCE,
    PREFERENCES,
    Preference,
    SearchError,
)
from bora_workbench._cli_calibration_preflight import show_preflight
from bora_workbench._cli_calibration_progress import CalibrationProgress
from bora_workbench._cli_calibration_summary import show_outcome
from bora_workbench._cli_theme import print_error, print_success, print_warning
from bora_workbench.calibration import (
    CalibrationError,
    CalibrationRunError,
    CalibrationTarget,
    prepare_target,
    selected_mode_ids,
)
from bora_workbench.config import ConfigError
from bora_workbench.engine import EngineError
from bora_workbench.hardware import HardwareError
from bora_workbench.process import ProcessError
from bora_workbench.profiles import ContentError, PlanError

_APPROVED_CTX = set(CONTEXT_SCALE)


class CalibrationCancelled(RuntimeError):
    """Mark an operator cancellation that maps to the contractual exit code 130."""


@dataclass(frozen=True, slots=True)
class CalibrationCliInput:
    """Group the raw CLI values of one calibration invocation."""

    mode: str
    no_activate: bool = False
    activate: bool = False
    target_ctx: int | None = None
    preference: str | None = None


@dataclass(frozen=True, slots=True)
class CalibrationCliOutput:
    """Group CLI streams without passing broad presentation dependencies into core code."""

    stdout: Console
    stderr: Console


def _preference(value: str | None) -> Preference:
    """Normalize and validate the requested launch envelope preference."""
    normalized = (value or DEFAULT_PREFERENCE).replace("-", "_")
    if normalized not in PREFERENCES:
        allowed = ", ".join(name.replace("_", "-") for name in PREFERENCES)
        raise CalibrationError(f"unknown preference {value!r}; use one of: {allowed}")
    return cast(Preference, normalized)


def _validate(options: CalibrationCliInput) -> None:
    """Reject conflicting activation and unapproved target contexts before any process starts."""
    if options.no_activate and options.activate:
        raise CalibrationError("--no-activate and --activate are mutually exclusive")
    if options.activate and options.target_ctx is not None:
        raise CalibrationError("--target-ctx cannot be used while activating a pending candidate")
    if options.target_ctx is not None and options.target_ctx not in _APPROVED_CTX:
        allowed = ", ".join(str(value) for value in sorted(_APPROVED_CTX, reverse=True))
        raise CalibrationError(f"--target-ctx must be one of: {allowed}")


def _activate(mode_value: str, console: Console) -> None:
    """Promote already measured candidates without rerunning expensive trials."""
    for mode_id in selected_mode_ids(mode_value):
        try:
            path = promote_candidate(mode_id)
        except RecordError as error:
            raise CalibrationRunError(str(error)) from error
        print_success(console, "Activated calibration candidate", str(path))


def _measure(target: CalibrationTarget, run_options: RunOptions) -> RunResult:
    """Map search and classification failures onto the contractual operational exit code.

    Both are operational: the input was valid and processes already ran (spec 5.11).
    """
    try:
        return run_calibration(target, run_options)
    except (UnclassifiableTrialError, SearchError) as error:
        raise CalibrationRunError(str(error)) from error


def _run(options: CalibrationCliInput, output: CalibrationCliOutput) -> None:
    """Activate pending candidates or measure the three envelopes of the selected modes."""
    _validate(options)
    preference = _preference(options.preference)
    if options.activate:
        _activate(options.mode, output.stdout)
        return
    target = prepare_target(options.mode)
    show_preflight(target, options, output.stdout)
    if not typer.confirm("Start calibration?", default=False):
        raise CalibrationCancelled("calibration cancelled before process start")
    with CalibrationProgress(output.stdout) as progress:
        run_options = RunOptions(
            preference=preference,
            target_ctx=options.target_ctx,
            is_activate=not options.no_activate,
            progress=progress,
        )
        result = _measure(target, run_options)
    show_outcome(result, preference, output.stdout)
    if result.failures:
        # The records that were written stay valid and activated; the run is still incomplete, so
        # the exit code must not claim success for modes that produced nothing (spec 5.11).
        raise CalibrationRunError("calibration did not complete for: " + "; ".join(result.failures))


def run_calibrate(options: CalibrationCliInput, output: CalibrationCliOutput) -> None:
    """Run calibration with contractual error and cancellation mapping (spec 5.11)."""
    try:
        _run(options, output)
    except (KeyboardInterrupt, typer.Abort, CalibrationCancelled) as error:
        print_warning(output.stderr, f"Calibration cancelled: {error}")
        raise typer.Exit(code=130) from error
    except CalibrationRunError as error:
        print_error(output.stderr, "Calibration error", str(error))
        raise typer.Exit(code=1) from error
    except (ConfigError, CalibrationError, ValueError) as error:
        print_error(output.stderr, "Calibration input error", str(error))
        raise typer.Exit(code=2) from error
    except (ContentError, EngineError, HardwareError, PlanError, ProcessError, OSError) as error:
        print_error(output.stderr, "Calibration error", str(error))
        raise typer.Exit(code=1) from error
