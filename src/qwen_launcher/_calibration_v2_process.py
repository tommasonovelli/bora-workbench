"""Run one fresh calibration/v2 trial process with joint VRAM and RAM monitoring.

Every screening probe and finalist start is a fresh, isolated process exercised with the real mode
workload while VRAM (CUDA) and RAM (all backends) are sampled at the protocol interval (design
document section 3, steps 2-3). Environment failures propagate and invalidate the whole run;
everything else becomes a candidate-level ``TrialFailure`` that keeps the measured evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from qwen_launcher._calibration_ram import RamError, RamMonitor, RamSummary
from qwen_launcher._calibration_v2_types import RELEASE_TOLERANCE_GIB, VRAM_RESERVE_GIB
from qwen_launcher._calibration_vram import (
    VramEnvironmentError,
    VramError,
    VramMonitor,
    VramSummary,
    VramThresholds,
)
from qwen_launcher.benchmark import BenchmarkResult, run_benchmark, run_probe, run_vision_probe
from qwen_launcher.calibration import CalibrationError, CalibrationTarget
from qwen_launcher.engine import build_command
from qwen_launcher.process import RunningService, StartRequest, start_service, stop_services
from qwen_launcher.profiles import LaunchPlan, Mode


class TrialFailure(RuntimeError):
    """Retain measured evidence when one candidate trial must be judged infeasible."""

    def __init__(self, error: Exception, evidence: tuple[VramSummary | None, RamSummary | None]):
        """Keep the original expected failure and any completed monitor summaries."""
        super().__init__(str(error))
        self.error = error
        self.vram, self.ram = evidence


@dataclass(frozen=True, slots=True)
class TrialSpec:
    """Group one candidate launch plan, isolated root, and benchmark requirement."""

    plan: LaunchPlan
    root: Path
    with_benchmark: bool


@dataclass(frozen=True, slots=True)
class TrialMeasurement:
    """Hold one completed trial's benchmark and monitor evidence."""

    benchmark: BenchmarkResult | None
    vram: VramSummary | None
    ram: RamSummary


@dataclass(slots=True)
class _SpawnRecord:
    """Capture child identity before health readiness can fail."""

    pid: int | None = None

    def __call__(self, pid: int) -> None:
        """Record the exact PID reported immediately after shell-free spawn."""
        self.pid = pid


@dataclass(slots=True)
class _TrialState:
    """Track the monitors and process identity of one running trial."""

    vram_monitor: VramMonitor | None
    ram_monitor: RamMonitor
    running: RunningService | None = None
    spawned: _SpawnRecord = field(default_factory=_SpawnRecord)
    benchmark: BenchmarkResult | None = None


def _monitors(target: CalibrationTarget) -> tuple[VramMonitor | None, RamMonitor]:
    """Create RAM monitoring for every backend and VRAM monitoring only for CUDA."""
    if target.hardware.backend == "cpu":
        return None, RamMonitor()
    if target.hardware.gpu_index is None:
        raise CalibrationError("CUDA calibration requires a selected GPU index")
    thresholds = VramThresholds(VRAM_RESERVE_GIB, RELEASE_TOLERANCE_GIB)
    return VramMonitor(target.hardware.gpu_index, thresholds), RamMonitor()


def _workload(mode: Mode, base_url: str, with_benchmark: bool) -> BenchmarkResult | None:
    """Run real mode load on every start and benchmark/v1 only when confirming a finalist."""
    if mode.services.vision:
        run_vision_probe(base_url)
    if with_benchmark:
        return run_benchmark(base_url)
    run_probe(base_url)
    return None


def _execute(target: CalibrationTarget, spec: TrialSpec, state: _TrialState) -> None:
    """Start monitors and the fresh server process, then exercise the mode workload."""
    if state.vram_monitor is not None:
        state.vram_monitor.start()
    state.ram_monitor.start()
    command = build_command(target.executable, spec.plan, target.lock)
    request = StartRequest(command, spec.plan, target.lock, state.spawned)
    state.running = start_service(request, spec.root)
    base_url = f"http://127.0.0.1:{spec.plan.port}"
    state.benchmark = _workload(spec.plan.mode, base_url, spec.with_benchmark)


def _finish(
    state: _TrialState, root: Path
) -> tuple[VramSummary | None, RamSummary | None, BaseException | None]:
    """Stop the managed process and finalize both monitors, preserving the first failure."""
    cleanup_error: BaseException | None = None
    vram: VramSummary | None = None
    ram: RamSummary | None = None
    try:
        if state.running is not None:
            stop_services(root)
        if state.vram_monitor is not None:
            pid = state.spawned.pid if state.running is None else state.running.process.pid
            vram = state.vram_monitor.finish(pid)
    except BaseException as error:
        cleanup_error = error
    try:
        ram = state.ram_monitor.finish()
    except BaseException as error:
        cleanup_error = cleanup_error or error
    return vram, ram, cleanup_error


def run_trial(target: CalibrationTarget, spec: TrialSpec) -> TrialMeasurement:
    """Start, exercise, stop, and verify release for one isolated v2 trial process."""
    state = _TrialState(*_monitors(target))
    failure: BaseException | None = None
    try:
        _execute(target, spec, state)
    except BaseException as error:
        failure = error
    vram, ram, cleanup_error = _finish(state, spec.root)
    if isinstance(cleanup_error, (VramEnvironmentError, RamError)):
        # Contaminated or unreliable monitoring invalidates the whole run (design §3, step 10).
        raise cleanup_error
    failure = failure or cleanup_error
    if failure is None:
        assert ram is not None
        return TrialMeasurement(state.benchmark, vram, ram)
    if not isinstance(failure, Exception) or isinstance(failure, (VramEnvironmentError, RamError)):
        raise failure
    if isinstance(failure, VramError) and failure.summary is not None:
        vram = failure.summary
    raise TrialFailure(failure, (vram, ram)) from failure
