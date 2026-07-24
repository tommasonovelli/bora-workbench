"""Unit tests for class-based v6-lite and spike trial outcomes."""

from __future__ import annotations

import httpx
import pytest

from qwen_launcher._calibration_outcomes import (
    ClassifiedOutcome,
    TrialOutcome,
    UnclassifiableTrialError,
    classify,
)
from qwen_launcher._calibration_ram import RamError, RamReserveError, RamSummary
from qwen_launcher._calibration_vram import (
    VramEnvironmentError,
    VramReleaseError,
    VramReserveError,
)
from qwen_launcher.benchmark import BenchmarkError, BenchmarkHttpError


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, ClassifiedOutcome(TrialOutcome.SUCCESS)),
        (
            VramReserveError("reserve"),
            ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram"),
        ),
        (
            RamReserveError(RamSummary(8.0, 1.0)),
            ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "ram"),
        ),
        (VramReleaseError("release"), ClassifiedOutcome(TrialOutcome.RETRYABLE)),
        (BenchmarkHttpError(503), ClassifiedOutcome(TrialOutcome.RETRYABLE)),
        (
            httpx.ConnectError("offline", request=httpx.Request("POST", "http://127.0.0.1")),
            ClassifiedOutcome(TrialOutcome.RETRYABLE),
        ),
        (BenchmarkError("finish_reason"), ClassifiedOutcome(TrialOutcome.PROTOCOL_INVALID)),
    ],
)
def test_classify_maps_supported_error_classes(error, expected) -> None:
    """Map every candidate-level origin without parsing its message."""
    assert classify(error) == expected


@pytest.mark.parametrize(
    "error",
    [VramEnvironmentError("changed environment"), RamError("broken monitor"), OSError("other")],
)
def test_classify_rejects_run_invalidating_or_unknown_errors(error) -> None:
    """Keep unreliable environment evidence outside the candidate taxonomy."""
    with pytest.raises(UnclassifiableTrialError):
        classify(error)
