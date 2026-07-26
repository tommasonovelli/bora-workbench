"""Run one calibration trial end to end: monitored process, workload, and final gate (spec 5.6).

This is the only calibration module that starts a real server, so it is validated on hardware and
not offline; the ``_calibration_runner`` orchestration is fake-tested. One trial owns four things
that must stay together because each one decides what the others may report: the launch plan, the
monitored process lifecycle, the workload, and the D-059 classification of whatever the workload
raises. Cleanup runs even when the workload failed, and its precedence is decided in one place
(D-058). Monitors use the calibration reserves (0.5/2.0/0.125 GiB) and the run-scoped GPU context
population of D-046.

The final gate (spec 3.5) is the workload of the last trial per envelope. It fails only on invalid
responses; reserve and release violations are caught by the monitors that wrap it. Per-turn
``prompt_n``/``cache_n`` are diagnostic, never pass/fail, because a hybrid model may legitimately
reprocess context.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import httpx
import psutil

from bora_workbench._calibration_memory import (
    GpuContextBaseline,
    RamMonitor,
    RamSummary,
    VramMonitor,
    VramSummary,
    VramThresholds,
)
from bora_workbench._calibration_outcomes import ClassifiedOutcome, TrialOutcome, classify
from bora_workbench._calibration_trial_control import (
    TrialProgress,
    prefer_cleanup_error,
    select_trial_port,
)
from bora_workbench._calibration_types import (
    MAX_RETRY_PER_TRIAL,
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    VRAM_RESERVE_GIB,
    GateResult,
    Sample,
    SearchError,
    TrialInfeasibleError,
)
from bora_workbench.benchmark import (
    BenchmarkError,
    BenchmarkRetryableError,
    run_probe,
    run_vision_probe,
)
from bora_workbench.benchmark_quick import QuickBenchResult, run_quick_bench
from bora_workbench.calibration import CalibrationRunError, CalibrationTarget
from bora_workbench.engine import build_command
from bora_workbench.hardware import GpuProcessIdentity
from bora_workbench.process import RunningService, StartRequest, start_service, stop_services
from bora_workbench.profiles import LaunchPlan, Mode

TrialPoint = tuple[int, int | None]
Workload = Callable[[str, Mode, int], object]
Measurement = tuple[object, VramSummary | None, RamSummary]
JsonObject = dict[str, object]

_SMOKE_TOKENS = 48
_TURN_TOKENS = 32
_MULTI_TURN_COUNT = 4
_TIMEOUT_SECONDS = 15 * 60.0
_RATIO_SAMPLE_WORDS = 256
_SMOKE_CONTEXT_FRACTION = 0.8


@dataclass(slots=True)
class _SpawnRecord:
    """Capture child identity before health readiness can fail."""

    pid: int | None = None
    create_time: float | None = None

    def __call__(self, pid: int) -> None:
        """Record the spawned pid/create-time pair without failing process cleanup."""
        self.pid = pid
        try:
            self.create_time = psutil.Process(pid).create_time()
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            self.create_time = None


def _managed_gpu_identity(
    running: RunningService | None, spawned: _SpawnRecord
) -> GpuProcessIdentity | None:
    """Return the exact managed process instance even after normal cleanup."""
    if running is not None:
        service = running.state
        return GpuProcessIdentity(service.pid, service.create_time, None)
    if spawned.pid is None:
        return None
    return GpuProcessIdentity(spawned.pid, spawned.create_time, None)


@dataclass(frozen=True, slots=True)
class _SessionResources:
    """Group finalized monitor summaries with the highest-precedence cleanup failure."""

    vram: VramSummary | None
    ram: RamSummary | None
    error: BaseException | None


@dataclass(slots=True)
class _TrialSession:
    """Track both memory monitors and the process identity of one running trial."""

    vram: VramMonitor | None
    ram: RamMonitor
    spawned: _SpawnRecord = field(default_factory=_SpawnRecord)
    running: RunningService | None = None

    def start(self) -> None:
        """Begin fixed-interval polling before the server is spawned."""
        if self.vram is not None:
            self.vram.start()
        self.ram.start()

    def _finish_vram(
        self, error: BaseException | None
    ) -> tuple[VramSummary | None, BaseException | None]:
        """Finalize the VRAM monitor, keeping its reserve evidence ahead of the current failure."""
        if self.vram is None:
            return None, error
        try:
            return self.vram.finish(_managed_gpu_identity(self.running, self.spawned)), error
        except BaseException as caught:
            return None, prefer_cleanup_error(error, caught)

    def finish(self, root: Path) -> _SessionResources:
        """Stop the server and finalize both monitors, preferring run-invalidating evidence."""
        error: BaseException | None = None
        if self.running is not None:
            try:
                stop_services(root)
            except BaseException as caught:
                error = prefer_cleanup_error(error, caught)
        vram, error = self._finish_vram(error)
        ram: RamSummary | None = None
        try:
            ram = self.ram.finish()
        except BaseException as caught:
            error = prefer_cleanup_error(error, caught)
        return _SessionResources(vram, ram, error)


def _create_session(
    gpu_index: int | None, context_baseline: GpuContextBaseline | None
) -> _TrialSession:
    """Create the reserve monitors bound to the immutable run-scoped context population.

    A CUDA trial without that population would fall back to the per-trial legacy contract and could
    attribute another process's memory to this candidate, so it is refused (D-046).
    """
    ram = RamMonitor(minimum_free_gib=RAM_RESERVE_GIB)
    if gpu_index is None:
        return _TrialSession(None, ram)
    if context_baseline is None:
        raise CalibrationRunError("CUDA calibration requires a measured GPU context baseline")
    thresholds = VramThresholds(VRAM_RESERVE_GIB, RELEASE_TOLERANCE_GIB)
    return _TrialSession(VramMonitor(gpu_index, thresholds, context_baseline=context_baseline), ram)


def _preferred(failure: BaseException | None, cleanup: BaseException | None) -> BaseException:
    """Return the failure that must surface once workload and cleanup both produced one."""
    if cleanup is None:
        assert failure is not None
        return failure
    if failure is None:
        return cleanup
    return prefer_cleanup_error(failure, cleanup)


def _words(count: int) -> str:
    """Build one deterministic word sequence of the requested length."""
    return " ".join(f"ctx{index % 101}" for index in range(count))


def _payload(messages: list[JsonObject], max_tokens: int) -> JsonObject:
    """Build one deterministic uncached gate request."""
    return {
        "messages": messages,
        "max_tokens": max_tokens,
        "cache_prompt": False,
        "ignore_eos": True,
        "seed": 424242,
    }


def _post(client: httpx.Client, base_url: str, payload: JsonObject) -> JsonObject:
    """Submit one bounded gate request and require a JSON object response."""
    try:
        response = client.post(
            f"{base_url}/v1/chat/completions", json=payload, timeout=_TIMEOUT_SECONDS
        )
    except httpx.HTTPError as error:
        raise BenchmarkRetryableError(f"gate request failed: {error}") from error
    if response.status_code != 200:
        raise BenchmarkRetryableError(f"gate request returned HTTP {response.status_code}")
    value = response.json()
    if not isinstance(value, dict):
        raise BenchmarkError("gate response must be a JSON object")
    return cast(JsonObject, value)


def _is_valid(value: JsonObject, expected_n: int) -> bool:
    """Return whether one response finished at exactly the requested completion length."""
    try:
        choices = cast(list[JsonObject], value["choices"])
        finish_reason = choices[0]["finish_reason"]
        completion_n = int(cast(int, cast(JsonObject, value["usage"])["completion_tokens"]))
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    return finish_reason == "length" and completion_n == expected_n


def _tokens_per_word(client: httpx.Client, base_url: str) -> float:
    """Measure this model's tokens per generated word before sizing the smoke prompt.

    A word is not a token: on this vocabulary each ``ctxNN`` word costs roughly three tokens, so
    treating the 80% target as a word count overshoots the window and the server rejects the
    request outright. The ratio is measured once, from the same deterministic vocabulary, and the
    chat template overhead it also counts only makes the final prompt slightly smaller (spec 3.5).
    """
    payload = _payload([{"role": "user", "content": _words(_RATIO_SAMPLE_WORDS)}], 1)
    usage = cast(JsonObject, _post(client, base_url, payload)["usage"])
    try:
        prompt_tokens = int(cast(int, usage["prompt_tokens"]))
    except (KeyError, TypeError, ValueError) as error:
        raise BenchmarkError("gate response omitted the prompt token count") from error
    return max(1.0, prompt_tokens / _RATIO_SAMPLE_WORDS)


def _smoke_prompt(client: httpx.Client, base_url: str, ctx: int) -> str:
    """Build a deterministic prompt near 80% of the context window, measured in tokens."""
    words = int(ctx * _SMOKE_CONTEXT_FRACTION / _tokens_per_word(client, base_url))
    return _words(max(1, words))


def _smoke(client: httpx.Client, base_url: str, ctx: int) -> bool:
    """Run one near-full-context smoke request and require a valid bounded completion."""
    messages = [{"role": "user", "content": _smoke_prompt(client, base_url, ctx)}]
    return _is_valid(_post(client, base_url, _payload(messages, _SMOKE_TOKENS)), _SMOKE_TOKENS)


def _multi_turn(client: httpx.Client, base_url: str) -> bool:
    """Run four append-only turns and require every turn to finish validly (spec 3.5)."""
    messages: list[JsonObject] = []
    for index in range(_MULTI_TURN_COUNT):
        messages.append({"role": "user", "content": f"Turn {index}: continua la conversazione."})
        value = _post(client, base_url, _payload(messages, _TURN_TOKENS))
        if not _is_valid(value, _TURN_TOKENS):
            return False
        content = cast(JsonObject, cast(list[JsonObject], value["choices"])[0]["message"])
        messages.append({"role": "assistant", "content": str(content["content"])})
    return True


def _vision(client: httpx.Client, base_url: str) -> bool:
    """Run the pinned red-image request and require its verified answer for vstudio."""
    try:
        run_vision_probe(base_url, client)
    except BenchmarkError:
        return False
    return True


def run_gate(base_url: str, mode: Mode, ctx: int, client: httpx.Client | None = None) -> GateResult:
    """Run smoke, multi-turn, and (for vision) the pinned image gate for one envelope."""
    selected = httpx.Client() if client is None else client
    try:
        smoke = _smoke(selected, base_url, ctx)
        multi_turn = _multi_turn(selected, base_url)
        vision = _vision(selected, base_url) if mode.services.vision else None
    finally:
        if selected is not client:
            selected.close()
    return GateResult(smoke, multi_turn, vision)


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
        session = _create_session(self.target.hardware.gpu_index, self.context_baseline)
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
