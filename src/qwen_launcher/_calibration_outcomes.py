"""Classify v6/spike trials without changing calibration/v5 behavior."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

import httpx

from qwen_launcher._calibration_ram import RamError, RamReserveError
from qwen_launcher._calibration_vram import (
    VramEnvironmentError,
    VramReleaseError,
    VramReserveError,
)
from qwen_launcher.benchmark import BenchmarkError, BenchmarkRetryableError


class TrialOutcome(Enum):
    """Name the four v6-lite trial outcomes from D-059."""

    SUCCESS = "success"
    MEMORY_INFEASIBLE = "memory_infeasible"
    RETRYABLE = "retryable"
    PROTOCOL_INVALID = "protocol_invalid"


@dataclass(frozen=True, slots=True)
class ClassifiedOutcome:
    """Attach the constrained memory resource only to infeasible outcomes."""

    outcome: TrialOutcome
    resource: Literal["ram", "vram"] | None = None


class UnclassifiableTrialError(ValueError):
    """Report an error that invalidates the run rather than one candidate."""


def classify(error: BaseException | None) -> ClassifiedOutcome:
    """Map class-defined failures to D-059 outcomes and reject run-invalidating evidence."""
    if error is None:
        return ClassifiedOutcome(TrialOutcome.SUCCESS)
    if isinstance(error, (VramEnvironmentError, RamError)):
        raise UnclassifiableTrialError(f"run-invalidating error: {error}") from error
    if isinstance(error, VramReserveError):
        return ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "vram")
    if isinstance(error, RamReserveError):
        return ClassifiedOutcome(TrialOutcome.MEMORY_INFEASIBLE, "ram")
    retryable = (VramReleaseError, BenchmarkRetryableError, httpx.TransportError)
    if isinstance(error, retryable):
        return ClassifiedOutcome(TrialOutcome.RETRYABLE)
    if isinstance(error, BenchmarkError):
        return ClassifiedOutcome(TrialOutcome.PROTOCOL_INVALID)
    raise UnclassifiableTrialError(f"unsupported trial error: {type(error).__name__}") from error
