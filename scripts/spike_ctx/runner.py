"""Orchestrate the maintainer-run cross-context decision package."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from qwen_launcher._calibration_gpu_contexts import (
    GpuContextBaseline,
    capture_gpu_context_baseline,
)
from qwen_launcher.calibration import CalibrationTarget, prepare_target
from scripts.spike_ctx.models import SearchResult, TrialResult
from scripts.spike_ctx.output import (
    incomplete_document,
    successful_document,
    write_document,
    write_manifest,
)
from scripts.spike_ctx.search import find_boundary
from scripts.spike_ctx.trial import (
    SpikeTrialFailure,
    TrialConfig,
    TrialRequest,
    TrialRuntime,
    execute_quick,
    execute_reasoning,
)

_CONTEXTS = (131072, 65536, 32768)


@dataclass(slots=True)
class _RunState:
    """Track roots, baseline, trial numbering, and complete successful measurements."""

    runtime_root: Path
    output_root: Path
    baseline: GpuContextBaseline
    sequence: int = 0
    trials: list[TrialResult] = field(default_factory=list)


def _copy_logs(root: Path, destination: Path) -> None:
    """Preserve process logs for later private diagnosis and manual redaction."""
    logs = tuple(root.glob("logs/*.log"))
    if not logs:
        return
    destination.mkdir(parents=True, exist_ok=True)
    for log in logs:
        shutil.copy2(log, destination / log.name)


def _trial(target: CalibrationTarget, config: TrialConfig, state: _RunState) -> TrialResult:
    """Execute one uniquely rooted trial and retain success plus failure logs."""
    state.sequence += 1
    label = f"trial-{state.sequence:02d}-ctx{config.ctx}-n{config.n_cpu_moe}-{config.speculative}"
    process_root = state.runtime_root / label
    runtime = TrialRuntime(process_root, state.output_root / "responses" / label, state.baseline)
    try:
        result = execute_quick(TrialRequest(target, config, runtime))
        state.trials.append(result)
        return result
    finally:
        _copy_logs(process_root, state.output_root / "logs" / label)


def _probe(target: CalibrationTarget, ctx: int, state: _RunState):
    """Build a search callback returning original class-defined trial failures."""

    def measure(value: int) -> BaseException | None:
        """Run one full quick measurement as a feasibility decision point."""
        try:
            _trial(target, TrialConfig(ctx, value), state)
        except SpikeTrialFailure as failure:
            return failure.error
        return None

    return measure


def _find_searches(target: CalibrationTarget, state: _RunState) -> dict[int, SearchResult]:
    """Measure the two unknown context boundaries with six binary decisions each."""
    return {ctx: find_boundary(_probe(target, ctx, state)) for ctx in _CONTEXTS[1:]}


def _has_trial(state: _RunState, config: TrialConfig) -> bool:
    """Return whether an equivalent quick measurement already completed."""
    return any(
        item.ctx == config.ctx
        and item.n_cpu_moe == config.n_cpu_moe
        and item.speculative == config.speculative
        for item in state.trials
    )


def _ensure_trial(target: CalibrationTarget, config: TrialConfig, state: _RunState) -> None:
    """Measure a required boundary or prudent point unless search already did so."""
    if not _has_trial(state, config):
        _trial(target, config, state)


def _measure_required(
    target: CalibrationTarget, searches: dict[int, SearchResult], state: _RunState
) -> None:
    """Complete the six core configurations and the two MTP-off appendix trials."""
    for value in (37, 41):
        _ensure_trial(target, TrialConfig(131072, value), state)
    for ctx, search in searches.items():
        if search.boundary is None:
            continue
        _ensure_trial(target, TrialConfig(ctx, search.boundary), state)
        _ensure_trial(target, TrialConfig(ctx, search.prudent), state)
    _ensure_trial(target, TrialConfig(131072, 37, "disabled"), state)
    boundary_65k = searches[65536].boundary
    if boundary_65k is not None:
        _ensure_trial(target, TrialConfig(65536, boundary_65k, "disabled"), state)


def _reasoning(target: CalibrationTarget, boundary: int, state: _RunState) -> str:
    """Try reasoning off alone, then the verified zero budget only if needed."""
    for needs_budget in (False, True):
        state.sequence += 1
        label = f"reasoning-ctx32768-n{boundary}-budget{int(needs_budget)}"
        runtime = TrialRuntime(
            state.runtime_root / label,
            state.output_root / "responses" / label,
            state.baseline,
        )
        config = TrialConfig(32768, boundary, reasoning="off", reasoning_budget_zero=needs_budget)
        try:
            execute_reasoning(TrialRequest(target, config, runtime))
            return "reasoning-off-plus-budget-0" if needs_budget else "reasoning-off"
        except SpikeTrialFailure as failure:
            if "<think>" not in str(failure.error) or needs_budget:
                raise
        finally:
            _copy_logs(runtime.process_root, state.output_root / "logs" / label)
    raise RuntimeError("reasoning check did not produce a result")


def run_real(output_root: Path) -> None:
    """Run the real CUDA package while leaving the GO/NO-GO verdict to the maintainer."""
    target = prepare_target("coding")
    if target.hardware.backend != "cuda" or target.hardware.gpu_index is None:
        raise RuntimeError("the cross-context spike requires one supported CUDA GPU")
    output_root.mkdir(parents=True, exist_ok=False)
    baseline = capture_gpu_context_baseline(target.hardware.gpu_index)
    try:
        with tempfile.TemporaryDirectory(prefix="qwen-spike-ctx-") as temporary:
            state = _RunState(Path(temporary), output_root, baseline)
            try:
                searches = _find_searches(target, state)
                _measure_required(target, searches, state)
                boundary = searches[32768].boundary
                reasoning = None if boundary is None else _reasoning(target, boundary, state)
                document = successful_document(searches, state.trials, reasoning)
            except BaseException as error:
                document = incomplete_document(error, state.trials)
                raise
            finally:
                write_document(output_root, document)
    finally:
        write_manifest(output_root)
