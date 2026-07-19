"""Run one fresh calibration/v3 process with joint resource and timing evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from qwen_launcher._calibration_ram import RamError, RamMonitor, RamReserveError, RamSummary
from qwen_launcher._calibration_v3_process_types import TrialFailure, TrialMeasurement, TrialSpec
from qwen_launcher._calibration_v3_types import (
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    TrialEvidence,
)
from qwen_launcher._calibration_vram import (
    VramEnvironmentError,
    VramError,
    VramMonitor,
    VramSummary,
    VramThresholds,
)
from qwen_launcher.benchmark import BenchmarkResult, run_benchmark, run_probe, run_vision_probe
from qwen_launcher.calibration import CalibrationRunError, CalibrationTarget
from qwen_launcher.engine import build_command
from qwen_launcher.process import RunningService, StartRequest, start_service, stop_services
from qwen_launcher.profiles import Mode


@dataclass(slots=True)
class _SpawnRecord:
    """Capture child identity before health readiness can fail."""

    pid: int | None = None

    def __call__(self, pid: int) -> None:
        """Record the exact PID reported immediately after shell-free spawn."""
        self.pid = pid


@dataclass(frozen=True, slots=True)
class _CompletedTrial:
    """Group cleanup timestamps and resource summaries for evidence assembly."""

    started_at: str
    finished_at: str
    vram: VramSummary | None
    ram: RamSummary | None


@dataclass(slots=True)
class _TrialState:
    """Track monitors and process identity for one running trial."""

    vram_monitor: VramMonitor | None
    ram_monitor: RamMonitor
    running: RunningService | None = None
    spawned: _SpawnRecord = field(default_factory=_SpawnRecord)
    benchmark: BenchmarkResult | None = None


def _monitors(target: CalibrationTarget) -> tuple[VramMonitor | None, RamMonitor]:
    """Apply the universal RAM reserve and CUDA-only VRAM thresholds (D-042)."""
    ram = RamMonitor(minimum_free_gib=RAM_RESERVE_GIB)
    if target.hardware.backend == "cpu":
        return None, ram
    if target.hardware.gpu_index is None:
        raise CalibrationRunError("CUDA calibration requires a selected GPU index")
    thresholds = VramThresholds(VRAM_RESERVE_GIB, RELEASE_TOLERANCE_GIB)
    return VramMonitor(target.hardware.gpu_index, thresholds), ram


def _workload(mode: Mode, base_url: str, with_benchmark: bool) -> BenchmarkResult | None:
    """Run real mode load and a complete benchmark on every confirmation session."""
    if mode.services.vision:
        run_vision_probe(base_url)
    if with_benchmark:
        return run_benchmark(base_url)
    run_probe(base_url)
    return None


def _execute(target: CalibrationTarget, spec: TrialSpec, state: _TrialState) -> None:
    """Start monitors and the fresh server, then exercise the mode workload."""
    if state.vram_monitor is not None:
        state.vram_monitor.start()
    state.ram_monitor.start()
    command = build_command(target.executable, spec.plan, target.lock)
    request = StartRequest(command, spec.plan, target.lock, state.spawned)
    state.running = start_service(request, spec.root)
    base_url = f"http://127.0.0.1:{spec.plan.port}"
    state.benchmark = _workload(spec.plan.mode, base_url, spec.with_benchmark)


def _prefer_cleanup_error(current: BaseException | None, new: BaseException) -> BaseException:
    """Prefer run-invalidating monitor failures over candidate-level diagnostics."""
    if isinstance(current, (VramEnvironmentError, RamError)):
        return current
    if isinstance(new, (VramEnvironmentError, RamError)):
        return new
    return new if current is None else current


def _finish(
    state: _TrialState, root: Path
) -> tuple[VramSummary | None, RamSummary | None, BaseException | None]:
    """Stop the process and finalize both monitors without dropping reserve evidence."""
    error: BaseException | None = None
    vram: VramSummary | None = None
    ram: RamSummary | None = None
    if state.running is not None:
        try:
            stop_services(root)
        except BaseException as caught:
            error = _prefer_cleanup_error(error, caught)
    if state.vram_monitor is not None:
        pid = state.spawned.pid if state.running is None else state.running.process.pid
        try:
            vram = state.vram_monitor.finish(pid)
        except BaseException as caught:
            if isinstance(caught, VramError) and caught.summary is not None:
                vram = caught.summary
            error = _prefer_cleanup_error(error, caught)
    try:
        ram = state.ram_monitor.finish()
    except BaseException as caught:
        if isinstance(caught, RamReserveError):
            ram = caught.summary
        error = _prefer_cleanup_error(error, caught)
    return vram, ram, error


def _timestamp() -> str:
    """Return one strict UTC timestamp suitable for calibration-record/v2."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _log_path(spec: TrialSpec, state: _TrialState) -> str | None:
    """Return a run-relative log reference that survives evidence-directory promotion."""
    path = Path(state.running.state.log_path) if state.running is not None else None
    if path is None:
        path = next(iter(sorted(spec.root.glob("logs/*.log"))), None)
    if path is None:
        return None
    try:
        return path.resolve().relative_to(spec.evidence_root.resolve()).as_posix()
    except ValueError:
        return None


def _evidence(spec: TrialSpec, state: _TrialState, completed: _CompletedTrial) -> TrialEvidence:
    """Assemble detailed per-process evidence after full cleanup."""
    return TrialEvidence(
        spec.order,
        completed.started_at,
        completed.finished_at,
        state.benchmark,
        completed.vram,
        completed.ram,
        _log_path(spec, state),
    )


def run_trial(target: CalibrationTarget, spec: TrialSpec) -> TrialMeasurement:
    """Start, exercise, stop, and verify one isolated calibration/v3 trial."""
    state = _TrialState(*_monitors(target))
    started_at = _timestamp()
    failure: BaseException | None = None
    try:
        _execute(target, spec, state)
    except BaseException as caught:
        failure = caught
    vram, ram, cleanup_error = _finish(state, spec.root)
    completed = _CompletedTrial(started_at, _timestamp(), vram, ram)
    evidence = _evidence(spec, state, completed)
    failure = failure or cleanup_error
    if failure is None:
        assert isinstance(ram, RamSummary)
        return TrialMeasurement(state.benchmark, vram, ram, evidence)
    if not isinstance(failure, Exception):
        raise failure
    if isinstance(failure, (VramEnvironmentError, RamError)):
        raise failure
    raise TrialFailure(failure, evidence) from failure
