"""Render active calibration and pending-candidate states without activating either."""

from __future__ import annotations

from typing import Literal, cast

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench._calibration_reuse import CandidateStatus
from bora_workbench._calibration_types import MEASURABLE_CONTEXT_SCALE, PREFERENCES, Preference
from bora_workbench.snapshot import WorkbenchSnapshot, record_display_label
from bora_workbench.tui.actions import (
    CalibrationMode,
    CalibrationSelection,
    CommandSpec,
    ModeId,
    compose_calibration,
    compose_calibration_activation,
)

_CANDIDATE_LABELS: dict[CandidateStatus, str] = {
    "missing": "absent",
    "valid": "candidate",
    "superseded": "superseded",
    "invalid": "invalid",
}
WizardStage = Literal["mode", "preference", "activation", "target", "review"]
_MODE_CHOICES: tuple[CalibrationMode, ...] = ("coding", "studio", "vstudio", "all")
_TARGET_CHOICES: tuple[int | None, ...] = (None, *MEASURABLE_CONTEXT_SCALE)
_STAGE_NUMBERS = {"mode": 1, "preference": 2, "activation": 3, "target": 4}


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
    """Show calibration truth and compose one reviewed terminal command without running it."""

    def __init__(self) -> None:
        """Create a wizard at mode selection with balanced activation defaults."""
        super().__init__(classes="section-view")
        self._stage: WizardStage = "mode"
        self._choice_index = 0
        self._mode: CalibrationMode = "coding"
        self._preference: Preference = "balanced"
        self._is_candidate_only = False
        self._target_ctx: int | None = None
        self._candidate_modes: tuple[ModeId, ...] = ()
        self._candidate_mode: ModeId | None = None

    def compose(self) -> ComposeResult:
        """Yield the title, wizard, and immutable record details."""
        yield Static("Calibration", classes="section-title", markup=False)
        yield Static(self._wizard_text(), classes="section-actions", markup=False)
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def _choices(self) -> tuple[str, ...]:
        """Return only the valid choices for the current wizard stage."""
        if self._stage == "mode":
            candidates = tuple(f"activate candidate: {mode}" for mode in self._candidate_modes)
            return (*_MODE_CHOICES, *candidates)
        if self._stage == "preference":
            return tuple(value.replace("_", "-") for value in PREFERENCES)
        if self._stage == "activation":
            return ("activate measured record", "keep as candidate (--no-activate)")
        if self._stage == "target":
            targets = tuple(str(value) for value in MEASURABLE_CONTEXT_SCALE)
            return ("search the approved measurable scale", *targets)
        return ()

    def _selected_command(self) -> CommandSpec:
        """Compose either the separate activation route or the measured wizard state."""
        if self._candidate_mode is not None:
            return compose_calibration_activation(self._candidate_mode)
        selection = CalibrationSelection(
            self._mode, self._preference, self._is_candidate_only, self._target_ctx
        )
        return compose_calibration(selection)

    def _wizard_text(self) -> str:
        """Render current choices or the exact final command and CLI ownership warning."""
        if self._stage == "review":
            command = self._selected_command()
            return "\n".join(
                (
                    "Review the exact terminal command",
                    f"> {command.display}",
                    "The real CLI preflight and confirmation follow after the TUI closes.",
                    "Press Enter to continue, or Esc/q to cancel without running it.",
                )
            )
        number = _STAGE_NUMBERS[self._stage]
        lines = [f"Calibration wizard step {number}/4: {self._stage} (Tab selects; Enter accepts)"]
        lines.extend(
            f"{'>' if index == self._choice_index else ' '} {choice}"
            for index, choice in enumerate(self._choices())
        )
        return "\n".join(lines)

    def _show_wizard(self) -> None:
        """Update wizard text after one choice or snapshot change."""
        self.query_one(".section-actions", Static).update(self._wizard_text())

    def move_action(self, offset: int) -> None:
        """Move only within the current valid wizard choices."""
        choices = self._choices()
        if choices:
            self._choice_index = (self._choice_index + offset) % len(choices)
            self._show_wizard()

    def _advance_mode(self) -> None:
        """Choose measurement mode or jump a valid candidate directly to review."""
        if self._choice_index < len(_MODE_CHOICES):
            self._mode = _MODE_CHOICES[self._choice_index]
            self._stage = "preference"
            return
        candidate_index = self._choice_index - len(_MODE_CHOICES)
        self._candidate_mode = self._candidate_modes[candidate_index]
        self._stage = "review"

    def _advance_preference(self) -> None:
        """Accept one preference before asking how the measured record is retained."""
        self._preference = PREFERENCES[self._choice_index]
        self._stage = "activation"

    def _advance_activation(self) -> None:
        """Accept normal activation or candidate-only measurement."""
        self._is_candidate_only = self._choice_index == 1
        self._stage = "target"

    def _advance_target(self) -> None:
        """Accept full-scale search or one measurable approved context."""
        self._target_ctx = _TARGET_CHOICES[self._choice_index]
        self._stage = "review"

    def _advance(self) -> None:
        """Accept one choice while keeping forbidden combinations unrepresentable."""
        operations = {
            "mode": self._advance_mode,
            "preference": self._advance_preference,
            "activation": self._advance_activation,
            "target": self._advance_target,
        }
        operations[self._stage]()
        self._choice_index = 1 if self._stage == "preference" else 0
        self._show_wizard()

    def review_action(self) -> CommandSpec | None:
        """Consume Enter for each question and return a command only after final review."""
        if self._stage != "review":
            self._advance()
            return None
        return self._selected_command()

    def selected_action(self) -> CommandSpec:
        """Expose the reviewed command for the generic actionable-view contract."""
        return self._selected_command()

    def _set_candidate_modes(self, snapshot: WorkbenchSnapshot) -> None:
        """Offer activation routes only for valid pending candidates in packaged order."""
        candidates = tuple(
            cast(ModeId, record.mode_id)
            for record in snapshot.doctor.records
            if record.mode_id in _MODE_CHOICES[:-1]
            and record.evaluation.candidate_status == "valid"
        )
        self._candidate_modes = candidates
        if self._candidate_mode is not None and self._candidate_mode not in candidates:
            self._stage, self._choice_index, self._candidate_mode = "mode", 0, None
        self._choice_index %= max(1, len(self._choices()))
        self._show_wizard()

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace record details and update only snapshot-supported candidate routes."""
        self._set_candidate_modes(snapshot)
        self.query_one(".section-body", Static).update(render_calibration(snapshot))
