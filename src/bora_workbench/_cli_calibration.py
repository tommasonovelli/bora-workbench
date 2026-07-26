"""Present the calibrate command: options, preflight, live progress, summary, and exit codes.

One calibration run is one user-facing conversation—what will be measured, whether to start it,
how far it has got, and what it produced—so the whole conversation lives in one module. Everything
printed before the confirmation is derived from the detected hardware and the requested options,
never from a fixed script: an operator who reads it must be able to predict the contexts that will
be searched, the probe budget that bounds them, and what happens to the records at the end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from types import TracebackType
from typing import cast

import typer
from rich.console import Console
from rich.progress import Progress, TaskID, TimeElapsedColumn

from bora_workbench._calibration_record import RecordError, promote_candidate, records_directory
from bora_workbench._calibration_run import RunOptions, RunResult, run_calibration
from bora_workbench._calibration_runner import ModeResult
from bora_workbench._calibration_trial_control import ProgressEvent
from bora_workbench._calibration_types import (
    BASELINE_CTX,
    CONTEXT_SCALE,
    DEFAULT_PREFERENCE,
    PREFERENCES,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    TEXT_SEARCH_BUDGET,
    VRAM_RESERVE_GIB,
    VSTUDIO_SEARCH_BUDGET,
    EnvelopeResult,
    Preference,
    SearchError,
    UnclassifiableTrialError,
)
from bora_workbench._cli_theme import (
    metric_column,
    phase_result_style,
    print_error,
    print_heading,
    print_note,
    print_success,
    print_warning,
    progress_columns,
)
from bora_workbench.calibration import (
    CalibrationError,
    CalibrationRunError,
    CalibrationTarget,
    prepare_target,
    selected_mode_ids,
)
from bora_workbench.config import ConfigError
from bora_workbench.engine import EngineError
from bora_workbench.hardware import HardwareError
from bora_workbench.process import ProcessError
from bora_workbench.profiles import ContentError, PlanError

_APPROVED_CTX = set(CONTEXT_SCALE)


class CalibrationCancelled(RuntimeError):
    """Mark an operator cancellation that maps to the contractual exit code 130."""


@dataclass(frozen=True, slots=True)
class CalibrationCliInput:
    """Group the parsed CLI values of one calibration invocation."""

    mode: str
    no_activate: bool = False
    activate: bool = False
    target_ctx: int | None = None
    preference: str | None = None


def _target_ctx(arguments: list[str], index: int) -> int:
    """Read and parse the mandatory ``--target-ctx`` value."""
    if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
        raise CalibrationError("--target-ctx requires a value")
    try:
        return int(arguments[index + 1])
    except ValueError as error:
        raise CalibrationError("--target-ctx must be an integer") from error


def parse_calibration_input(
    mode: str, preference: str | None, extras: list[str]
) -> CalibrationCliInput:
    """Parse the documented calibrate extras, rejecting unknown or duplicate options.

    The extras stay outside the Typer callback because the command accepts unknown options in
    order to reject them here with an actionable message instead of Typer's usage error.
    """
    no_activate = False
    activate = False
    target_ctx: int | None = None
    index = 0
    while index < len(extras):
        option = extras[index]
        if option == "--target-ctx":
            if target_ctx is not None:
                raise CalibrationError("--target-ctx may be supplied only once")
            target_ctx = _target_ctx(extras, index)
            index += 2
            continue
        if option == "--no-activate":
            no_activate = True
        elif option == "--activate":
            activate = True
        else:
            raise CalibrationError(f"unknown calibrate option {option!r}")
        index += 1
    return CalibrationCliInput(mode, no_activate, activate, target_ctx, preference)


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
    if options.activate and options.preference is not None:
        raise CalibrationError("--preference cannot relabel an already measured candidate")
    if options.activate and options.target_ctx is not None:
        raise CalibrationError("--target-ctx cannot be used while activating a pending candidate")
    if options.target_ctx is not None and options.target_ctx not in _APPROVED_CTX:
        allowed = ", ".join(str(value) for value in sorted(_APPROVED_CTX, reverse=True))
        raise CalibrationError(f"--target-ctx must be one of: {allowed}")


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
    preference = _preference(options.preference).replace("_", "-")
    console.print(
        f"Local {preference} cell search; no technical input is needed and nothing is sent."
    )
    console.print(f"Modes: {', '.join(mode.id for mode in target.modes)}")
    console.print(f"Backend: {target.hardware.backend}; engine: {target.lock['release']}")
    _print_hardware(target, console)
    console.print(f"Contexts: {_scale_text(target, options.target_ctx)}")
    console.print(
        f"Constants: VRAM reserve {VRAM_RESERVE_GIB} GiB, RAM reserve {RAM_RESERVE_GIB} GiB, "
        f"release tolerance {RELEASE_TOLERANCE_GIB} GiB, {_budget_text(target)}."
    )
    lifecycle = "candidate only" if options.no_activate else "candidate then atomic activation"
    console.print(f"Records: {records_directory()} ({lifecycle}); one cell per selected mode.")
    console.print("Latest-run logs and evidence are retained in one rotated private slot.")
    console.print(
        "Duration: potentially hours; trial crashes are isolated and memory is monitored."
    )


def _format_duration(seconds: float) -> str:
    """Format a learned or elapsed duration for compact terminal feedback."""
    rounded = max(0, round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


# Phases whose total is a budget cap rather than an exact trial count: an adaptive search may
# finish well below it, so the count and the projection must not read as a fixed schedule.
_CAPPED_PHASES = frozenset({"screening", "search", "pairing", "gate"})


def _count_text(event: ProgressEvent) -> str:
    """Distinguish a budget cap from an exact phase total."""
    separator = "/≤" if event.phase in _CAPPED_PHASES else "/"
    return f"{event.completed}{separator}{event.total}"


def _remaining_text(event: ProgressEvent) -> str:
    """Label capped-phase time as a cap projection and an exact phase as an ETA."""
    if event.estimated_remaining_seconds is None:
        return "learning duration…"
    duration = _format_duration(event.estimated_remaining_seconds)
    if event.phase in _CAPPED_PHASES:
        return f"cap projection ≈ {duration}"
    return f"ETA ≈ {duration}"


def _plain_line(event: ProgressEvent) -> str:
    """Build stable non-interactive output for one completed trial."""
    message = f"{event.mode_id} {event.phase}: {_count_text(event)}"
    if event.estimated_remaining_seconds is None:
        return message
    return f"{message}; {_remaining_text(event)}"


class CalibrationProgress:
    """Show a live TTY task while preserving line-oriented redirected output."""

    def __init__(self, console: Console, get_time: Callable[[], float] = monotonic) -> None:
        """Bind progress to the caller's console so terminal detection remains accurate."""
        self._console = console
        self._get_time = get_time
        self._is_live = console.is_terminal
        self._progress = Progress(
            *progress_columns(
                metric_column("count"), TimeElapsedColumn(), metric_column("remaining")
            ),
            console=console,
            refresh_per_second=4,
            transient=True,
            redirect_stdout=False,
            redirect_stderr=False,
            get_time=get_time,
        )
        self._task_id: TaskID | None = None
        self._phase_key: tuple[str, str] | None = None
        self._phase_started_at = 0.0
        self._last_event: ProgressEvent | None = None

    def __enter__(self) -> CalibrationProgress:
        """Start live refresh only for an interactive terminal."""
        if self._is_live:
            self._progress.start()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop Rich cleanly and retain a phase summary on success or failure."""
        del exception, traceback
        if not self._is_live:
            return
        try:
            is_success = exception_type is None or self._is_exact_phase_complete()
            self._finish_phase(is_success)
        finally:
            self._progress.stop()

    def __call__(self, event: ProgressEvent) -> None:
        """Consume one core event as live or line-oriented presentation."""
        if not self._is_live:
            if not event.is_running:
                self._console.print(_plain_line(event))
            return
        self._update_live(event)

    def _update_live(self, event: ProgressEvent) -> None:
        """Create or refresh the single visible mode-phase task."""
        phase_key = (event.mode_id, event.phase)
        if phase_key != self._phase_key:
            self._finish_phase(True)
            self._phase_key = phase_key
            self._phase_started_at = self._get_time()
            self._task_id = self._progress.add_task(
                self._description(event),
                total=event.total,
                completed=event.completed,
                count=_count_text(event),
                remaining=_remaining_text(event),
            )
        else:
            assert self._task_id is not None
            self._progress.update(
                self._task_id,
                total=event.total,
                completed=event.completed,
                description=self._description(event),
                count=_count_text(event),
                remaining=_remaining_text(event),
                refresh=True,
            )
        self._last_event = event

    def _description(self, event: ProgressEvent) -> str:
        """Name the mode, phase, and currently running or completed trial."""
        trial = event.completed + 1 if event.is_running else event.completed
        state = "running" if event.is_running else "complete"
        return f"{event.mode_id} · {event.phase} · trial {trial} {state}"

    def _is_exact_phase_complete(self) -> bool:
        """Recognize completed confirmation even if later record persistence fails."""
        event = self._last_event
        return bool(
            event
            and event.phase == "confirmation"
            and not event.is_running
            and event.completed == event.total
        )

    def _finish_phase(self, is_success: bool) -> None:
        """Persist a concise phase result before replacing the transient task."""
        if self._task_id is None or self._last_event is None or self._phase_key is None:
            return
        elapsed = _format_duration(self._get_time() - self._phase_started_at)
        state = "complete" if is_success else "stopped"
        mode_id, phase = self._phase_key
        completed = self._last_event.completed
        self._progress.remove_task(self._task_id)
        style = phase_result_style(is_success)
        self._progress.console.print(
            f"[{style}]{mode_id} {phase} {state}: {completed} trial(s) in {elapsed}.[/{style}]"
        )
        self._task_id = None
        self._phase_key = None
        self._last_event = None


def _offload(envelope: EnvelopeResult) -> str:
    """Name the measured offload position, which a CPU backend does not have."""
    value = envelope.sample.n_cpu_moe
    return "baseline" if value is None else str(value)


def _memory(envelope: EnvelopeResult) -> str:
    """Describe the minimum memory margin measured while this envelope was running."""
    sample = envelope.sample
    values = [f"RAM available min {sample.ram_min_available_gib:.2f} GiB"]
    if sample.vram_min_free_gib is not None:
        values.append(f"VRAM free min {sample.vram_min_free_gib:.2f} GiB")
    return ", ".join(values)


def _envelope_line(envelope: EnvelopeResult) -> str:
    """Summarize the one measured preference cell this mode will launch with."""
    sample = envelope.sample
    return (
        f"  {envelope.preference}: ctx={sample.ctx}, n_cpu_moe={_offload(envelope)}; "
        f"{sample.e2e_ms:.0f} ms short e2e, {sample.decode_tps:.2f} tok/s decode, "
        f"{sample.prefill_tps:.2f} tok/s prefill; {_memory(envelope)}"
    )


def _mode_lines(result: ModeResult) -> list[str]:
    """Build the per-mode header and its one selected preference cell."""
    return [
        f"{result.mode.id}: {len(result.samples)} measured sample(s)",
        _envelope_line(result.envelope),
    ]


def show_outcome(result: RunResult, console: Console) -> None:
    """Print one measured cell per mode, then the record and evidence locations."""
    state = "completed for every selected mode" if not result.failures else "completed partially"
    print_success(console, f"Local calibration {state}.")
    for mode_result in result.mode_results:
        for line in _mode_lines(mode_result):
            console.print(line)
    for path in result.record_paths:
        print_note(console, "Record", str(path))
    for failure in result.failures:
        print_warning(console, f"No record written for {failure}")
    console.print(f"Private run evidence: {result.evidence_path}")
    console.print("No private record or process log was uploaded.")


def _activate(mode_value: str, console: Console) -> None:
    """Promote already measured candidates without rerunning expensive trials."""
    for mode_id in selected_mode_ids(mode_value):
        try:
            path = promote_candidate(mode_id)
        except RecordError as error:
            raise CalibrationRunError(str(error)) from error
        print_success(console, "Activated calibration candidate", str(path))


def _measure(target: CalibrationTarget, run_options: RunOptions) -> RunResult:
    """Map search and classification failures onto the contractual operational exit code.

    Both are operational: the input was valid and processes already ran (spec 5.11).
    """
    try:
        return run_calibration(target, run_options)
    except (UnclassifiableTrialError, SearchError) as error:
        raise CalibrationRunError(str(error)) from error


def _run(options: CalibrationCliInput, stdout: Console) -> None:
    """Activate pending candidates or measure one preference cell per selected mode."""
    _validate(options)
    if options.activate:
        _activate(options.mode, stdout)
        return
    preference = _preference(options.preference)
    target = prepare_target(options.mode)
    show_preflight(target, options, stdout)
    if not typer.confirm("Start calibration?", default=False):
        raise CalibrationCancelled("calibration cancelled before process start")
    with CalibrationProgress(stdout) as progress:
        run_options = RunOptions(
            preference=preference,
            target_ctx=options.target_ctx,
            is_activate=not options.no_activate,
            progress=progress,
        )
        result = _measure(target, run_options)
    show_outcome(result, stdout)
    if result.failures:
        # The records that were written stay valid and activated; the run is still incomplete, so
        # the exit code must not claim success for modes that produced nothing (spec 5.11).
        raise CalibrationRunError("calibration did not complete for: " + "; ".join(result.failures))


def run_calibrate(options: CalibrationCliInput, stdout: Console, stderr: Console) -> None:
    """Run calibration with contractual error and cancellation mapping (spec 5.11)."""
    try:
        _run(options, stdout)
    except (KeyboardInterrupt, typer.Abort, CalibrationCancelled) as error:
        print_warning(stderr, f"Calibration cancelled: {error}")
        raise typer.Exit(code=130) from error
    except CalibrationRunError as error:
        print_error(stderr, "Calibration error", str(error))
        raise typer.Exit(code=1) from error
    except (ConfigError, CalibrationError, ValueError) as error:
        print_error(stderr, "Calibration input error", str(error))
        raise typer.Exit(code=2) from error
    except (ContentError, EngineError, HardwareError, PlanError, ProcessError, OSError) as error:
        print_error(stderr, "Calibration error", str(error))
        raise typer.Exit(code=1) from error
