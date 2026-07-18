"""Present and run the zero-input adaptive calibration/v2 protocol from the CLI.

The operator only picks the modes; domain, ordering, and selection are measured locally (D-038).
Errors and cancellation propagate to the shared calibrate command mapping in one place.
"""

from __future__ import annotations

import typer
from rich.console import Console

from qwen_launcher._calibration_record import records_directory
from qwen_launcher._calibration_v2_runner import run_calibration_v2
from qwen_launcher._calibration_v2_types import (
    CONTEXT_SCALE,
    MODE_PROBE_CAP,
    RELEASE_TOLERANCE_GIB,
    STABLE_START_RUNS,
    VRAM_RESERVE_GIB,
    ModeCalibration,
    V2Outcome,
)
from qwen_launcher._cli_calibration import CalibrationCancelled, CalibrationCliOutput
from qwen_launcher.calibration import CalibrationTarget, prepare_target


def _show_preflight(target: CalibrationTarget, console: Console) -> None:
    """Show the exact adaptive workload, declared constants, and risk before confirmation."""
    console.print("[bold]Calibration preflight (calibration/v2)[/bold]")
    console.print("Adaptive local search with zero mandatory inputs; nothing is uploaded.")
    console.print(f"Modes: {', '.join(mode.id for mode in target.modes)}")
    console.print(f"Backend: {target.hardware.backend}; engine: {target.lock['release']}")
    console.print(
        f"RAM: {target.hardware.ram_total_gib:.3f} GiB total, "
        f"{target.hardware.ram_available_gib:.3f} GiB available"
    )
    if target.hardware.vram_total_gib is not None:
        console.print(
            f"VRAM baseline: {target.hardware.vram_total_gib:.3f} GiB total, "
            f"{target.hardware.vram_free_gib:.3f} GiB free"
        )
    scale = " -> ".join(str(ctx) for ctx in CONTEXT_SCALE)
    console.print(
        f"Design constants (D-039): VRAM reserve {VRAM_RESERVE_GIB} GiB, release/drift "
        f"tolerance {RELEASE_TOLERANCE_GIB} GiB, {STABLE_START_RUNS} stable starts per finalist, "
        f"at most {MODE_PROBE_CAP} screening probes per mode, context scale {scale}."
    )
    console.print(f"Destination: {records_directory()}")
    console.print("The private local record is reused immediately by the next launches.")
    console.print(
        "Duration: potentially hours; a probe process may crash or be discarded, and RAM and "
        "VRAM are monitored during every trial. Production state is isolated."
    )


def _mode_summary(calibration: ModeCalibration) -> str:
    """Summarize one mode's selected envelope and its deterministic selection rule."""
    selected = calibration.selected
    assert selected.benchmark is not None
    envelope = f"ctx={calibration.ctx}"
    if selected.n_cpu_moe is not None:
        envelope += f", n_cpu_moe={selected.n_cpu_moe}"
    return (
        f"{calibration.mode.id}: {envelope}; median {selected.benchmark.tok_s.median:.2f} tok/s; "
        f"rule {calibration.selection_rule}; probes {len(calibration.probes)}"
    )


def _show_outcome(outcome: V2Outcome, console: Console) -> None:
    """Print every selected envelope and the private record path it produced."""
    console.print("[green]Local calibration completed.[/green]")
    for calibration, path in zip(outcome.calibrations, outcome.record_paths, strict=True):
        console.print(_mode_summary(calibration))
        console.print(f"Record: {path}")
    console.print("Records are private and local; sharing evidence remains a separate manual step.")


def run_calibrate_v2(mode_value: str, output: CalibrationCliOutput) -> None:
    """Prepare, confirm, and run the adaptive search for the selected packaged modes."""
    target = prepare_target(mode_value)
    _show_preflight(target, output.stdout)
    if not typer.confirm("Start local calibration?", default=False):
        raise CalibrationCancelled("calibration cancelled before process start")
    outcome = run_calibration_v2(target)
    _show_outcome(outcome, output.stdout)
