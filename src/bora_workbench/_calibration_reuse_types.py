"""Define immutable active-record and pending-candidate evaluation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bora_workbench._calibration_record import JsonObject
from bora_workbench.config import Config
from bora_workbench.hardware import HardwareInfo

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
