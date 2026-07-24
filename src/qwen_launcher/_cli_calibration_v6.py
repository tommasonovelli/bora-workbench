"""Present the opt-in calibration/v6-lite protocol, preflight, and plain-language outcome.

v6-lite is experimental and opt-in; calibration/v5 stays the default. Promotion of v6 to the default
protocol is a human decision recorded in IMPLEMENTATION_SPEC.md, never claimed here (D-063).
"""

from __future__ import annotations

from typing import cast

import typer
from rich.console import Console

from qwen_launcher._calibration_record import RecordError, promote_candidate, records_directory
from qwen_launcher._calibration_v6_run import run_calibration_v6
from qwen_launcher._calibration_v6_run_types import V6RunOptions
from qwen_launcher._calibration_v6_types import (
    CONTEXT_REFINEMENT,
    CONTEXT_SCALE_V6,
    DEFAULT_PREFERENCE,
    PREFERENCES,
    Preference,
)
from qwen_launcher._cli_calibration import (
    CalibrationCancelled,
    CalibrationCliInput,
    CalibrationCliOutput,
)
from qwen_launcher._cli_calibration_v5 import _selected_mode_ids
from qwen_launcher._cli_theme import print_heading, print_success
from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationRunError,
    CalibrationTarget,
    prepare_target,
)

_APPROVED_CTX = set(CONTEXT_SCALE_V6) | set(CONTEXT_REFINEMENT)


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
        raise CalibrationError(f"v6 target context must be one of: {allowed}")


def _activate(mode_value: str, console: Console) -> None:
    """Promote already measured v6 candidates without rerunning expensive trials."""
    for mode_id in _selected_mode_ids(mode_value):
        try:
            path = promote_candidate(mode_id)
        except RecordError as error:
            raise CalibrationRunError(str(error)) from error
        print_success(console, "Activated calibration candidate", str(path))


def _preflight(target: CalibrationTarget, preference: Preference, console: Console) -> None:
    """Show the experimental v6-lite objective, reserves, and lifecycle before confirmation."""
    print_heading(console, "Calibration preflight (calibration/v6-lite, experimental)")
    console.print("Opt-in shared search over 131072 -> 65536 -> 32768; v5 remains the default.")
    console.print(f"Modes: {', '.join(mode.id for mode in target.modes)}; preference: {preference}")
    console.print("Reserves: 0.5 GiB VRAM, 2.0 GiB RAM, 0.125 GiB release tolerance.")
    console.print(f"Records: {records_directory()} (three envelopes fast/balanced/max_context).")
    console.print("Promotion of v6 to the default protocol stays a human decision.")
    console.print("Duration: about 40-60 fresh processes for --mode all; trials are isolated.")


def run_calibrate_v6(options: CalibrationCliInput, output: CalibrationCliOutput) -> None:
    """Activate pending v6 candidates or run the experimental v6-lite search for selected modes."""
    _validate(options)
    preference = _preference(options.preference)
    if options.activate:
        _activate(options.mode, output.stdout)
        return
    target = prepare_target(options.mode)
    _preflight(target, preference, output.stdout)
    if not typer.confirm("Start experimental v6-lite calibration?", default=False):
        raise CalibrationCancelled("calibration cancelled before process start")
    run_options = V6RunOptions(
        preference=preference,
        target_ctx=options.target_ctx,
        is_activate=not options.no_activate,
    )
    result = run_calibration_v6(target, run_options)
    for path in result.record_paths:
        print_success(output.stdout, "Wrote calibration/v6-lite record", str(path))
