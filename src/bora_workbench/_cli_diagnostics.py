"""Present the commands that install and report on the local installation.

`engine install` and `engine status` provision and inspect the pinned managed llama.cpp build,
`validate` checks the packaged content, and `doctor` reports both of them together with the
configuration, the detected hardware and the local calibration records. None of these commands
touches the process layer: they describe or repair what is on disk, never what is running.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from types import TracebackType

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.text import Text

from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench._cli_models import pull_model
from bora_workbench._cli_theme import (
    format_bytes,
    format_duration,
    metric_column,
    phase_result_style,
    print_error,
    print_note,
    print_success,
    print_warning,
    progress_columns,
    status_table,
)
from bora_workbench.config import ConfigError
from bora_workbench.engine import (
    Backend,
    EngineError,
    EngineStatus,
    InstallProgressEvent,
    InstallResult,
    engine_status,
    install_engine,
    load_engine_lock,
)
from bora_workbench.hardware import HardwareError, HardwareInfo, detect_hardware
from bora_workbench.profiles import ContentError
from bora_workbench.snapshot import DoctorSnapshot, SnapshotError, collect_doctor_snapshot
from bora_workbench.validation import ValidationIssue, ValidationResult, validate_resources


@dataclass(frozen=True, slots=True)
class EngineInstallOptions:
    """Group what `engine install` was asked to reinstall and to acquire."""

    force: bool
    include_model: bool


def _position(event: InstallProgressEvent) -> str:
    """Show which locked asset is active when the target contains multiple archives."""
    if event.item_index is None or event.item_count is None:
        return ""
    return f"[{event.item_index}/{event.item_count}] "


def _phase_message(event: InstallProgressEvent) -> str:
    """Translate one core event into concise user-facing installation progress."""
    asset = event.detail or "asset"
    position = _position(event)
    messages = {
        "asset": f"Checking locked asset {position}{asset}",
        "download": f"Downloading {position}{asset}",
        "extract": f"Extracting {position}{asset}",
        "compile": "Configuring and compiling Ubuntu CUDA llama-server",
        "verify": "Verifying llama-server version and help contracts",
        "activate": "Activating the verified managed engine",
    }
    return messages[event.stage]


def _plain_line(event: InstallProgressEvent) -> str:
    """Build one durable phase line for redirected output."""
    if event.stage == "download" and event.is_cached:
        return f"Using verified cached asset {_position(event)}{event.detail}."
    message = _phase_message(event)
    if event.stage == "compile":
        message += "; this can take several minutes"
    return f"{message}."


class EngineInstallProgress:
    """Show one live phase task while keeping redirected logs line-oriented."""

    def __init__(self, console: Console, get_time: Callable[[], float] = monotonic) -> None:
        """Bind progress to the command console and a testable monotonic clock."""
        self._console = console
        self._get_time = get_time
        self._is_live = console.is_terminal
        self._progress = Progress(
            *progress_columns(metric_column("metrics"), metric_column("eta")),
            console=console,
            refresh_per_second=4,
            transient=True,
            redirect_stdout=False,
            redirect_stderr=False,
            get_time=get_time,
        )
        self._task_id: TaskID | None = None
        self._phase_key: tuple[str, str | None, int | None] | None = None
        self._phase_started_at = 0.0
        self._last_refresh_at = 0.0
        self._last_event: InstallProgressEvent | None = None

    def __enter__(self) -> EngineInstallProgress:
        """Start live refresh only when attached to an interactive terminal."""
        if self._is_live:
            self._progress.start()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop Rich cleanly and retain an honest measured-phase summary."""
        del exception, traceback
        if not self._is_live:
            return
        try:
            self._finish_phase(exception_type is None)
        finally:
            self._progress.stop()

    def __call__(self, event: InstallProgressEvent) -> None:
        """Consume one core event as live or line-oriented presentation."""
        phase_key = (event.stage, event.detail, event.item_index)
        if not self._is_live:
            if phase_key != self._phase_key:
                self._console.print(_plain_line(event))
                self._phase_key = phase_key
            return
        self._update_live(event, phase_key)

    def _update_live(
        self, event: InstallProgressEvent, phase_key: tuple[str, str | None, int | None]
    ) -> None:
        """Create or refresh the single visible installation task."""
        if event.stage == "compile":
            total = None if event.percent is None else 100
            completed = event.percent or 0
        else:
            total, completed = event.total_bytes, event.completed_bytes or 0
        if phase_key != self._phase_key:
            self._finish_phase(True)
            self._phase_key = phase_key
            self._phase_started_at = self._get_time()
            self._last_refresh_at = self._phase_started_at
            self._task_id = self._progress.add_task(
                _phase_message(event), total=total, metrics="", eta=""
            )
        assert self._task_id is not None
        metrics, eta = self._phase_fields(event)
        now = self._get_time()
        is_complete = total is not None and completed >= total
        should_refresh = is_complete or now - self._last_refresh_at >= 0.25
        self._progress.update(
            self._task_id,
            total=total,
            completed=completed,
            metrics=metrics,
            eta=eta,
            refresh=should_refresh,
        )
        if should_refresh:
            self._last_refresh_at = now
        self._last_event = event

    def _phase_fields(self, event: InstallProgressEvent) -> tuple[str, str]:
        """Show the compile percentage, or the transfer byte count, rate, and estimate."""
        if event.stage == "compile":
            return (f"{event.percent}%" if event.percent is not None else ""), ""
        if event.completed_bytes is None:
            return "", ""
        completed = event.completed_bytes
        total = event.total_bytes
        amount = format_bytes(completed)
        if total is not None:
            amount = f"{amount}/{format_bytes(total)}"
        elapsed = self._get_time() - self._phase_started_at
        if elapsed <= 0 or completed <= 0:
            return amount, "ETA learning…" if total else ""
        rate = completed / elapsed
        metrics = f"{amount} · {format_bytes(rate)}/s"
        if total is None:
            return metrics, ""
        remaining = max(0, total - completed) / rate
        return metrics, f"ETA ~ {format_duration(remaining)}"

    def _finish_phase(self, is_success: bool) -> None:
        """Clear the transient task and retain summaries for measured work."""
        if self._task_id is None:
            return
        self._progress.remove_task(self._task_id)
        event = self._last_event
        if event is not None and event.completed_bytes is not None:
            elapsed = format_duration(self._get_time() - self._phase_started_at)
            state = "complete" if is_success else "stopped"
            if event.stage == "download" and event.is_cached:
                state = "cached"
            style = phase_result_style(is_success)
            self._progress.console.print(
                f"[{style}]{_phase_message(event)} {state} in {elapsed}.[/{style}]"
            )
        self._task_id = None
        self._phase_key = None
        self._last_event = None


