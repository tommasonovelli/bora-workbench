"""Options and result for one opt-in calibration/v6-lite run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_v6_runner import ModeResult
from qwen_launcher._calibration_v6_types import DEFAULT_PREFERENCE, Preference


@dataclass(frozen=True, slots=True)
class V6RunOptions:
    """Group the opt-in controls for a v6-lite run without burdening the default v5 path."""

    preference: Preference = DEFAULT_PREFERENCE
    target_ctx: int | None = None
    is_activate: bool = True


@dataclass(frozen=True, slots=True)
class V6RunResult:
    """Identify the evidence run and the written per-mode record lifecycle paths."""

    evidence_run_id: str
    record_paths: tuple[Path, ...]
    mode_results: tuple[ModeResult, ...]
