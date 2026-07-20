"""Present calibration/v3, candidate activation, progress, and plain-language outcomes."""

from __future__ import annotations

from statistics import median

import typer
from rich.console import Console

from qwen_launcher._calibration_record import RecordError, promote_candidate, records_directory
from qwen_launcher._calibration_v3_runner import run_calibration_v3
from qwen_launcher._calibration_v3_types import (
    CONFIRM_ROUNDS,
    CONTEXT_SCALE,
    EXPERT_CONTEXT_TARGETS,
    MODE_PROBE_CAP,
    OBJECTIVE,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    ModeCalibration,
    ProgressEvent,
    V3Outcome,
    V3RunOptions,
)
from qwen_launcher._cli_calibration import (
    CalibrationCancelled,
    CalibrationCliInput,
    CalibrationCliOutput,
)
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
    console.print("[bold]Calibration preflight (calibration/v3)[/bold]")
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
    lifecycle = "candidate only" if options.no_activate else "candidate then atomic activation"
    console.print(f"Records: {records_directory()} ({lifecycle}).")
    console.print("Latest-run logs and evidence are retained in one rotated private slot.")
    console.print(
        "Duration: potentially hours; trial crashes are isolated and memory is monitored."
    )


def _progress(event: ProgressEvent, console: Console) -> None:
    """Show phase progress with a learned estimate after two local process durations."""
    message = f"{event.mode_id} {event.phase}: {event.completed}/{event.total}"
    if event.estimated_remaining_seconds is not None:
        minutes = event.estimated_remaining_seconds / 60
        message += f"; estimated remaining {minutes:.1f} min"
    console.print(message)


def _selected_rates(calibration: ModeCalibration) -> list[float]:
    """Flatten both selected paired benchmark sessions for the final plain-language summary."""
    return [
        value
        for session in calibration.selected.sessions
        if session.benchmark is not None
        for value in session.benchmark.measured_tok_s
    ]


def _mode_summary(calibration: ModeCalibration) -> str:
    """Summarize one selected envelope and why it won."""
    selected = calibration.selected
    envelope = f"ctx={calibration.ctx}"
    if selected.n_cpu_moe is not None:
        envelope += f", n_cpu_moe={selected.n_cpu_moe}"
    rate = median(_selected_rates(calibration))
    return (
        f"{calibration.mode.id}: {envelope}; confirmed median {rate:.2f} tok/s; "
        f"rule {calibration.selection_rule}; probes {len(calibration.probes)}"
    )


def _show_outcome(outcome: V3Outcome, console: Console) -> None:
    """Print selections, candidate/active paths, retained evidence, and privacy boundary."""
    console.print("[green]Local calibration completed.[/green]")
    for calibration in outcome.calibrations:
        console.print(_mode_summary(calibration))
    for path in outcome.candidate_paths:
        if path.exists():
            console.print(f"Candidate: {path}")
    for path in outcome.active_paths:
        console.print(f"Active record: {path}")
    if not outcome.active_paths:
        console.print(
            "[yellow]Candidates were not activated; launches still use prior records.[/yellow]"
        )
    console.print(f"Latest private evidence: {outcome.evidence_path}")
    console.print("Sharing remains a separate manual, redacted contribution step.")


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
        console.print(f"[green]Activated calibration candidate:[/green] {path}")


def run_calibrate_v3(options: CalibrationCliInput, output: CalibrationCliOutput) -> None:
    """Activate pending evidence or run paired adaptive search for selected modes."""
    if options.target_ctx is not None and options.target_ctx not in EXPERT_CONTEXT_TARGETS:
        allowed = ", ".join(str(value) for value in EXPERT_CONTEXT_TARGETS)
        raise CalibrationError(f"target context must be one of: {allowed}")
    if options.activate:
        _activate_candidates(options, output.stdout)
        return
    target = prepare_target(options.mode)
    _show_preflight(target, options, output.stdout)
    if not typer.confirm("Start local calibration?", default=False):
        raise CalibrationCancelled("calibration cancelled before process start")
    run_options = V3RunOptions(
        options.target_ctx,
        not options.no_activate,
        lambda event: _progress(event, output.stdout),
    )
    _show_outcome(run_calibration_v3(target, run_options), output.stdout)
