"""Drive one calibration run: shared text search, vstudio search, evidence, and records.

The orchestration in ``_calibration_runner`` and the record builder are fake-tested; this module
wires them to the real ``TrialRunner``, retains the evidence tree, and writes records, so it is
validated on hardware. It owns the two run-scoped decisions the trials must share: the context scale
for the detected backend and the immutable GPU context population required by D-046.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from bora_workbench._calibration_memory import (
    GpuContextBaseline,
    VramEnvironmentError,
    capture_gpu_context_baseline,
)
from bora_workbench._calibration_record import (
    RecordContext,
    build_record,
    candidate_record_path,
    preserve_evidence,
    promote_candidate,
    write_record,
)
from bora_workbench._calibration_runner import GateTarget, ModeResult, run_group
from bora_workbench._calibration_search import GroupPlan, SearchProvider
from bora_workbench._calibration_trial import TrialRunner
from bora_workbench._calibration_trial_control import ProgressCallback, TrialProgress
from bora_workbench._calibration_types import (
    DEFAULT_PREFERENCE,
    MEASURABLE_CONTEXT_SCALE,
    MIN_CTX_QUICK_BENCH,
    TEXT_SEARCH_BUDGET,
    VSTUDIO_SEARCH_BUDGET,
    Preference,
    SearchError,
)
from bora_workbench.calibration import CalibrationRunError, CalibrationTarget
from bora_workbench.paths import data_dir
from bora_workbench.profiles import Mode


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Group the optional controls without burdening the zero-input default path."""

    preference: Preference = DEFAULT_PREFERENCE
    target_ctx: int | None = None
    is_activate: bool = True
    progress: ProgressCallback | None = None


@dataclass(frozen=True, slots=True)
class RunResult:
    """Identify the evidence run, the written record paths, and any group that did not finish.

    ``failures`` is non-empty only for a partial run: the modes it names produced no record, while
    every mode in ``mode_results`` was measured and gated completely.
    """

    evidence_run_id: str
    record_paths: tuple[Path, ...]
    mode_results: tuple[ModeResult, ...]
    evidence_path: Path
    failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _RunSpec:
    """Group the immutable target, runtime root, search preference, and identity for one run."""

    target: CalibrationTarget
    runtime_root: Path
    contexts: tuple[int, ...]
    run_id: str
    context_baseline: GpuContextBaseline | None
    progress: TrialProgress
    preference: Preference = DEFAULT_PREFERENCE


def _capture_context_baseline(target: CalibrationTarget) -> GpuContextBaseline | None:
    """Fail fast before process work when CUDA context identities cannot be trusted (D-046)."""
    if target.hardware.backend == "cpu":
        return None
    if target.hardware.gpu_index is None:
        raise CalibrationRunError("CUDA calibration requires a selected GPU index")
    try:
        return capture_gpu_context_baseline(target.hardware.gpu_index)
    except VramEnvironmentError as error:
        raise CalibrationRunError(f"calibration run invalidated: {error}") from error


def _contexts(target: CalibrationTarget, options: RunOptions) -> tuple[int, ...]:
    """Choose the searched contexts: an explicit target, the measurable scale, or one CPU context.

    The ladder stops at the smallest step the pinned quick-bench request fits in, because a step
    below it can only spend trials on a request the engine must refuse (D-071). CPU confirms that
    same single step instead of scanning, because that backend has no offload axis and the spec
    forbids inventing one (spec 5.6).
    """
    if options.target_ctx is not None:
        return (options.target_ctx,)
    if target.hardware.backend == "cpu":
        return (MIN_CTX_QUICK_BENCH,)
    return MEASURABLE_CONTEXT_SCALE


def _run_group_for(
    spec: _RunSpec, modes: tuple[Mode, ...], budget: int
) -> tuple[tuple[ModeResult, str | None], ...]:
    """Run one shared-hardware group and pair each result with the measured GPU driver."""
    runners = {
        mode.id: TrialRunner(
            spec.target, mode, spec.runtime_root, spec.context_baseline, spec.progress
        )
        for mode in modes
    }
    search = runners[modes[0].id]
    provider = SearchProvider(search.probe, search.sample, search.confirm)
    targets = tuple(GateTarget(mode, runners[mode.id].gate) for mode in modes)
    has_offload_axis = spec.target.hardware.backend != "cpu"
    plan = GroupPlan(
        spec.contexts,
        budget,
        has_offload_axis,
        spec.progress,
        preference=spec.preference,
    )
    results = run_group(provider, targets, plan)
    return tuple((result, search.driver) for result in results)


def _persist(spec: _RunSpec, options: RunOptions, produced: tuple[ModeResult, str | None]) -> Path:
    """Write one candidate record and promote it unless activation was declined."""
    result, driver = produced
    context = RecordContext(spec.target, spec.run_id, driver)
    document = build_record(context, result)
    path = write_record(document, candidate_record_path(result.mode.id))
    return promote_candidate(result.mode.id) if options.is_activate else path


def _groups(target: CalibrationTarget) -> tuple[tuple[tuple[Mode, ...], int], ...]:
    """Split the selected modes into the independent groups one run measures, with their budgets."""
    text_modes = tuple(mode for mode in target.modes if not mode.services.vision)
    groups = [(text_modes, TEXT_SEARCH_BUDGET)] if text_modes else []
    groups.extend(((mode,), VSTUDIO_SEARCH_BUDGET) for mode in target.modes if mode.services.vision)
    return tuple(groups)


def _measure(spec: _RunSpec) -> tuple[list[tuple[ModeResult, str | None]], tuple[str, ...]]:
    """Measure every independent group, keeping the results of the ones that completed.

    Groups do not share a decision, only hardware, and a run costs hours: a group whose memory
    boundary moved must not discard the modes that already finished (D-067).
    """
    produced: list[tuple[ModeResult, str | None]] = []
    failures: list[str] = []
    for modes, budget in _groups(spec.target):
        label = "+".join(mode.id for mode in modes)
        try:
            produced.extend(_run_group_for(spec, modes, budget))
        except SearchError as error:
            failures.append(f"{label}: {error}")
    return produced, tuple(failures)


def run_calibration(target: CalibrationTarget, options: RunOptions) -> RunResult:
    """Search, retain evidence, and persist one record per selected mode."""
    run_id = uuid4().hex
    root = data_dir() / "calibration"
    runtime_root = root / f".runtime-{run_id}"
    runtime_root.mkdir(parents=True, exist_ok=False)
    spec = _RunSpec(
        target,
        runtime_root,
        _contexts(target, options),
        run_id,
        _capture_context_baseline(target),
        TrialProgress(options.progress),
        options.preference,
    )
    try:
        produced, failures = _measure(spec)
    except BaseException as error:
        try:
            if runtime_root.exists():
                preserve_evidence(root, runtime_root, run_id)
        except BaseException as cleanup:
            if not isinstance(error, Exception):
                raise error from cleanup
            raise
        raise
    evidence_path = preserve_evidence(root, runtime_root, run_id)
    if not produced:
        raise SearchError("; ".join(failures) or "no mode produced a usable result")
    paths = tuple(_persist(spec, options, item) for item in produced)
    results = tuple(result for result, _ in produced)
    return RunResult(run_id, paths, results, evidence_path, failures)
