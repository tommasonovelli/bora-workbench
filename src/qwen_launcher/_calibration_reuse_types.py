"""Define immutable active-record and pending-candidate evaluation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from qwen_launcher._calibration_record import JsonObject
from qwen_launcher.config import Config
from qwen_launcher.hardware import HardwareInfo

RecordStatus = Literal[
    "valid",
    "missing",
    "candidate",
    "superseded",
    "invalid",
    "incompatible",
    "insufficient-headroom",
]
CandidateStatus = Literal["missing", "valid", "superseded", "invalid"]


@dataclass(frozen=True, slots=True)
class ReuseQuery:
    """Group current identities a record must match before reuse."""

    config: Config
    mode_id: str
    hardware: HardwareInfo
    lock: JsonObject


@dataclass(frozen=True, slots=True)
class RecordEvaluation:
    """Report active reuse and pending-candidate state with actionable diagnostics."""

    status: RecordStatus
    ctx: int | None
    n_cpu_moe: int | None
    diagnostics: tuple[str, ...]
    candidate_status: CandidateStatus = "missing"
    candidate_diagnostics: tuple[str, ...] = ()
