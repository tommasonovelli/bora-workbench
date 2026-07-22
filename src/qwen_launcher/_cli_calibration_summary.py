"""Explain calibration/v4 selections and retained record paths."""

from __future__ import annotations

from statistics import median

from rich.console import Console

from qwen_launcher._calibration_v4_types import (
    SELECTION_CPU_BASELINE,
    SELECTION_DOMINANCE,
    SELECTION_DRIFT,
    SELECTION_FREE_VRAM,
    SELECTION_PRUDENT,
    SELECTION_SINGLE,
    ModeCalibration,
    V4Outcome,
)

_SELECTION_EXPLANATIONS = {
    SELECTION_CPU_BASELINE: "confirmed the fixed CPU baseline",
    SELECTION_SINGLE: "selected the only finalist that passed confirmation",
    SELECTION_DOMINANCE: "selected the finalist that won both paired rounds",
    SELECTION_FREE_VRAM: "resolved equivalent throughput by measured free VRAM",
    SELECTION_PRUDENT: "resolved equivalent throughput with the prudent boundary",
    SELECTION_DRIFT: "used the safe tie-break after measured VRAM baseline drift",
}


def _selected_rates(calibration: ModeCalibration) -> tuple[float, ...]:
    """Return every measured rate belonging to the selected finalist."""
    return tuple(
        rate
        for session in calibration.selected.sessions
        if session.benchmark is not None
        for rate in session.benchmark.measured_tok_s
    )


def _memory_summary(calibration: ModeCalibration) -> str:
    """Describe the selected finalist's measured minimum available memory."""
    selected = calibration.selected
    values = []
    if selected.ram is not None:
        values.append(f"RAM available min {selected.ram.minimum_available_gib:.2f} GiB")
    if selected.vram is not None:
        values.append(f"VRAM free min {selected.vram.minimum_free_gib:.2f} GiB")
    return ", ".join(values) if values else "memory evidence unavailable"


def _mode_summary(calibration: ModeCalibration) -> str:
    """Summarize the selected envelope, paired reason, and measured headroom."""
    value = calibration.selected.n_cpu_moe
    n_cpu_moe = "baseline" if value is None else str(value)
    rates = _selected_rates(calibration)
    speed = "n/a" if not rates else f"{median(rates):.3f} tok/s confirmed median"
    reason = _SELECTION_EXPLANATIONS.get(calibration.selection_rule, calibration.selection_rule)
    return (
        f"{calibration.mode.id}: ctx={calibration.ctx}, n_cpu_moe={n_cpu_moe}; {speed}; "
        f"{reason}; {_memory_summary(calibration)}; {len(calibration.probes)} screening probe(s)"
    )


def _show_context_hint(calibration: ModeCalibration, console: Console) -> None:
    """Expose D-050's approved 96K expert check only at the automatic 64K gap."""
    is_cuda = calibration.selected.vram is not None
    if calibration.target_ctx is not None or not is_cuda or calibration.ctx != 65536:
        return
    console.print(
        f"[yellow]{calibration.mode.id}: automatic v4 does not test 98304. "
        "To measure that gap without activation, run "
        f"`qwen-launcher calibrate --mode {calibration.mode.id} "
        "--target-ctx 98304 --no-activate`; feasibility is not implied.[/yellow]"
    )


def show_calibration_outcome(outcome: V4Outcome, console: Console) -> None:
    """Print record paths, selection reasons, and actionable context gaps."""
    console.print("[green]Local calibration completed.[/green]")
    for calibration in outcome.calibrations:
        console.print(_mode_summary(calibration))
        _show_context_hint(calibration, console)
    for path in outcome.active_paths:
        console.print(f"Active record: {path}")
    if not outcome.active_paths:
        for path in outcome.candidate_paths:
            if path.exists():
                console.print(f"Candidate record: {path}")
        console.print("Review candidate records, then activate with `calibrate --activate`.")
    console.print(f"Private run evidence: {outcome.evidence_path}")
    console.print("No private record or process log was uploaded.")
