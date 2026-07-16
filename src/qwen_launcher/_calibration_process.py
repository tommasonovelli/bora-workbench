"""Run one isolated calibration process with mode workload and aggregate VRAM evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_vram import VramError, VramMonitor, VramSummary
from qwen_launcher.benchmark import BenchmarkResult, run_benchmark, run_probe, run_vision_probe
from qwen_launcher.calibration import CalibrationError, CalibrationSettings, CalibrationTarget
from qwen_launcher.engine import build_command
from qwen_launcher.process import RunningService, StartRequest, start_service, stop_services
from qwen_launcher.profiles import LaunchPlan, Mode


class StartFailure(RuntimeError):
    """Retain measurable VRAM evidence when one candidate start must be discarded."""

    def __init__(self, error: Exception, vram: VramSummary | None) -> None:
        """Keep the original expected failure and any completed monitor summary."""
        super().__init__(str(error))
        self.error = error
        self.vram = vram


@dataclass(slots=True)
class _SpawnRecord:
    """Capture child identity before health readiness can fail."""

    pid: int | None = None

    def __call__(self, pid: int) -> None:
        """Record the exact PID reported immediately after shell-free spawn."""
        self.pid = pid


@dataclass(frozen=True, slots=True)
class StartSpec:
    """Group one candidate launch plan, isolated root, and benchmark position."""

    plan: LaunchPlan
    root: Path
    is_final: bool


def _monitor(target: CalibrationTarget, settings: CalibrationSettings) -> VramMonitor | None:
    """Create aggregate monitoring only for CUDA, using the explicit reserve."""
    if target.hardware.backend == "cpu":
        return None
    if target.hardware.gpu_index is None or settings.minimum_free_vram_gib is None:
        raise CalibrationError("CUDA calibration requires selected GPU and explicit VRAM reserve")
    return VramMonitor(target.hardware.gpu_index, settings.minimum_free_vram_gib)


def _workload(mode: Mode, base_url: str, is_final: bool) -> BenchmarkResult | None:
    """Run real mode load on every start and benchmark/v1 on the final stable start."""
    if mode.services.vision:
        run_vision_probe(base_url)
    if is_final:
        return run_benchmark(base_url)
    run_probe(base_url)
    return None


def _finish_monitor(
    monitor: VramMonitor | None, running: RunningService | None, spawned_pid: int | None
) -> VramSummary | None:
    """Finalize aggregate evidence after cleanup using the exact managed child PID."""
    if monitor is None:
        return None
    pid = spawned_pid if running is None else running.process.pid
    return monitor.finish(pid)


def run_start(
    target: CalibrationTarget, settings: CalibrationSettings, spec: StartSpec
) -> tuple[BenchmarkResult | None, VramSummary | None]:
    """Start, exercise, stop, and verify release for one isolated candidate process."""
    monitor = _monitor(target, settings)
    running: RunningService | None = None
    spawned = _SpawnRecord()
    workload_error: BaseException | None = None
    try:
        if monitor is not None:
            monitor.start()
        command = build_command(target.executable, spec.plan, target.lock)
        request = StartRequest(command, spec.plan, target.lock, spawned)
        running = start_service(request, spec.root)
        base_url = f"http://127.0.0.1:{spec.plan.port}"
        benchmark = _workload(spec.plan.mode, base_url, spec.is_final)
    except BaseException as error:
        workload_error = error
        benchmark = None
    try:
        if running is not None:
            stop_services(spec.root)
        vram = _finish_monitor(monitor, running, spawned.pid)
    except BaseException as cleanup_error:
        if workload_error is None:
            workload_error = cleanup_error
        vram = None
    if isinstance(workload_error, (KeyboardInterrupt, SystemExit)):
        raise workload_error
    if isinstance(workload_error, Exception):
        attached = vram
        if isinstance(workload_error, VramError) and workload_error.summary is not None:
            attached = workload_error.summary
        raise StartFailure(workload_error, attached) from workload_error
    return benchmark, vram
