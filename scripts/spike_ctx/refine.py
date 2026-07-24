"""Run only an evidence-triggered adjacent-context refinement."""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path

from qwen_launcher._calibration_gpu_contexts import capture_gpu_context_baseline
from qwen_launcher.calibration import CalibrationTarget, prepare_target
from scripts.spike_ctx.output import write_document, write_manifest
from scripts.spike_ctx.runner import _ensure_trial, _probe, _RunState
from scripts.spike_ctx.search import find_boundary
from scripts.spike_ctx.trial import TrialConfig

_ALLOWED_CONTEXTS = (98304, 49152)


def _measure(target: CalibrationTarget, ctx: int, state: _RunState) -> dict[str, object]:
    """Measure one refinement and build its pending-review document."""
    search = find_boundary(_probe(target, ctx, state))
    if search.boundary is not None:
        _ensure_trial(target, TrialConfig(ctx, search.boundary), state)
        _ensure_trial(target, TrialConfig(ctx, search.prudent), state)
    return {
        "schema": "cross-context-spike-refinement/v1",
        "decision": "pending-human-review",
        "ctx": ctx,
        "search": asdict(search),
        "trials": [asdict(item) for item in state.trials],
    }


def run_refinement(output_root: Path, ctx: int) -> None:
    """Measure one approved adjacent rung after initial evidence justifies it."""
    if ctx not in _ALLOWED_CONTEXTS:
        raise ValueError(f"refinement context must be one of {_ALLOWED_CONTEXTS}")
    target = prepare_target("coding")
    if target.hardware.backend != "cuda" or target.hardware.gpu_index is None:
        raise RuntimeError("the cross-context spike requires one supported CUDA GPU")
    output_root.mkdir(parents=True, exist_ok=False)
    baseline = capture_gpu_context_baseline(target.hardware.gpu_index)
    try:
        with tempfile.TemporaryDirectory(prefix="qwen-spike-ctx-refine-") as temporary:
            state = _RunState(Path(temporary), output_root, baseline)
            try:
                document = _measure(target, ctx, state)
            except BaseException as error:
                document = {
                    "schema": "cross-context-spike-refinement/v1",
                    "decision": "incomplete-run",
                    "ctx": ctx,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "trials": [asdict(item) for item in state.trials],
                }
                raise
            finally:
                write_document(output_root, document)
    finally:
        write_manifest(output_root)
