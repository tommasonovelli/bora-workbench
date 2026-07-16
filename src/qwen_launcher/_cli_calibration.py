"""Collect explicit Step 5A inputs and present calibration draft evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from qwen_launcher.calibration import (
    CalibrationError,
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


def _explicit_settings(value: str, target: CalibrationTarget) -> tuple[int, float | None]:
    """Parse explicit ``RUNS[:MIN_FREE_VRAM_GIB]`` values without defaults."""
    fields = value.split(":")
    expected = 2 if target.hardware.backend == "cuda" else 1
    if len(fields) != expected:
        syntax = "RUNS:MIN_FREE_VRAM_GIB" if expected == 2 else "RUNS"
        raise CalibrationError(f"--settings must use {syntax} syntax")
    try:
        return int(fields[0]), float(fields[1]) if expected == 2 else None
    except ValueError as error:
        raise CalibrationError("--settings values must be numeric") from error


def _settings(target: CalibrationTarget, options: CalibrationCliInput) -> CalibrationSettings:
    """Resolve missing policy-free values interactively without assigning author defaults."""
    values = options.candidate_values or _prompt_candidates(target)
    candidates = tuple(parse_candidate(value, target.hardware.backend) for value in values)
    if options.settings_value is not None:
        starts, reserve = _explicit_settings(options.settings_value, target)
    else:
        starts = typer.prompt("Required fresh stable starts per candidate", type=int)
        reserve = None
        if target.hardware.backend == "cuda":
            reserve = typer.prompt("Minimum free VRAM reserve in GiB", type=float)
    return CalibrationSettings(candidates, starts, reserve)


def _show_preflight(
    target: CalibrationTarget, settings: CalibrationSettings, console: Console
) -> None:
    """Show exact workload, risk, evidence location, and detected baseline before confirmation."""
    console.print("[bold]Calibration preflight[/bold]")
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


def _show_outcome(path: Path, console: Console) -> None:
    """Print every exact shareable file and the manual privacy-review boundary."""
    console.print(f"[green]Draft bundle created:[/green] {path}")
    console.print("Proposed selections are not accepted profiles and no data was uploaded.")
    files = sorted(file for file in path.rglob("*") if file.is_file())
    for file in files:
        relative = file.relative_to(path).as_posix()
        console.print(f"\n[bold]Exact shareable preview: {relative}[/bold]")
        console.print(file.read_text(encoding="utf-8", errors="replace"), markup=False)
    console.print("Review every file above; privacy_reviewed remains false until human review.")


def run_calibrate(options: CalibrationCliInput, output: CalibrationCliOutput) -> None:
    """Run the interactive calibration command with contractual error and cancellation mapping."""
    try:
        target = prepare_target(options.mode)
        settings = _settings(target, options)
        _show_preflight(target, settings, output.stdout)
        if not typer.confirm("Start local calibration?", default=False):
            raise CalibrationCancelled("calibration cancelled before process start")
        outcome = run_calibration(target, settings)
        _show_outcome(outcome.bundle_path, output.stdout)
    except (KeyboardInterrupt, typer.Abort, CalibrationCancelled) as error:
        output.stderr.print(f"[yellow]Calibration cancelled:[/yellow] {error}")
        raise typer.Exit(code=130) from error
    except (ConfigError, CalibrationError, ValueError) as error:
        output.stderr.print(f"[red]Calibration input error:[/red] {error}")
        raise typer.Exit(code=2) from error
    except (ContentError, EngineError, HardwareError, PlanError, ProcessError, OSError) as error:
        output.stderr.print(f"[red]Calibration error:[/red] {error}")
        raise typer.Exit(code=1) from error
