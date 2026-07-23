"""Present calibration/v5, candidate activation, progress, and plain-language outcomes."""

from __future__ import annotations

import typer
from rich.console import Console

from qwen_launcher._calibration_record import RecordError, promote_candidate, records_directory
from qwen_launcher._calibration_v5_runner import run_calibration_v5
from qwen_launcher._calibration_v5_types import (
    APPROVED_CONTEXT_TARGETS,
    CONFIRM_ROUNDS,
    CONTEXT_SCALE,
    MODE_PROBE_CAP,
    OBJECTIVE,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    V5RunOptions,
)
from qwen_launcher._cli_calibration import (
    CalibrationCancelled,
    CalibrationCliInput,
    CalibrationCliOutput,
)
from qwen_launcher._cli_calibration_progress import CalibrationProgress
from qwen_launcher._cli_calibration_summary import show_calibration_outcome
from qwen_launcher._cli_theme import print_heading, print_success
from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationRunError,
    CalibrationTarget,
    prepare_target,
)
from qwen_launcher.profiles import load_catalog


def _show_preflight(
    target: CalibrationTarget, options: CalibrationCliInput, console: Console
) -> None:
    """Show objective, workload, constants, lifecycle, and risk before process confirmation."""
    print_heading(console, "Calibration preflight (calibration/v5)")
    console.print("Paired adaptive local search with zero mandatory technical inputs; no upload.")
    console.print(f"Objective: {OBJECTIVE}")
    console.print(f"Modes: {', '.join(mode.id for mode in target.modes)}")
    console.print(f"Backend: {target.hardware.backend}; engine: {target.lock['release']}")
    console.print(
        f"RAM: {target.hardware.ram_total_gib:.3f} GiB total, "
        f"{target.hardware.ram_available_gib:.3f} GiB available"
    )
    if target.hardware.vram_total_gib is not None:
        console.print(
            f"VRAM: {target.hardware.vram_total_gib:.3f} GiB total, "
            f"{target.hardware.vram_free_gib:.3f} GiB free"
        )
    scale = str(options.target_ctx) if options.target_ctx else " -> ".join(map(str, CONTEXT_SCALE))
    console.print(
        f"Constants: VRAM reserve {VRAM_RESERVE_GIB} GiB, RAM reserve {RAM_RESERVE_GIB} GiB, "
        f"release tolerance {RELEASE_TOLERANCE_GIB} GiB, {CONFIRM_ROUNDS} ABBA rounds, "
        f"at most {MODE_PROBE_CAP} probes, context {scale}."
    )
    console.print(
        f"Trial ports: use configured {target.config.llama_port} when free; "
        "otherwise use a temporary loopback port."
    )
    lifecycle = "candidate only" if options.no_activate else "candidate then atomic activation"
    console.print(f"Records: {records_directory()} ({lifecycle}).")
    console.print("Latest-run logs and evidence are retained in one rotated private slot.")
    console.print(
        "Duration: potentially hours; trial crashes are isolated and memory is monitored."
    )
    console.print(
        "Progress: live on terminals and line-oriented when redirected; screening shows a "
        "probe-cap count and a duration projection to that cap."
    )


def _selected_mode_ids(value: str) -> tuple[str, ...]:
    """Resolve one mode or all packaged modes without hardware or process side effects."""
    catalog = load_catalog()
    if value == "all":
        return tuple(mode.id for mode in catalog.modes)
    if catalog.mode(value) is None:
        valid = ", ".join([mode.id for mode in catalog.modes] + ["all"])
        raise CalibrationError(f"unknown calibration mode {value!r}; valid values: {valid}")
    return (value,)


def _activate_candidates(options: CalibrationCliInput, console: Console) -> None:
    """Promote already validated candidates without rerunning expensive trials."""
    for mode_id in _selected_mode_ids(options.mode):
        try:
            path = promote_candidate(mode_id)
        except RecordError as error:
            raise CalibrationRunError(str(error)) from error
        print_success(console, "Activated calibration candidate", str(path))


def run_calibrate_v5(options: CalibrationCliInput, output: CalibrationCliOutput) -> None:
    """Activate pending evidence or run paired adaptive search for selected modes."""
    if options.target_ctx is not None and options.target_ctx not in APPROVED_CONTEXT_TARGETS:
        allowed = ", ".join(str(value) for value in APPROVED_CONTEXT_TARGETS)
        raise CalibrationError(f"target context must be one of: {allowed}")
    if options.activate:
        _activate_candidates(options, output.stdout)
        return
    target = prepare_target(options.mode)
    _show_preflight(target, options, output.stdout)
    if not typer.confirm("Start local calibration?", default=False):
        raise CalibrationCancelled("calibration cancelled before process start")
    with CalibrationProgress(output.stdout) as progress:
        run_options = V5RunOptions(
            target_ctx=options.target_ctx,
            is_activate=not options.no_activate,
            progress=progress,
        )
        outcome = run_calibration_v5(target, run_options)
    show_calibration_outcome(outcome, output.stdout)
