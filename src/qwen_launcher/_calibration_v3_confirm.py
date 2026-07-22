"""Confirm calibration/v3 finalists with paired ABBA rounds and full benchmarks.

Two finalists run A→B then B→A, giving both equal mean temporal position without adding process
starts. Baseline drift no longer discards either finalist because absolute reserves remain enforced;
it is returned so selection can suppress throughput dominance (D-041).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from qwen_launcher._calibration_gpu_evidence import combine_telemetry
from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_v3_plan import build_plan
from qwen_launcher._calibration_v3_process import TrialFailure, TrialSpec, run_trial
from qwen_launcher._calibration_v3_types import (
    CONFIRM_ROUNDS,
    FinalistEvidence,
    ProgressUpdate,
    TrialEvidence,
    TrialOrder,
)
from qwen_launcher._calibration_vram import VramSummary

if TYPE_CHECKING:
    from qwen_launcher._calibration_v3_screening import _ModeRun


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    """Return finalists and the measured aggregate VRAM baseline excursion."""

    finalists: tuple[FinalistEvidence, ...]
    baseline_drift_gib: float | None


@dataclass(frozen=True, slots=True)
class _SessionAssignment:
    """Identify one finalist's deterministic round and global ABBA position."""

    finalist_index: int
    round_index: int
    global_position: int


@dataclass(slots=True)
class _PairedRun:
    """Group one mode run, context, and mutable per-finalist confirmation state."""

    mode_run: _ModeRun
    ctx: int
    confirmations: list[_Confirmation]


@dataclass(slots=True)
class _Confirmation:
    """Collect all paired sessions and the first candidate-level failure for one finalist."""

    ctx: int
    n_cpu_moe: int | None
    sessions: list[TrialEvidence] = field(default_factory=list)
    discard_reason: str | None = None

    def absorb(self, evidence: TrialEvidence, error: Exception | None = None) -> None:
        """Retain one session and preserve the first failure diagnosis."""
        self.sessions.append(evidence)
        if error is not None and self.discard_reason is None:
            self.discard_reason = str(error)

    def finished(self) -> FinalistEvidence:
        """Assemble one finalist from every scheduled paired session."""
        reason = self.discard_reason
        if reason is None and any(session.benchmark is None for session in self.sessions):
            reason = "confirmation session produced no benchmark/v1 result"
        vram = _combine_vram([item.vram for item in self.sessions if item.vram is not None])
        ram = _combine_ram([item.ram for item in self.sessions if item.ram is not None])
        return FinalistEvidence(
            self.ctx,
            self.n_cpu_moe,
            "valid" if reason is None else "discarded",
            reason,
            tuple(self.sessions),
            vram,
            ram,
        )


def _combine_vram(summaries: list[VramSummary]) -> VramSummary | None:
    """Combine sessions without understating peak, incremental need, or release duration."""
    if not summaries:
        return None
    return VramSummary(
        min(item.baseline_used_gib for item in summaries),
        max(item.peak_used_gib for item in summaries),
        min(item.minimum_free_gib for item in summaries),
        max(item.release_used_gib for item in summaries),
        summaries[0].driver_version,
        max(item.release_duration_seconds for item in summaries),
        max(item.initial_compute_context_count for item in summaries),
        combine_telemetry([item.telemetry for item in summaries]),
        sum(item.context_replacement_count for item in summaries),
    )


def _combine_ram(summaries: list[RamSummary]) -> RamSummary | None:
    """Combine sessions without understating the observed RAM range."""
    if not summaries:
        return None
    return RamSummary(
        max(item.baseline_available_gib for item in summaries),
        min(item.minimum_available_gib for item in summaries),
    )


def _schedule(count: int) -> tuple[_SessionAssignment, ...]:
    """Build the exact A→B/B→A order, or two rounds for a sole finalist."""
    if CONFIRM_ROUNDS != 2:
        raise ValueError("calibration/v3 ABBA confirmation requires exactly two rounds")
    order = ((0,), (0,)) if count == 1 else ((0, 1), (1, 0))
    assignments: list[_SessionAssignment] = []
    position = 0
    for round_index, finalists in enumerate(order, start=1):
        for finalist_index in finalists:
            position += 1
            assignments.append(_SessionAssignment(finalist_index, round_index, position))
    return tuple(assignments)


def _trial_spec(run: _ModeRun, ctx: int, assignment: _SessionAssignment) -> TrialSpec:
    """Build one isolated confirmation trial with its record-reconstructible ABBA position."""
    value = run.finalist_values[assignment.finalist_index]
    label = "baseline" if value is None else f"n{value}"
    root = (
        run.runtime_root
        / run.mode.id
        / (f"final-r{assignment.round_index}-p{assignment.global_position}-{label}")
    )
    order = TrialOrder(
        "confirmation",
        assignment.global_position,
        assignment.round_index,
        assignment.global_position,
    )
    return TrialSpec(
        build_plan(run, ctx, value),
        root,
        True,
        run.runtime_root,
        order,
        run.gpu_context_baseline,
    )


def _run_session(paired: _PairedRun, assignment: _SessionAssignment) -> None:
    """Run one scheduled session and retain candidate failures without breaking ABBA."""
    run = paired.mode_run
    progress = paired.confirmations[assignment.finalist_index]
    total = len(_schedule(len(paired.confirmations)))
    run.report_progress(ProgressUpdate("confirmation", assignment.global_position - 1, total, True))
    try:
        measured = run_trial(run.target, _trial_spec(run, paired.ctx, assignment))
    except TrialFailure as failure:
        progress.absorb(failure.evidence, failure.error)
        evidence = failure.evidence
    else:
        progress.absorb(measured.evidence)
        evidence = measured.evidence
    if evidence.vram is not None:
        run.drivers.add(evidence.vram.driver_version)
    run.note_duration(evidence)
    run.report_progress(ProgressUpdate("confirmation", assignment.global_position, total, False))


def _baseline_drift(finalists: tuple[FinalistEvidence, ...]) -> float | None:
    """Measure aggregate confirmation baseline excursion when CUDA evidence exists."""
    baselines = [
        session.vram.baseline_used_gib
        for finalist in finalists
        for session in finalist.sessions
        if session.vram is not None
    ]
    return max(baselines) - min(baselines) if len(baselines) > 1 else None


def confirm_finalists(run: _ModeRun, ctx: int) -> ConfirmationResult:
    """Execute paired rounds for all finalists and return drift as a selection degradation flag."""
    paired = _PairedRun(run, ctx, [_Confirmation(ctx, value) for value in run.finalist_values])
    for assignment in _schedule(len(paired.confirmations)):
        _run_session(paired, assignment)
    finalists = tuple(progress.finished() for progress in paired.confirmations)
    return ConfirmationResult(finalists, _baseline_drift(finalists))
