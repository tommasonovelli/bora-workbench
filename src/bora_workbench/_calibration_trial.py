"""Run one fresh calibration trial and expose probe, sample, and gate providers.

This is the only calibration module that starts a real server, so it is validated on hardware and
not offline; the ``_calibration_runner`` orchestration is fake-tested. Monitors and the process
lifecycle live in ``_calibration_session``; this module owns the launch plan, the workload, and
the D-059 classification of whatever the workload raises.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from bora_workbench._calibration_gate import run_gate
from bora_workbench._calibration_memory import GpuContextBaseline, RamSummary, VramSummary
from bora_workbench._calibration_outcomes import ClassifiedOutcome, TrialOutcome, classify
from bora_workbench._calibration_session import create_session
from bora_workbench._calibration_trial_control import (
    TrialProgress,
    prefer_cleanup_error,
    select_trial_port,
)
from bora_workbench._calibration_types import (
    MAX_RETRY_PER_TRIAL,
    GateResult,
    Sample,
    SearchError,
    TrialInfeasibleError,
)
from bora_workbench.benchmark import run_probe
from bora_workbench.benchmark_quick import QuickBenchResult, run_quick_bench
from bora_workbench.calibration import CalibrationTarget
from bora_workbench.engine import build_command
from bora_workbench.process import StartRequest, start_service
from bora_workbench.profiles import LaunchPlan, Mode

TrialPoint = tuple[int, int | None]
Workload = Callable[[str, Mode, int], object]
Measurement = tuple[object, VramSummary | None, RamSummary]


@dataclass(slots=True)
class TrialRunner:
    """Start one fresh monitored server per probe, sample, or gate request for one mode.

    ``driver`` is the only mutable state: the recorded GPU driver version is known solely from a
    finalized VRAM monitor, so the last trial that produced one reports it to the record builder.
    """

    target: CalibrationTarget
    mode: Mode
    runtime_root: Path
    context_baseline: GpuContextBaseline | None = None
    progress: TrialProgress = field(default_factory=TrialProgress)
    driver: str | None = None

    def _plan(self, point: TrialPoint) -> LaunchPlan:
        """Build one trial launch plan; vision disables speculative decoding (D-060).

        CPU launches carry no ``n_cpu_moe`` because that backend has no offload axis (spec 5.6).
        """
        ctx, n_cpu_moe = point
        target = self.target
        return LaunchPlan(
            self.mode,
            target.config.model,
            target.model_path,
            target.mmproj_path if self.mode.services.vision else None,
            select_trial_port(target.config.llama_port),
            None,
            ctx,
            None if target.hardware.backend == "cpu" else n_cpu_moe,
            target.hardware.backend,
            target.hardware.gpu_index,
            (),
            "disabled" if self.mode.services.vision else "mtp2",
        )

    def _run(self, point: TrialPoint, workload: Workload) -> Measurement:
        """Start a fresh server, run one workload, and finalize monitors, raising on failure."""
        ctx, n_cpu_moe = point
        session = create_session(self.target.hardware.gpu_index, self.context_baseline)
        root = self.runtime_root / self.mode.id / f"c{ctx}-n{n_cpu_moe}"
        failure: BaseException | None = None
        result: object = None
        self.progress.started()
        try:
            session.start()
            plan = self._plan(point)
            command = build_command(self.target.executable, plan, self.target.lock)
            request = StartRequest(command, plan, self.target.lock, session.spawned)
            session.running = start_service(request, root)
            result = workload(f"http://127.0.0.1:{plan.port}", plan.mode, ctx)
        except BaseException as caught:
            failure = caught
        resources = session.finish(root)
        self.progress.finished()
        if resources.vram is not None:
            self.driver = resources.vram.driver_version
        if resources.error is not None or failure is not None:
            raise _preferred(failure, resources.error)
        assert resources.ram is not None
        return result, resources.vram, resources.ram

    def _attempt(self, point: TrialPoint, workload: Workload) -> Measurement:
        """Run one measured workload, retrying once on a classified retryable failure (D-059)."""
        for _ in range(MAX_RETRY_PER_TRIAL + 1):
            try:
                return self._run(point, workload)
            except Exception as error:
                outcome = classify(error)
                if outcome.outcome is TrialOutcome.MEMORY_INFEASIBLE:
                    message = f"{point} is no longer feasible: {error}"
                    raise TrialInfeasibleError(message) from error
                if outcome.outcome is not TrialOutcome.RETRYABLE:
                    raise SearchError(f"{point} produced invalid evidence: {error}") from error
        raise SearchError(f"{point} remained retryable after one retry")

    def probe(self, ctx: int, n_cpu_moe: int | None) -> ClassifiedOutcome:
        """Run one light feasibility probe and classify its outcome by exception class."""
        try:
            self._run((ctx, n_cpu_moe), lambda url, _mode, _ctx: run_probe(url))
        except Exception as error:
            return classify(error)
        return ClassifiedOutcome(TrialOutcome.SUCCESS)

    def sample(self, ctx: int, n_cpu_moe: int | None) -> Sample:
        """Measure one feasible configuration with the production quick-bench workload."""
        point = (ctx, n_cpu_moe)
        result, vram, ram = self._attempt(point, lambda url, _mode, _ctx: run_quick_bench(url))
        assert isinstance(result, QuickBenchResult)
        vram_needed = (
            None if vram is None else max(0.0, vram.peak_used_gib - vram.baseline_used_gib)
        )
        return Sample(
            ctx,
            n_cpu_moe,
            "disabled" if self.mode.services.vision else "mtp2",
            result,
            ram.needed_gib,
            vram_needed,
            ram.minimum_available_gib,
            None if vram is None else vram.minimum_free_gib,
        )

    def gate(self, ctx: int, n_cpu_moe: int | None) -> GateResult:
        """Run the final per-envelope gate for this mode inside a fresh monitored process."""
        result, _vram, _ram = self._attempt((ctx, n_cpu_moe), run_gate)
        assert isinstance(result, GateResult)
        return result


def _preferred(failure: BaseException | None, cleanup: BaseException | None) -> BaseException:
    """Return the failure that must surface once workload and cleanup both produced one."""
    if cleanup is None:
        assert failure is not None
        return failure
    if failure is None:
        return cleanup
    return prefer_cleanup_error(failure, cleanup)
