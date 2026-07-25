"""Options and result for one calibration run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_progress import ProgressCallback
from qwen_launcher._calibration_runner import ModeResult
from qwen_launcher._calibration_types import DEFAULT_PREFERENCE, Preference


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Group the optional controls without burdening the zero-input default path."""

    preference: Preference = DEFAULT_PREFERENCE
    target_ctx: int | None = None
    is_activate: bool = True
    progress: ProgressCallback | None = None


@dataclass(frozen=True, slots=True)
class RunResult:
    """Identify the evidence run, the written record paths, and any group that did not finish.

    ``failures`` is non-empty only for a partial run: the modes it names produced no record, while
    every mode in ``mode_results`` was measured and gated completely.
    """

    evidence_run_id: str
    record_paths: tuple[Path, ...]
    mode_results: tuple[ModeResult, ...]
    evidence_path: Path
    failures: tuple[str, ...] = ()
