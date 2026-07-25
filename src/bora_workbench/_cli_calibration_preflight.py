"""State exactly what one calibration run will do before the operator confirms it.

Everything printed here is derived from the detected hardware and the requested options, never from
a fixed script: an operator who reads it must be able to predict the contexts that will be searched,
the probe budget that bounds them, and what happens to the records at the end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from bora_workbench._calibration_record import records_directory
from bora_workbench._calibration_types import (
    BASELINE_CTX,
    CONTEXT_SCALE,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    TEXT_SEARCH_BUDGET,
    VRAM_RESERVE_GIB,
    VSTUDIO_SEARCH_BUDGET,
)
from bora_workbench._cli_theme import print_heading
from bora_workbench.calibration import CalibrationTarget

if TYPE_CHECKING:
    from bora_workbench._cli_calibration import CalibrationCliInput


def _scale_text(target: CalibrationTarget, target_ctx: int | None) -> str:
    """Describe exactly which contexts this run will search on the detected backend."""
    if target_ctx is not None:
        return str(target_ctx)
    if target.hardware.backend == "cpu":
        return f"{BASELINE_CTX} (CPU confirms one baseline; it has no offload axis)"
    return " -> ".join(str(value) for value in CONTEXT_SCALE)


def _budget_text(target: CalibrationTarget) -> str:
    """State the probe budget of each group this run will actually create."""
    budgets = []
    if any(not mode.services.vision for mode in target.modes):
        budgets.append(f"{TEXT_SEARCH_BUDGET} shared text probes")
    if any(mode.services.vision for mode in target.modes):
        budgets.append(f"{VSTUDIO_SEARCH_BUDGET} vision probes")
    return "at most " + " and ".join(budgets)


def _print_hardware(target: CalibrationTarget, console: Console) -> None:
    """Print the detected memory the reserves will be measured against."""
    console.print(
        f"RAM: {target.hardware.ram_total_gib:.3f} GiB total, "
        f"{target.hardware.ram_available_gib:.3f} GiB available"
    )
    if target.hardware.vram_total_gib is not None:
        console.print(
            f"VRAM: {target.hardware.vram_total_gib:.3f} GiB total, "
            f"{target.hardware.vram_free_gib:.3f} GiB free"
        )


def show_preflight(
    target: CalibrationTarget, options: CalibrationCliInput, console: Console
) -> None:
    """Show the objective, reserves, workload, and record lifecycle before confirmation."""
    print_heading(console, "Calibration preflight")
    console.print("Local three-envelope search; no technical input is needed and nothing is sent.")
    console.print(f"Modes: {', '.join(mode.id for mode in target.modes)}")
    console.print(f"Backend: {target.hardware.backend}; engine: {target.lock['release']}")
    _print_hardware(target, console)
    console.print(f"Contexts: {_scale_text(target, options.target_ctx)}")
    console.print(
        f"Constants: VRAM reserve {VRAM_RESERVE_GIB} GiB, RAM reserve {RAM_RESERVE_GIB} GiB, "
        f"release tolerance {RELEASE_TOLERANCE_GIB} GiB, {_budget_text(target)}."
    )
    lifecycle = "candidate only" if options.no_activate else "candidate then atomic activation"
    console.print(f"Records: {records_directory()} ({lifecycle}); three envelopes per mode.")
    console.print("Latest-run logs and evidence are retained in one rotated private slot.")
    console.print(
        "Duration: potentially hours; trial crashes are isolated and memory is monitored."
    )
