"""Run one fresh calibration/v6-lite trial and expose probe, sample, and gate providers.

This is the only v6 module that starts a real server, so it is validated on hardware rather than
offline; the ``_calibration_v6_runner`` orchestration is fake-tested. Trials apply the v6 reserves
(0.5/2.0/0.125 GiB) and reuse the calibration/v5 monitors and process lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from qwen_launcher._calibration_outcomes import ClassifiedOutcome, TrialOutcome, classify
from qwen_launcher._calibration_port import select_trial_port
from qwen_launcher._calibration_ram import RamMonitor, RamSummary
from qwen_launcher._calibration_v5_process import _prefer_cleanup_error
from qwen_launcher._calibration_v5_process_types import SpawnRecord, managed_gpu_identity
from qwen_launcher._calibration_v6_gate import run_gate
from qwen_launcher._calibration_v6_types import (
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    GateResult,
    V6Sample,
)
from qwen_launcher._calibration_vram import VramMonitor, VramSummary, VramThresholds
from qwen_launcher.benchmark import run_probe
from qwen_launcher.benchmark_quick import QuickBenchResult, run_quick_bench
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.process import (
    RunningService,
    StartRequest,
    start_service,
    stop_services,
)
from qwen_launcher.profiles import LaunchPlan, Mode


@dataclass(slots=True)
class _Session:
    """Track monitors and process identity for one running v6 trial."""

    vram: VramMonitor | None
    ram: RamMonitor
    spawned: SpawnRecord = field(default_factory=SpawnRecord)
    running: RunningService | None = None


@dataclass(frozen=True, slots=True)
class V6TrialRunner:
    """Start one fresh monitored server per probe, sample, or gate request for one mode."""

    target: CalibrationTarget
    mode: Mode
    runtime_root: Path
    driver: list[str | None] = field(default_factory=lambda: [None])

    def _plan(self, ctx: int, n_cpu_moe: int) -> LaunchPlan:
        """Build one v6 launch plan; vision disables speculative decoding (D-060)."""
        target = self.target
        return LaunchPlan(
            self.mode,
            target.config.model,
            target.model_path,
            target.mmproj_path if self.mode.services.vision else None,
            select_trial_port(target.config.llama_port),
            None,
            ctx,
            n_cpu_moe,
            target.hardware.backend,
            target.hardware.gpu_index,
            (),
            "disabled" if self.mode.services.vision else "mtp2",
        )

    def _session(self) -> _Session:
        """Create v6 reserve monitors using legacy PID contamination detection."""
        gpu_index = self.target.hardware.gpu_index
        vram = (
            VramMonitor(gpu_index, VramThresholds(VRAM_RESERVE_GIB, RELEASE_TOLERANCE_GIB))
            if gpu_index is not None
            else None
        )
        return _Session(vram, RamMonitor(minimum_free_gib=RAM_RESERVE_GIB))

    def _finish(
        self, session: _Session, root: Path
    ) -> tuple[VramSummary | None, RamSummary | None, BaseException | None]:
        """Stop the server and finalize both monitors, preferring run-invalidating evidence."""
        error: BaseException | None = None
        vram: VramSummary | None = None
        ram: RamSummary | None = None
        if session.running is not None:
            try:
                stop_services(root)
            except BaseException as caught:
                error = _prefer_cleanup_error(error, caught)
        if session.vram is not None:
            try:
                vram = session.vram.finish(managed_gpu_identity(session.running, session.spawned))
            except BaseException as caught:
                error = _prefer_cleanup_error(error, caught)
        try:
            ram = session.ram.finish()
        except BaseException as caught:
            error = _prefer_cleanup_error(error, caught)
        return vram, ram, error

    def _run(
        self, ctx: int, n_cpu_moe: int, workload
    ) -> tuple[object, VramSummary | None, RamSummary]:
        """Start a fresh server, run one workload, and finalize monitors, raising on failure."""
        session = self._session()
        root = self.runtime_root / self.mode.id / f"c{ctx}-n{n_cpu_moe}"
        failure: BaseException | None = None
        result: object = None
        try:
            if session.vram is not None:
                session.vram.start()
            session.ram.start()
            plan = self._plan(ctx, n_cpu_moe)
            command = build_v6_command(self.target, plan)
            request = StartRequest(command, plan, self.target.lock, session.spawned)
            session.running = start_service(request, root)
            result = workload(f"http://127.0.0.1:{plan.port}", plan.mode, ctx)
        except BaseException as caught:
            failure = caught
        vram, ram, cleanup = self._finish(session, root)
        if cleanup is not None:
            failure = _prefer_cleanup_error(failure, cleanup)
        if session.vram is not None and vram is not None:
            self.driver[0] = vram.driver_version
        if failure is not None:
            raise failure
        assert ram is not None
        return result, vram, ram

    def probe(self, ctx: int, n_cpu_moe: int) -> ClassifiedOutcome:
        """Run one light feasibility probe and classify its outcome by exception class."""
        try:
            self._run(ctx, n_cpu_moe, lambda url, mode, _ctx: run_probe(url))
        except Exception as error:
            return classify(error)
        return ClassifiedOutcome(TrialOutcome.SUCCESS)

    def sample(self, ctx: int, n_cpu_moe: int) -> V6Sample:
        """Measure one feasible configuration with the production quick-bench workload."""
        result, vram, ram = self._run(ctx, n_cpu_moe, lambda url, mode, _ctx: run_quick_bench(url))
        assert isinstance(result, QuickBenchResult)
        speculative = "disabled" if self.mode.services.vision else "mtp2"
        vram_needed = (
            None if vram is None else max(0.0, vram.peak_used_gib - vram.baseline_used_gib)
        )
        vram_min_free = None if vram is None else vram.minimum_free_gib
        return V6Sample(
            ctx,
            n_cpu_moe,
            speculative,
            result,
            ram.needed_gib,
            vram_needed,
            ram.minimum_available_gib,
            vram_min_free,
        )

    def gate(self, ctx: int, n_cpu_moe: int) -> GateResult:
        """Run the final per-envelope gate for this mode inside a fresh monitored process."""
        result, _vram, _ram = self._run(
            ctx, n_cpu_moe, lambda url, mode, gate_ctx: run_gate(url, mode, gate_ctx)
        )
        assert isinstance(result, GateResult)
        return result


def build_v6_command(target: CalibrationTarget, plan: LaunchPlan) -> tuple[str, ...]:
    """Build the verified server command for one v6 trial plan."""
    from qwen_launcher.engine import build_command

    return build_command(target.executable, plan, target.lock)
