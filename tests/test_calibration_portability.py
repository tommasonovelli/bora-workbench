"""Calibration input safeguards that prevent host-specific candidate comparisons."""

from __future__ import annotations

import pytest

from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationSettings,
    Candidate,
    validate_settings,
)
from qwen_launcher.validation import validate_resources
from tests.calibration_fixtures import valid_policy
from tests.content_fixtures import copy_resource_root, write_json


def _cuda_settings(candidates: tuple[Candidate, ...]) -> CalibrationSettings:
    """Build complete CUDA settings around one candidate sequence."""
    return CalibrationSettings(candidates, 2, 0.5, 0.125)


def test_one_run_never_compares_different_context_targets() -> None:
    """Keep context a fixed product target instead of rewarding a smaller context for speed."""
    candidates = (Candidate("large", 131072, 48), Candidate("small", 8192, 47))

    with pytest.raises(CalibrationError, match="same context"):
        validate_settings(_cuda_settings(candidates), "cuda")


def test_cuda_search_order_is_prudent_and_each_envelope_is_unique() -> None:
    """Require descending unique CPU offload values without assuming memory monotonicity."""
    reversed_candidates = (Candidate("aggressive", 8192, 37), Candidate("safe", 8192, 48))
    duplicate_candidates = (Candidate("first", 8192, 48), Candidate("second", 8192, 48))

    with pytest.raises(CalibrationError, match="prudent to aggressive"):
        validate_settings(_cuda_settings(reversed_candidates), "cuda")
    with pytest.raises(CalibrationError, match="unique n_cpu_moe"):
        validate_settings(_cuda_settings(duplicate_candidates), "cuda")


def test_packaged_policy_obeys_the_same_search_invariants(tmp_path) -> None:
    """Apply fixed-context and prudent-order rules to contributed policy data too."""
    root = copy_resource_root(tmp_path)
    policy = valid_policy()
    candidates = policy["policies"][0]["modes"]["coding"]["candidates"]  # type: ignore[index]
    candidates.append({"id": "mixed", "ctx": 16384, "n_cpu_moe": 49})
    write_json(root / "content/calibration-policy.json", policy)

    messages = {issue.message for issue in validate_resources(root).errors}

    assert "must use one fixed context" in messages
    assert "must be ordered from prudent to aggressive" in messages


def test_cpu_does_not_claim_optimization_without_a_tuning_axis() -> None:
    """Reject duplicate fixed-context CPU envelopes that differ only by their labels."""
    candidates = (Candidate("first", 8192, None), Candidate("second", 8192, None))
    settings = CalibrationSettings(candidates, 2, None, None)

    with pytest.raises(CalibrationError, match="no varying envelope"):
        validate_settings(settings, "cpu")
