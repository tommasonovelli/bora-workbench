"""Drive one opt-in calibration/v6-lite run: shared text search, vstudio search, and records.

The orchestration in ``_calibration_v6_runner`` and the record builder are fake-tested; this module
wires them to the real ``V6TrialRunner`` and writes records, so it is validated on hardware.
calibration/v5 stays the default and is untouched by this path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from qwen_launcher._calibration_record import (
    candidate_record_path,
    promote_candidate,
    write_record,
)
from qwen_launcher._calibration_record_v5 import V6RecordContext, build_record_v5
from qwen_launcher._calibration_v6_run_types import V6RunOptions, V6RunResult
from qwen_launcher._calibration_v6_runner import (
    GateTarget,
    GroupPlan,
    ModeResult,
    SearchProvider,
    run_group,
)
from qwen_launcher._calibration_v6_trial import V6TrialRunner
from qwen_launcher._calibration_v6_types import (
    CONTEXT_SCALE_V6,
    TEXT_SEARCH_BUDGET,
    VSTUDIO_SEARCH_BUDGET,
)
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.paths import data_dir
from qwen_launcher.profiles import Mode


@dataclass(frozen=True, slots=True)
class _RunSpec:
    """Group the immutable target, evidence root, context scale, and run id for one run."""

    target: CalibrationTarget
    root: Path
    contexts: tuple[int, ...]
    run_id: str


def _run_group_for(
    spec: _RunSpec, modes: tuple[Mode, ...], budget: int
) -> tuple[tuple[ModeResult, str | None], ...]:
    """Run one shared-hardware group and pair each result with the measured GPU driver."""
    runners = {mode.id: V6TrialRunner(spec.target, mode, spec.root) for mode in modes}
    search = runners[modes[0].id]
    provider = SearchProvider(search.probe, search.sample)
    targets = tuple(GateTarget(mode, runners[mode.id].gate) for mode in modes)
    results = run_group(provider, targets, GroupPlan(spec.contexts, budget))
    return tuple((result, search.driver[0]) for result in results)


def _persist(
    spec: _RunSpec, options: V6RunOptions, produced: tuple[ModeResult, str | None]
) -> Path:
    """Write one v6 candidate record and promote it unless activation was declined."""
    result, driver = produced
    context = V6RecordContext(spec.target, spec.run_id, options.preference, driver)
    document = build_record_v5(context, result)
    path = write_record(document, candidate_record_path(result.mode.id))
    return promote_candidate(result.mode.id) if options.is_activate else path


def run_calibration_v6(target: CalibrationTarget, options: V6RunOptions) -> V6RunResult:
    """Run the shared text group and each vision group, then persist per-mode v5 records."""
    run_id = uuid4().hex
    contexts = (options.target_ctx,) if options.target_ctx is not None else CONTEXT_SCALE_V6
    spec = _RunSpec(target, data_dir() / "calibration" / "evidence" / run_id, contexts, run_id)
    text_modes = tuple(mode for mode in target.modes if not mode.services.vision)
    vision_modes = tuple(mode for mode in target.modes if mode.services.vision)
    produced: list[tuple[ModeResult, str | None]] = []
    if text_modes:
        produced.extend(_run_group_for(spec, text_modes, TEXT_SEARCH_BUDGET))
    for mode in vision_modes:
        produced.extend(_run_group_for(spec, (mode,), VSTUDIO_SEARCH_BUDGET))
    paths = tuple(_persist(spec, options, item) for item in produced)
    return V6RunResult(run_id, paths, tuple(result for result, _ in produced))
