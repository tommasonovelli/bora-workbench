"""Run the read-only doctor command and build its Rich diagnostics presentation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from qwen_launcher._cli_theme import print_error, print_warning, status_table
from qwen_launcher._engine_types import EngineStatus
from qwen_launcher.config import Config, ConfigError, load_config
from qwen_launcher.hardware import HardwareError, HardwareInfo, detect_hardware


@dataclass(frozen=True, slots=True)
class DoctorData:
    """Group read-only doctor values and computed public paths."""

    config: Config
    hardware: HardwareInfo
    shared_seeds: int
    version: str
    directories: tuple[Path, Path, Path, Path]
    engine: EngineStatus


def _gib(value: float | None) -> str:
    """Format an exact GiB measurement for human diagnostics."""
    return "not applicable" if value is None else f"{value:.2f} GiB"


def _gpu_label(hardware: HardwareInfo) -> str:
    """Describe the selected GPU without implying multi-GPU launch support."""
    if hardware.gpu_index is None:
        return "none"
    return f"{hardware.gpu_name} (index {hardware.gpu_index}, detected {hardware.gpu_count})"


def build_doctor_table(data: DoctorData) -> Table:
    """Build the read-only diagnostics table from already collected service values."""
    config, hardware = data.config, data.hardware
    table = status_table("qwen-launcher diagnostics")
    table.add_column("Item")
    table.add_column("Value")
    rows = [
        ("Version", data.version),
        ("Configuration", "valid"),
        ("Model", config.model),
        ("llama.cpp port", str(config.llama_port)),
        ("OS", f"{hardware.os_name} — {hardware.os_version}"),
        ("CPU", f"{hardware.cpu_name} ({hardware.cpu_cores} logical cores)"),
        ("RAM total", _gib(hardware.ram_total_gib)),
        ("RAM available", _gib(hardware.ram_available_gib)),
        ("Backend", hardware.backend),
        ("GPU", _gpu_label(hardware)),
        ("VRAM total", _gib(hardware.vram_total_gib)),
        ("VRAM free", _gib(hardware.vram_free_gib)),
        ("Shared profile seeds", str(data.shared_seeds) if data.shared_seeds else "none"),
        ("Managed engine", "active" if data.engine.is_active else "not installed"),
        ("Engine release", data.engine.release or "none"),
        ("Engine backend", data.engine.backend or "none"),
        ("Engine compatible", "yes" if data.engine.is_compatible else "no"),
        ("Engine executable", str(data.engine.executable) if data.engine.executable else "none"),
        ("Config directory", str(data.directories[0])),
        ("Data directory", str(data.directories[1])),
        ("Cache directory", str(data.directories[2])),
        ("State directory", str(data.directories[3])),
    ]
    for label, value in rows:
        table.add_row(label, value)
    return table


def _calibrated_parameters(ctx: int | None, n_cpu_moe: int | None) -> str:
    """Show the record's launch parameters so "calibrated" is verifiable at a glance."""
    if ctx is None:
        return ""
    if n_cpu_moe is None:
        return f" (ctx {ctx})"
    return f" (ctx {ctx}, --n-cpu-moe {n_cpu_moe})"


def _record_line(mode_id: str, evaluation: object) -> str:
    """Describe active, candidate, superseded, invalid, and headroom record states."""
    from qwen_launcher._calibration_reuse import RecordEvaluation

    if not isinstance(evaluation, RecordEvaluation):
        raise TypeError("doctor record evaluation has an invalid runtime type")
    detail = evaluation.diagnostics[0] if evaluation.diagnostics else ""
    suffix = ""
    if evaluation.candidate_status == "valid":
        suffix = " Pending candidate is valid and awaits `calibrate --activate`."
    elif evaluation.candidate_status in {"invalid", "superseded"}:
        candidate_detail = evaluation.candidate_diagnostics[0]
        suffix = f" Pending candidate is {evaluation.candidate_status}: {candidate_detail}"
    if evaluation.status == "valid":
        parameters = _calibrated_parameters(evaluation.ctx, evaluation.n_cpu_moe)
        return f"[green]Calibration[/green] {mode_id}: active record valid{parameters}.{suffix}"
    if evaluation.status == "missing":
        return (
            f"[yellow]Calibration[/yellow] {mode_id}: no active record; "
            f"baseline not optimized.{suffix}"
        )
    if evaluation.status == "candidate":
        return f"[yellow]Calibration[/yellow] {mode_id}: valid candidate awaits activation."
    if evaluation.status == "superseded":
        return (
            f"[yellow]Calibration[/yellow] {mode_id}: record schema superseded: {detail}.{suffix}"
        )
    if evaluation.status == "insufficient-headroom":
        return f"[yellow]Calibration[/yellow] {mode_id}: {detail}{suffix}"
    label = "invalid" if evaluation.status == "invalid" else "stale"
    return f"[yellow]Calibration[/yellow] {mode_id}: active record is {label}: {detail}{suffix}"


def _record_lines(config: Config, hardware: HardwareInfo) -> tuple[str, ...]:
    """Evaluate every packaged mode's local record against the current machine."""
    from qwen_launcher._calibration_reuse import ReuseQuery, evaluate_record
    from qwen_launcher.engine import load_engine_lock
    from qwen_launcher.profiles import load_catalog

    lock = load_engine_lock()
    lines = []
    for mode in load_catalog().modes:
        evaluation = evaluate_record(ReuseQuery(config, mode.id, hardware, lock))
        lines.append(_record_line(mode.id, evaluation))
    return tuple(lines)


def run_doctor(version: str, stdout: Console, stderr: Console) -> None:
    """Describe configuration, hardware, content, records, and paths without modifying anything."""
    from qwen_launcher._cli_validation import show_validation
    from qwen_launcher.engine import engine_status
    from qwen_launcher.paths import cache_dir, config_dir, data_dir, state_dir
    from qwen_launcher.profiles import load_catalog
    from qwen_launcher.validation import validate_resources

    try:
        config = load_config()
    except ConfigError as error:
        print_error(stderr, "Configuration error", str(error))
        raise typer.Exit(code=2) from error
    try:
        hardware = detect_hardware()
    except HardwareError as error:
        print_error(stderr, "Hardware error", str(error))
        raise typer.Exit(code=1) from error
    validation = validate_resources()
    shared_seeds = 0
    record_lines: tuple[str, ...] = ()
    if not validation.errors:
        catalog = load_catalog()
        shared_seeds = sum(profile.is_engine_compatible for profile in catalog.profiles)
        record_lines = _record_lines(config, hardware)
    managed_engine = engine_status()
    directories = (config_dir(), data_dir(), cache_dir(), state_dir())
    data = DoctorData(config, hardware, shared_seeds, version, directories, managed_engine)
    stdout.print(build_doctor_table(data))
    for warning in hardware.warnings:
        print_warning(stdout, warning)
    for line in record_lines:
        stdout.print(line)
    for difference in managed_engine.differences:
        print_warning(stdout, f"Engine: {difference}")
    show_validation(validation, stdout, stderr)
    if validation.errors:
        raise typer.Exit(code=1)
