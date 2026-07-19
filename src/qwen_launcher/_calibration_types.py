"""Define immutable runtime evidence produced by calibration candidate trials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.calibration import Candidate
from qwen_launcher.profiles import Mode

# "oom" must match as a whole word: a bare substring test would classify unrelated log text
# such as "zoom" as an out-of-memory failure.
_OOM_PATTERN = re.compile(r"\boom\b|out of memory")


@dataclass(frozen=True, slots=True)
class CandidateTrial:
    """Record one valid or discarded candidate with all report and bundle evidence."""

    candidate: Candidate
    outcome: str
    discard_reason: str | None
    successful_start_runs: int
    benchmark: BenchmarkResult | None
    vram: VramSummary | None
    log_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ModeTrials:
    """Hold ordered candidate trials and the deterministic draft proposal for one mode."""

    mode: Mode
    candidates: tuple[CandidateTrial, ...]
    proposed_candidate_id: str | None


@dataclass(frozen=True, slots=True)
class TrialResult:
    """Hold all selected-mode trials and optional CUDA driver evidence."""

    modes: tuple[ModeTrials, ...]
    gpu_driver: str | None


def discard_reason(error: Exception, logs: tuple[Path, ...]) -> str:
    """Classify OOM evidence while preserving an actionable candidate failure reason."""
    text = str(error)
    for path in logs:
        try:
            text += "\n" + path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    lowered = text.casefold()
    if _OOM_PATTERN.search(lowered):
        return f"OOM: {error}"
    return str(error) or error.__class__.__name__


def select_candidate(trials: tuple[CandidateTrial, ...]) -> str | None:
    """Maximize median, then free VRAM, then preserve the prudent declared order."""
    valid = [(index, trial) for index, trial in enumerate(trials) if trial.outcome == "valid"]
    if not valid:
        return None

    def key(item: tuple[int, CandidateTrial]) -> tuple[float, float, int]:
        """Build the exact calibration/v1 selection key for one valid trial."""
        index, trial = item
        assert trial.benchmark is not None
        free = float("inf") if trial.vram is None else trial.vram.minimum_free_gib
        return (trial.benchmark.tok_s.median, free, -index)

    return max(valid, key=key)[1].candidate.id