def _print_status(status: EngineStatus, stdout: Console, stderr: Console) -> None:
    """Render one already inspected managed-engine status."""
    table = status_table("managed llama.cpp engine")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Active", "yes" if status.is_active else "no")
    table.add_row("Release", Text(status.release or "none"))
    table.add_row("Backend", Text(status.backend or "none"))
    table.add_row(
        "Executable",
        Text(str(status.executable) if status.executable else "none"),
    )
    table.add_row("Compatible", "yes" if status.is_compatible else "no")
    stdout.print(table)
    is_blocking = not status.is_compatible and status.differences != ("not installed",)
    for difference in status.differences:
        if is_blocking:
            print_error(stderr, "Engine status error", difference)
        else:
            print_warning(stdout, f"Difference: {difference}")


def _install_with_progress(backend: Backend, force: bool, stdout: Console) -> InstallResult:
    """Run installation with live byte progress or durable redirected phase lines."""
    with EngineInstallProgress(stdout) as progress:
        return install_engine(backend, force, progress)


def _report_install(result: InstallResult, stdout: Console) -> None:
    """State what the managed engine installation left active."""
    action = "Installed and activated" if result.was_installed else "Already active"
    print_success(stdout, action, f"llama.cpp {result.status.release}")
    print_note(stdout, "Backend", result.status.backend or "none")
    print_note(stdout, "Executable", str(result.status.executable))


def run_engine_install(options: EngineInstallOptions, stdout: Console, stderr: Console) -> None:
    """Install the engine, then acquire the pinned model unless the caller declined it.

    The weights are fetched here because an engine without them cannot serve anything, and asking
    a first-time user to discover a second command was the largest part of the old setup (D-078).
    """
    try:
        hardware = detect_hardware()
        for warning in hardware.warnings:
            print_warning(stdout, warning)
        stdout.print(f"Installing llama.cpp for backend={hardware.backend} from engine.lock.")
        stdout.print("Third-party notices will be retained inside the managed installation.")
        if hardware.backend == "cuda":
            stdout.print("Managed Windows CUDA runtime assets are subject to the NVIDIA CUDA EULA.")
        result = _install_with_progress(hardware.backend, options.force, stdout)
        _report_install(result, stdout)
        if options.include_model:
            pull_model(load_engine_lock(), stdout)
    except (EngineError, HardwareError) as error:
        print_error(stderr, "Engine installation error", str(error))
        raise typer.Exit(code=1) from error
    except KeyboardInterrupt as error:
        print_warning(stderr, "Interrupted; nothing incomplete was kept.")
        raise typer.Exit(code=130) from error


def show_engine_status(stdout: Console, stderr: Console) -> None:
    """Show the active manifest, compatibility, and exact differences from the lock."""
    try:
        status = engine_status()
    except EngineError as error:
        print_error(stderr, "Engine status error", str(error))
        raise typer.Exit(code=1) from error
    _print_status(status, stdout, stderr)
    is_absent = status.differences == ("not installed",)
    if not status.is_compatible and not is_absent:
        raise typer.Exit(code=1)


