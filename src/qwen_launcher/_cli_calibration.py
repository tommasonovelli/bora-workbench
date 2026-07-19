"""Collect explicit Step 5A inputs and present calibration draft evidence."""

from __future__ import annotations

from dataclasses import dataclass

import typer
from rich.console import Console

from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationOutcome,
    CalibrationRunError,
    CalibrationSettings,
    CalibrationTarget,
    parse_candidate,
    prepare_target,
    run_calibration,
)
from qwen_launcher.config import ConfigError
from qwen_launcher.engine import EngineError
from qwen_launcher.hardware import HardwareError
from qwen_launcher.paths import data_dir
from qwen_launcher.process import ProcessError
from qwen_launcher.profiles import ContentError, PlanError


class CalibrationCancelled(RuntimeError):
    """Mark an operator cancellation that maps to the contractual exit code 130."""


@dataclass(frozen=True, slots=True)
class CalibrationCliInput:
    """Group raw CLI values that may still require interactive completion."""

    mode: str
    candidate_values: tuple[str, ...]
    settings_value: str | None
    protocol: str = "v3"
    no_activate: bool = False
    activate: bool = False
    target_ctx: int | None = None


@dataclass(frozen=True, slots=True)
class CalibrationCliOutput:
    """Group CLI streams without passing broad presentation dependencies into core code."""

    stdout: Console
    stderr: Console


def _prompt_candidates(target: CalibrationTarget) -> tuple[str, ...]:
    """Collect at least one candidate and stop only when the operator explicitly declines more."""
    syntax = "ID:CTX:N_CPU_MOE" if target.hardware.backend == "cuda" else "ID:CTX"
    values: list[str] = []
    while True:
        values.append(typer.prompt(f"Candidate ({syntax})"))
        if not typer.confirm("Add another candidate?", default=False):
            return tuple(values)


def _explicit_settings(
    value: str, target: CalibrationTarget
) -> tuple[int, float | None, float | None]:
    """Parse explicit CUDA reserve and release tolerance without hidden defaults."""
    fields = value.split(":")
    expected = 3 if target.hardware.backend == "cuda" else 1
    if len(fields) != expected:
        syntax = "RUNS:MIN_FREE_VRAM_GIB:RELEASE_TOLERANCE_GIB" if expected == 3 else "RUNS"
        raise CalibrationError(f"--settings must use {syntax} syntax")
    try:
        if expected == 1:
            return int(fields[0]), None, None
        return int(fields[0]), float(fields[1]), float(fields[2])
    except ValueError as error:
        raise CalibrationError("--settings values must be numeric") from error


def _settings(target: CalibrationTarget, options: CalibrationCliInput) -> CalibrationSettings:
    """Resolve missing policy-free values interactively without assigning author defaults."""
    values = options.candidate_values or _prompt_candidates(target)
    candidates = tuple(parse_candidate(value, target.hardware.backend) for value in values)
    if options.settings_value is not None:
        starts, reserve, tolerance = _explicit_settings(options.settings_value, target)
    else:
        starts = typer.prompt("Required fresh stable starts per candidate", type=int)
        reserve = None
        tolerance = None
        if target.hardware.backend == "cuda":
            reserve = typer.prompt("Minimum free VRAM reserve in GiB", type=float)
            tolerance = typer.prompt("Post-stop VRAM release tolerance in GiB", type=float)
    return CalibrationSettings(candidates, starts, reserve, tolerance)


