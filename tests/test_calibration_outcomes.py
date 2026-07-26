"""Unit tests for the class-based trial outcome taxonomy."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from bora_workbench._calibration_memory import (
    RamError,
    RamReserveError,
    RamSummary,
    VramEnvironmentError,
    VramReleaseError,
    VramReserveError,
)
from bora_workbench._calibration_types import (
    ClassifiedOutcome,
    TrialOutcome,
    UnclassifiableTrialError,
    classify,
)
from bora_workbench.benchmark import BenchmarkError, BenchmarkHttpError
from bora_workbench.process import ProcessError, ServerStartupError


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


def test_classify_reads_a_startup_failure_as_infeasible_only_with_oom_evidence(
    tmp_path: Path,
) -> None:
    """Map the only observable form of exhausted VRAM: a server that dies during model load."""
    log = tmp_path / "llama-server.log"
    log.write_text("cudaMalloc failed: out of memory\n", encoding="utf-8")
    outcome = classify(ServerStartupError("llama-server exited", log))
    assert outcome == ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram")


def test_classify_treats_a_startup_failure_without_oom_evidence_as_retryable(
    tmp_path: Path,
) -> None:
    """Never fabricate a memory boundary from a start that failed for an unrelated reason."""
    log = tmp_path / "llama-server.log"
    log.write_text("srv init: health timeout\n", encoding="utf-8")
    assert classify(ServerStartupError("health timeout", log)).outcome is TrialOutcome.RETRYABLE
    assert classify(ServerStartupError("no log", None)).outcome is TrialOutcome.RETRYABLE


def test_classify_still_rejects_a_preflight_process_error() -> None:
    """Keep an occupied port or a live service outside the candidate taxonomy."""
    with pytest.raises(UnclassifiableTrialError):
        classify(ProcessError("port 8080 is already occupied"))
