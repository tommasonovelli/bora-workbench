"""Render active calibration and pending-candidate states without activating either."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench._calibration_reuse import CandidateStatus
from bora_workbench.snapshot import WorkbenchSnapshot, record_display_label

_CANDIDATE_LABELS: dict[CandidateStatus, str] = {
    "missing": "absent",
    "valid": "candidate",
    "superseded": "superseded",
    "invalid": "invalid",
}


def _record_lines(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Flatten canonical active and candidate states in packaged mode order."""
    lines: list[str] = []
    for record in snapshot.doctor.records:
        evaluation = record.evaluation
        lines.extend(
            (
                "",
                record.mode_id,
                f"Active record: {record_display_label(evaluation.status)}",
                f"Pending record: {_CANDIDATE_LABELS[evaluation.candidate_status]}",
                f"Preference: {evaluation.preference or 'none'}",
                f"Context: {evaluation.ctx if evaluation.ctx is not None else 'baseline'}",
            )
        )
        lines.extend(f"Diagnostic: {item}" for item in evaluation.diagnostics)
        lines.extend(f"Candidate diagnostic: {item}" for item in evaluation.candidate_diagnostics)
    return tuple(lines)


def render_calibration(snapshot: WorkbenchSnapshot) -> str:
    """Render one protocol's immutable record states and candidate distinction."""
    if not snapshot.doctor.records:
        return "Calibration details are unavailable until packaged mode content validates."
    introduction = (
        "Calibration measures one requested preference cell per selected mode.",
        "A candidate is never active until the real CLI confirmation promotes it.",
    )
    return "\n".join((*introduction, *_record_lines(snapshot)))


class CalibrationView(Vertical):
    """Show calibration truth without reintroducing protocols or writing records."""

    def __init__(self) -> None:
        """Create the hidden-until-selected calibration region."""
        super().__init__(classes="section-view")

    def compose(self) -> ComposeResult:
        """Yield the static title and literal detail body."""
        yield Static("Calibration", classes="section-title", markup=False)
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with canonical record and candidate labels."""
        self.query_one(".section-body", Static).update(render_calibration(snapshot))
