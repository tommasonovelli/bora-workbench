"""Run one fresh spike process through production command and lifecycle primitives."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast

from qwen_launcher._calibration_gpu_contexts import GpuContextBaseline
from qwen_launcher._calibration_port import select_trial_port
from qwen_launcher._calibration_ram import RamMonitor, RamSummary
from qwen_launcher._calibration_v5_process import _prefer_cleanup_error
from qwen_launcher._calibration_v5_process_types import SpawnRecord, managed_gpu_identity
from qwen_launcher._calibration_vram import VramMonitor, VramSummary, VramThresholds
from qwen_launcher.benchmark import BenchmarkRetryableError
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.engine import build_command
from qwen_launcher.process import (
    ProcessError,
    RunningService,
    StartRequest,
    start_service,
    stop_services,
)
from qwen_launcher.profiles import LaunchPlan
from scripts.spike_ctx.models import QuickResult, RequestMetric, TrialResult
from scripts.spike_ctx.quick import QuickRequest, run_quick, run_reasoning


@dataclass(frozen=True, slots=True)
class TrialConfig:
    """Describe one cross-context process configuration."""

    ctx: int
    n_cpu_moe: int
    speculative: Literal["mtp2", "disabled"] = "mtp2"
    reasoning: Literal["on", "off"] | None = None
    reasoning_budget_zero: bool = False


@dataclass(frozen=True, slots=True)
class TrialRuntime:
    """Group isolated process, response, and GPU-context roots."""

    process_root: Path
    response_root: Path
    gpu_context_baseline: GpuContextBaseline


@dataclass(frozen=True, slots=True)
class TrialRequest:
    """Group target, candidate, and runtime to keep trial APIs narrow."""

    target: CalibrationTarget
    config: TrialConfig
    runtime: TrialRuntime


@dataclass(slots=True)
class _Session:
    """Track process identity and resource monitors through cleanup."""

    vram: VramMonitor
    ram: RamMonitor
    spawned: SpawnRecord
    running: RunningService | None = None


class SpikeTrialFailure(RuntimeError):
    """Retain the class-defined cause of one failed spike candidate."""

    def __init__(self, error: Exception) -> None:
        """Expose the original failure to the outcome classifier."""
        super().__init__(str(error))
        self.error = error


def _plan(request: TrialRequest) -> LaunchPlan:
    """Build a coding plan with only spike-authorized variable fields."""
    target = request.target
    mode = target.modes[0]
    if request.config.reasoning is not None:
        mode = replace(mode, sampling=replace(mode.sampling, reasoning=request.config.reasoning))
    return LaunchPlan(
        mode,
        target.config.model,
        target.model_path,
        None,
        select_trial_port(target.config.llama_port),
        None,
        request.config.ctx,
        request.config.n_cpu_moe,
        "cuda",
        target.hardware.gpu_index,
        (),
        request.config.speculative,
    )


def _command(request: TrialRequest, plan: LaunchPlan) -> tuple[str, ...]:
    """Use the production builder and append only the verified budget flag when requested."""
    command = build_command(request.target.executable, plan, request.target.lock)
    if not request.config.reasoning_budget_zero:
        return command
    flag = "--reasoning-budget"
    if flag not in cast(list[str], request.target.lock["verified_flags"]):
        raise BenchmarkRetryableError("reasoning budget is absent from verified_flags")
    return (*command, flag, "0")


def _session(request: TrialRequest) -> _Session:
    """Create spike-specific 0.5/2.0/0.125 resource monitors."""
    target = request.target
    if target.hardware.gpu_index is None:
        raise BenchmarkRetryableError("cross-context spike requires one selected CUDA GPU")
    thresholds = VramThresholds(0.5, 0.125)
    vram = VramMonitor(
        target.hardware.gpu_index,
        thresholds,
        context_baseline=request.runtime.gpu_context_baseline,
    )
    return _Session(vram, RamMonitor(minimum_free_gib=2.0), SpawnRecord())


def _finish(
    session: _Session, root: Path
) -> tuple[VramSummary | None, RamSummary | None, BaseException | None]:
    """Stop the server and prefer run-invalidating monitor evidence."""
    error: BaseException | None = None
    try:
        if session.running is not None:
            stop_services(root)
    except BaseException as caught:
        error = _prefer_cleanup_error(error, caught)
    vram: VramSummary | None = None
    ram: RamSummary | None = None
    for monitor, identity in (
        (session.vram, managed_gpu_identity(session.running, session.spawned)),
        (session.ram, None),
    ):
        try:
            summary = (
                monitor.finish(identity) if isinstance(monitor, VramMonitor) else monitor.finish()
            )
            if isinstance(summary, VramSummary):
                vram = summary
            else:
                ram = summary
        except BaseException as caught:
            error = _prefer_cleanup_error(error, caught)
    return vram, ram, error


def _run(request: TrialRequest, is_reasoning: bool) -> tuple[object, VramSummary, RamSummary]:
    """Execute one workload and always complete both resource monitors."""
    session = _session(request)
    failure: BaseException | None = None
    result: object = None
    try:
        session.vram.start()
        session.ram.start()
        plan = _plan(request)
        start = StartRequest(_command(request, plan), plan, request.target.lock, session.spawned)
        session.running = start_service(start, request.runtime.process_root)
        base_url = f"http://127.0.0.1:{plan.port}"
        quick_request = QuickRequest(base_url, request.runtime.response_root)
        result = run_reasoning(quick_request) if is_reasoning else run_quick(quick_request)
    except BaseException as caught:
        failure = (
            BenchmarkRetryableError(str(caught)) if isinstance(caught, ProcessError) else caught
        )
    vram, ram, cleanup = _finish(session, request.runtime.process_root)
    if cleanup is not None:
        failure = _prefer_cleanup_error(failure, cleanup)
    if failure is not None:
        if not isinstance(failure, Exception):
            raise failure
        raise SpikeTrialFailure(failure) from failure
    assert vram is not None and ram is not None
    return result, vram, ram


def execute_quick(request: TrialRequest) -> TrialResult:
    """Return one complete quick-bench and its minimum resource observations."""
    result, vram, ram = _run(request, False)
    return TrialResult(
        request.config.ctx,
        request.config.n_cpu_moe,
        request.config.speculative,
        cast(QuickResult, result),
        ram.minimum_available_gib,
        vram.minimum_free_gib,
    )


def execute_reasoning(request: TrialRequest) -> tuple[RequestMetric, RequestMetric, RequestMetric]:
    """Return three valid reasoning-off measurements from one fresh process."""
    result, _vram, _ram = _run(request, True)
    return cast(tuple[RequestMetric, RequestMetric, RequestMetric], result)