def _print_issue(item: ValidationIssue, stdout: Console, stderr: Console) -> None:
    """Print one validation issue to the stream appropriate for its severity."""
    label = f"{item.file}:{item.field_path}: {item.message}"
    if item.severity == "error":
        print_error(stderr, "Invalid resource", label)
    else:
        print_warning(stdout, label)


def show_validation(result: ValidationResult, stdout: Console, stderr: Console) -> None:
    """Print deterministic validation details and a concise summary."""
    for item in result.issues:
        _print_issue(item, stdout, stderr)
    if result.errors:
        print_error(stderr, "Validation failed", f"{len(result.errors)} error(s)")
    else:
        print_success(stdout, "Validation passed", f"with {len(result.warnings)} warning(s)")


def run_validate(stdout: Console, stderr: Console) -> None:
    """Validate packaged content and map inaccessible resources without a traceback."""
    try:
        result = validate_resources()
    except OSError as error:
        print_error(stderr, "Validation error", f"could not read packaged resources: {error}")
        raise typer.Exit(code=1) from error
    show_validation(result, stdout, stderr)
    if result.errors:
        raise typer.Exit(code=1)


def _gib(value: float | None) -> str:
    """Format an exact GiB measurement for human diagnostics."""
    return "not applicable" if value is None else f"{value:.2f} GiB"


def _gpu_label(hardware: HardwareInfo) -> str:
    """Describe the selected GPU without implying multi-GPU launch support."""
    if hardware.gpu_index is None:
        return "none"
    return f"{hardware.gpu_name} (index {hardware.gpu_index}, detected {hardware.gpu_count})"


def _doctor_table(data: DoctorSnapshot) -> Table:
    """Build the diagnostics table exclusively from one collected snapshot."""
    config, hardware = data.configuration.config, data.hardware
    paths = data.paths
    table = status_table("bora-workbench diagnostics")
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
        ("Shared profiles", str(data.compatible_profiles) if data.compatible_profiles else "none"),
        ("Managed engine", "active" if data.engine.is_active else "not installed"),
        ("Engine release", data.engine.release or "none"),
        ("Engine backend", data.engine.backend or "none"),
        ("Engine compatible", "yes" if data.engine.is_compatible else "no"),
        ("Engine executable", str(data.engine.executable) if data.engine.executable else "none"),
        ("Config directory", str(paths.config)),
        ("Data directory", str(paths.data)),
        ("Cache directory", str(paths.cache)),
        ("State directory", str(paths.state)),
    ]
    for label, value in rows:
        table.add_row(label, Text(value))
    return table


def _calibrated_parameters(ctx: int | None, n_cpu_moe: int | None) -> str:
    """Show the record's launch parameters so "calibrated" is verifiable at a glance."""
    if ctx is None:
        return ""
    if n_cpu_moe is None:
        return f" (ctx {ctx})"
    return f" (ctx {ctx}, --n-cpu-moe {n_cpu_moe})"


def _record_line(mode_id: str, evaluation: RecordEvaluation) -> str:
    """Describe active, candidate, superseded, invalid, and headroom record states."""
    detail = escape(evaluation.diagnostics[0]) if evaluation.diagnostics else ""
    suffix = ""
    if evaluation.candidate_status == "valid":
        suffix = " Pending candidate is valid and awaits `calibrate --activate`."
    elif evaluation.candidate_status in {"invalid", "superseded"}:
        candidate_detail = escape(evaluation.candidate_diagnostics[0])
        suffix = f" Pending candidate is {evaluation.candidate_status}: {candidate_detail}"
    if evaluation.status == "valid":
        parameters = _calibrated_parameters(evaluation.ctx, evaluation.n_cpu_moe)
        preference = evaluation.preference or "unknown"
        return (
            f"[green]Calibration[/green] {mode_id}: active {preference} cell "
            f"valid{parameters}.{suffix}"
        )
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


def _collect_doctor(version: str, stderr: Console) -> DoctorSnapshot:
    """Collect doctor data and map expected domain failures to contractual exits."""
    try:
        return collect_doctor_snapshot(version)
    except ConfigError as error:
        print_error(stderr, "Configuration error", str(error))
        raise typer.Exit(code=2) from error
    except HardwareError as error:
        print_error(stderr, "Hardware error", str(error))
        raise typer.Exit(code=1) from error
    except (ContentError, EngineError, OSError, SnapshotError) as error:
        print_error(stderr, "Doctor error", str(error))
        raise typer.Exit(code=1) from error


def run_doctor(version: str, stdout: Console, stderr: Console) -> None:
    """Render one structured doctor snapshot without computing during presentation."""
    data = _collect_doctor(version, stderr)
    stdout.print(_doctor_table(data))
    for warning in data.hardware.warnings:
        print_warning(stdout, warning)
    for record in data.records:
        stdout.print(_record_line(record.mode_id, record.evaluation))
    for difference in data.engine.differences:
        print_warning(stdout, f"Engine: {difference}")
    show_validation(data.validation, stdout, stderr)
    if data.validation.errors:
        raise typer.Exit(code=1)