def _show_preflight(
    target: CalibrationTarget, settings: CalibrationSettings, console: Console
) -> None:
    """Show exact workload, risk, evidence location, and detected baseline before confirmation."""
    console.print("[bold]Calibration preflight[/bold]")
    console.print(
        "[yellow]calibration/v1 is gate-only and cannot create a portable profile.[/yellow]"
    )
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
    console.print("Candidates: " + ", ".join(candidate.id for candidate in settings.candidates))
    if settings.vram_release_tolerance_gib is not None:
        console.print(
            f"Post-stop VRAM release: 10 s window, "
            f"{settings.vram_release_tolerance_gib:.3f} GiB tolerance"
        )
    starts = len(target.modes) * len(settings.candidates) * settings.stable_start_runs
    console.print(
        f"Workload: {starts} fresh server start(s); each final start runs 1 warm-up + 5 measures."
    )
    console.print(
        "Duration: potentially hours; exact duration depends on measured hardware performance."
    )
    console.print(f"Destination: {data_dir() / 'calibrations'}")
    console.print("Disk: redacted process logs and JSON evidence are retained in the destination.")
    console.print("Risk: a trial process may crash or be discarded; production state is isolated.")


def _show_outcome(outcome: CalibrationOutcome, console: Console) -> None:
    """Print candidate outcomes, shareable files, and the manual review boundary."""
    path = outcome.bundle_path
    console.print(f"[green]Draft bundle created:[/green] {path}")
    console.print("Proposed selections are not accepted profiles and no data was uploaded.")
    for mode_id, candidate_id in outcome.proposed_selections:
        if candidate_id is None:
            message = f"{mode_id}: no valid candidate; bundle contains discards only."
            console.print(f"[yellow]{message}[/yellow]")
        else:
            console.print(f"{mode_id}: proposed candidate {candidate_id}")
    files = sorted(file for file in path.rglob("*") if file.is_file())
    for file in files:
        relative = file.relative_to(path).as_posix()
        console.print(f"\n[bold]Exact shareable preview: {relative}[/bold]")
        console.print(file.read_text(encoding="utf-8", errors="replace"), markup=False)
    console.print("Review every file above; privacy_reviewed remains false until human review.")


def _dispatch(options: CalibrationCliInput, output: CalibrationCliOutput) -> bool:
    """Route to calibration/v3 unless the operator explicitly selects the v1 laboratory."""
    has_v3_options = options.no_activate or options.activate or options.target_ctx is not None
    if options.protocol == "v1":
        if has_v3_options:
            raise CalibrationError("activation and target context options require calibration/v3")
        return False
    if options.protocol != "v3":
        raise CalibrationError(f"unknown calibration protocol {options.protocol!r}; use v3 or v1")
    if options.no_activate and options.activate:
        raise CalibrationError("--no-activate and --activate are mutually exclusive")
    if options.activate and options.target_ctx is not None:
        raise CalibrationError("--target-ctx cannot be used while activating a pending candidate")
    if options.candidate_values or options.settings_value is not None:
        raise CalibrationError("explicit candidates and settings require --protocol v1")
    from qwen_launcher._cli_calibration_v3 import run_calibrate_v3

    run_calibrate_v3(options, output)
    return True


def run_calibrate(options: CalibrationCliInput, output: CalibrationCliOutput) -> None:
    """Run the selected calibration protocol with contractual error and cancellation mapping."""
    try:
        if _dispatch(options, output):
            return
        target = prepare_target(options.mode)
        settings = _settings(target, options)
        _show_preflight(target, settings, output.stdout)
        if not typer.confirm("Start local calibration?", default=False):
            raise CalibrationCancelled("calibration cancelled before process start")
        outcome = run_calibration(target, settings)
        _show_outcome(outcome, output.stdout)
    except (KeyboardInterrupt, typer.Abort, CalibrationCancelled) as error:
        output.stderr.print(f"[yellow]Calibration cancelled:[/yellow] {error}")
        raise typer.Exit(code=130) from error
    except CalibrationRunError as error:
        output.stderr.print(f"[red]Calibration error:[/red] {error}")
        raise typer.Exit(code=1) from error
    except (ConfigError, CalibrationError, ValueError) as error:
        output.stderr.print(f"[red]Calibration input error:[/red] {error}")
        raise typer.Exit(code=2) from error
    except (ContentError, EngineError, HardwareError, PlanError, ProcessError, OSError) as error:
        output.stderr.print(f"[red]Calibration error:[/red] {error}")
        raise typer.Exit(code=1) from error
