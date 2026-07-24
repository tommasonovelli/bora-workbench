"""Offline tests for calibration/v6-lite group orchestration over fake trial providers."""

from __future__ import annotations

import pytest

from qwen_launcher._calibration_outcomes import ClassifiedOutcome, TrialOutcome
from qwen_launcher._calibration_v6_runner import (
    GateTarget,
    GroupPlan,
    SearchProvider,
    run_group,
)
from qwen_launcher._calibration_v6_types import GateResult, V6SearchError
from qwen_launcher.profiles import load_catalog
from tests.v6_fixtures import sample

_VRAM = ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram")
_SUCCESS = ClassifiedOutcome(TrialOutcome.SUCCESS)
_E2E = {131072: 200.0, 65536: 100.0, 32768: 105.0}
_BOUNDARY = {131072: 37, 65536: 30, 32768: 20}
_CONTEXTS = (131072, 65536, 32768)


def _mode(mode_id: str):
    """Return one packaged mode for a gate target."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    return mode


def _provider() -> SearchProvider:
    """Build a shared provider whose feasibility and latency depend only on the context."""

    def probe_at(ctx: int, n_cpu_moe: int) -> ClassifiedOutcome:
        return _SUCCESS if n_cpu_moe >= _BOUNDARY[ctx] else _VRAM

    def sample_at(ctx: int, n_cpu_moe: int):
        return sample(ctx, n_cpu_moe, _E2E[ctx])

    return SearchProvider(probe_at, sample_at)


def _pass_gate(ctx: int, n_cpu_moe: int) -> GateResult:
    """Pass every gate stage."""
    return GateResult(True, True, None)


def test_shared_search_yields_identical_hardware_for_coding_and_studio() -> None:
    """Run one hardware search and give coding and studio identical envelopes, distinct policies."""
    targets = (GateTarget(_mode("coding"), _pass_gate), GateTarget(_mode("studio"), _pass_gate))
    coding, studio = run_group(_provider(), targets, GroupPlan(_CONTEXTS, 24))
    assert coding.mode.id == "coding"
    assert studio.mode.id == "studio"
    for preference in ("fast", "balanced", "max_context"):
        left = coding.envelopes[preference].sample
        right = studio.envelopes[preference].sample
        assert (left.ctx, left.n_cpu_moe) == (right.ctx, right.n_cpu_moe)
    assert coding.envelopes["balanced"].sample.ctx == 65536
    assert coding.envelopes["max_context"].sample.ctx == 131072


def test_gate_failure_retries_next_candidate_then_errors() -> None:
    """Use the next candidate once when a gate fails, then fail the mode when both fail."""
    failing_context = 65536

    def gate_only_prudent(ctx: int, n_cpu_moe: int) -> GateResult:
        passed = not (ctx == failing_context and n_cpu_moe == 41)
        return GateResult(passed, passed, None)

    (result,) = run_group(
        _provider(), (GateTarget(_mode("coding"), gate_only_prudent),), GroupPlan(_CONTEXTS, 24)
    )
    assert result.envelopes["fast"].sample.n_cpu_moe != 41

    def gate_never(ctx: int, n_cpu_moe: int) -> GateResult:
        return GateResult(False, False, None)

    with pytest.raises(V6SearchError, match="final gate"):
        run_group(_provider(), (GateTarget(_mode("coding"), gate_never),), GroupPlan(_CONTEXTS, 24))
