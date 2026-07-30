"""Compose one calibration route through a wizard that cannot reach an invalid combination."""

from __future__ import annotations

from typing import Literal, cast

from rich.text import Text

from bora_workbench._calibration_reuse import CandidateStatus
from bora_workbench._calibration_types import MEASURABLE_CONTEXT_SCALE, PREFERENCES, Preference
from bora_workbench.snapshot import (
    ModeRecordSnapshot,
    WorkbenchSnapshot,
    record_display_label,
)
from bora_workbench.tui.actions import (
    CalibrationMode,
    CalibrationSelection,
    CommandSpec,
    ModeId,
    compose_calibration,
    compose_calibration_activation,
)
from bora_workbench.tui.choices import ChoiceList
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section

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
_STAGE_QUESTIONS = {
    "mode": "which mode to measure",
    "preference": "which preference to measure",
    "activation": "what to do with the measured record",
    "target": "which context to target",
}


def _record_line(record: ModeRecordSnapshot) -> str:
    """Render one mode's active and pending record state on a single line."""
    evaluation = record.evaluation
    active = record_display_label(evaluation.status)
    pending = _CANDIDATE_LABELS[evaluation.candidate_status]
    context = evaluation.ctx if evaluation.ctx is not None else "baseline"
    preference = evaluation.preference or "none"
    state = f"active {active}, pending {pending}, {preference}, ctx {context}"
    return f"{record.mode_id.ljust(10)}{state}"


def render_calibration(snapshot: WorkbenchSnapshot) -> str:
    """Render one protocol's immutable record states and candidate distinction."""
    if not snapshot.doctor.records:
        return "Calibration details are unavailable until packaged mode content validates."
    lines = [_record_line(record) for record in snapshot.doctor.records]
    note = (
        "- Calibration measures one requested preference cell per selected mode.",
        "- A candidate is never active until the real CLI confirmation promotes it.",
    )
    return "\n".join(("Record lifecycle", *lines, "", "How it works", *note))


class CalibrationView(Section):
    """Show calibration truth and compose one reviewed command without running it."""

    def __init__(self, palette: Palette) -> None:
        """Create a wizard at mode selection with balanced activation defaults."""
        super().__init__("Calibration", ChoiceList(()), palette)
        self._stage: WizardStage = "mode"
        self._choice_index = 0
        self._mode: CalibrationMode = "coding"
        self._preference: Preference = "balanced"
        self._is_candidate_only = False
        self._target_ctx: int | None = None
        self._candidate_modes: tuple[ModeId, ...] = ()
        self._candidate_mode: ModeId | None = None

    def shows_actions(self) -> bool:
        """Paint the wizard even though this section holds no fixed action list."""
        return True

    def _choices_for_stage(self) -> tuple[str, ...]:
        """Return only the valid choices for the current wizard stage."""
        if self._stage == "mode":
            candidates = tuple(f"activate the {mode} candidate" for mode in self._candidate_modes)
            return (*_MODE_CHOICES, *candidates)
        if self._stage == "preference":
            return tuple(value.replace("_", "-") for value in PREFERENCES)
        if self._stage == "activation":
            return ("activate the measured record", "keep it as a candidate")
        if self._stage == "target":
            targets = tuple(str(value) for value in MEASURABLE_CONTEXT_SCALE)
            return ("search the approved scale", *targets)
        return ()

    def _selected_command(self) -> CommandSpec:
        """Compose either the separate activation route or the measured wizard state."""
        if self._candidate_mode is not None:
            return compose_calibration_activation(self._candidate_mode)
        selection = CalibrationSelection(
            self._mode, self._preference, self._is_candidate_only, self._target_ctx
        )
        return compose_calibration(selection)

    def _action_text(self) -> Text:
        """Render the current question, or the reviewed command and its CLI ownership."""
        text = Text()
        if self._stage == "review":
            text.append("Review the exact command", style=self._palette.selected_style)
            text.append("\n\nNext  ", style=self._palette.accent_style)
            text.append(
                "The real CLI preflight and confirmation follow after this closes.",
                style=self._palette.body_style,
            )
            return text
        number = _STAGE_NUMBERS[self._stage]
        text.append(f"Step {number}/4  ", style=self._palette.accent_style)
        text.append(_STAGE_QUESTIONS[self._stage], style=self._palette.body_style)
        text.append("\n\n")
        stage_choices = self._choices_for_stage()
        for position, choice in enumerate(stage_choices):
            is_marked = position == self._choice_index
            marker = f"{self._palette.marker} " if is_marked else "  "
            style = self._palette.selected_style if is_marked else self._palette.body_style
            text.append(f"{marker}{choice}", style=style)
            if position < len(stage_choices) - 1:
                text.append("\n")
        return text

    def _preview_text(self) -> Text:
        """Show the exact command only once every question has been answered."""
        if self._stage != "review":
            return Text("Enter accepts the marked answer.", style=self._palette.muted_style)
        text = Text("Command  ", style=self._palette.accent_style)
        text.append(self._selected_command().display, style=self._palette.command_style)
        return text

    def move(self, offset: int) -> None:
        """Move only within the current valid wizard choices."""
        stage_choices = self._choices_for_stage()
        if stage_choices:
            self._choice_index = (self._choice_index + offset) % len(stage_choices)
            self.refresh_actions()

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
        """Accept one answer while keeping forbidden combinations unrepresentable."""
        operations = {
            "mode": self._advance_mode,
            "preference": self._advance_preference,
            "activation": self._advance_activation,
            "target": self._advance_target,
        }
        operations[self._stage]()
        self._choice_index = 1 if self._stage == "preference" else 0
        self.refresh_actions()

    def activate(self) -> CommandSpec | None:
        """Consume Enter for each question and return a command only after final review."""
        if self._stage != "review":
            self._advance()
            return None
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
        self._choice_index %= max(1, len(self._choices_for_stage()))
        self.refresh_actions()

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace record details and update only snapshot-supported candidate routes."""
        self._set_candidate_modes(snapshot)
        self.show_body(render_calibration(snapshot))
