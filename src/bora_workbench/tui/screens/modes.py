"""Offer the three foreground modes beside the calibration cell or baseline each would use."""

from __future__ import annotations

from bora_workbench.profiles import FALLBACK_CTX
from bora_workbench.snapshot import ModeRecordSnapshot, WorkbenchSnapshot
from bora_workbench.tui.actions import ModeId, compose_mode
from bora_workbench.tui.choices import Choice, ChoiceList, Flag
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section

_FORCE = "force"
_MODES: tuple[ModeId, ...] = ("coding", "studio", "vstudio")
_NOTE = (
    "- `--force` bypasses only the default-model memory gate.",
    "- The selected mode owns this terminal after the workbench closes.",
)
_MODE_GUIDANCE = {
    "coding": "API-first development with browser UI and vision disabled.",
    "studio": "Text chat through the integrated llama.cpp browser interface.",
    "vstudio": "Multimodal chat with the pinned vision projector enabled.",
}


def _mode_choice(mode: ModeId) -> Choice:
    """Build one mode row whose sole flag is the exact memory-gate override."""
    return Choice(
        mode,
        lambda flags: compose_mode(mode, _FORCE in flags),
        (Flag("f", _FORCE),),
        _MODE_GUIDANCE[mode],
    )


CHOICES: tuple[Choice, ...] = tuple(_mode_choice(mode) for mode in _MODES)


def _cell(record: ModeRecordSnapshot) -> str:
    """Describe an active measured cell or the safe baseline used without one."""
    evaluation = record.evaluation
    if evaluation.status != "valid" or evaluation.ctx is None:
        return f"verified baseline, ctx {FALLBACK_CTX}"
    n_cpu_moe = "" if evaluation.n_cpu_moe is None else f", n_cpu_moe {evaluation.n_cpu_moe}"
    preference = evaluation.preference or "recorded"
    return f"active {preference} cell, ctx {evaluation.ctx}{n_cpu_moe}"


def render_modes(snapshot: WorkbenchSnapshot) -> str:
    """Render one line per packaged mode without constructing a launch plan."""
    records = snapshot.doctor.records
    if not records:
        return "No trusted packaged record was collected, so no launch cell can be shown."
    lines = [f"{record.mode_id.ljust(12)}{_cell(record)}" for record in records]
    return "\n".join(("Launch cells", *lines, "", "Before launch", *_NOTE))


class ModesView(Section):
    """Show mode launch facts without invoking profile selection or a mode callback."""

    def __init__(self, palette: Palette) -> None:
        """Create the hidden-until-opened Run section marked on the first mode."""
        super().__init__("Run a mode", ChoiceList(CHOICES), palette)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with cells derived only from the shared snapshot."""
        self.show_body(render_modes(snapshot))
