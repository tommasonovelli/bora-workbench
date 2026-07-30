"""Offer managed-engine and pinned-model setup without installing or verifying anything."""

from __future__ import annotations

from bora_workbench.models import ArtifactInspection
from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.actions import (
    compose_engine_install,
    compose_engine_status,
    compose_pull,
    compose_remove_model,
)
from bora_workbench.tui.choices import Choice, ChoiceList, Flag
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section

_FORCE = "force"
_NO_MODEL = "no-model"
_KEEP_CACHE = "keep-cache"
_DRY_RUN = "dry-run"
_NOTE = (
    "Opening this screen never downloads or hashes model payloads.",
    "keep-cache leaves shared Hugging Face copies; dry-run deletes nothing.",
    "Downloads, verification, and confirmations begin only after the workbench closes.",
)
CHOICES: tuple[Choice, ...] = (
    Choice(
        "install engine",
        lambda flags: compose_engine_install(_FORCE in flags, _NO_MODEL in flags),
        (Flag("f", _FORCE), Flag("n", _NO_MODEL)),
    ),
    Choice("download pinned model", lambda flags: compose_pull()),
    Choice(
        "remove pinned model",
        lambda flags: compose_remove_model(_KEEP_CACHE in flags, _DRY_RUN in flags),
        (Flag("c", _KEEP_CACHE), Flag("d", _DRY_RUN)),
    ),
    Choice("engine status", lambda flags: compose_engine_status()),
)


def _engine_lines(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Describe the active engine and every collected lock difference as text."""
    engine = snapshot.doctor.engine
    state = "active" if engine.is_active else "not active"
    compatibility = "matches engine.lock" if engine.is_compatible else "does not match engine.lock"
    lines = (
        "Engine",
        f"state         {state}, {compatibility}",
        f"release       {engine.release or 'none'} ({engine.backend or 'no backend'})",
        f"executable    {engine.executable or 'none'}",
    )
    return (*lines, *(f"difference    {item}" for item in engine.differences))


def _artifact_line(artifact: ArtifactInspection) -> str:
    """Render one artifact's receipt status, location, and literal path."""
    size = "absent" if artifact.size_bytes is None else f"{artifact.size_bytes} bytes"
    state = f"{artifact.status}, {artifact.location}, {size}"
    return f"{artifact.label.ljust(14)}{state}\n{'':14}{artifact.path}"


def _model_lines(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Describe model ownership and receipts without treating presence as verification."""
    model = snapshot.model
    if model is None:
        return ("", "Model", "Inspection unavailable until packaged content validates.")
    ownership = "locked managed model" if model.is_managed else "user-managed external model"
    verified = "receipt verified" if model.is_verified else "receipt not verified"
    lines = ("", "Model", f"identity      {model.model}", f"ownership     {ownership}, {verified}")
    lines = (*lines, *(_artifact_line(artifact) for artifact in model.artifacts))
    return (*lines, *(f"diagnostic    {item}" for item in model.diagnostics))


def render_setup(snapshot: WorkbenchSnapshot) -> str:
    """Render setup facts while keeping acquisition and digest work in existing CLI owners."""
    return "\n".join((*_engine_lines(snapshot), *_model_lines(snapshot), "", *_NOTE))


class SetupView(Section):
    """Show engine and model setup facts without exposing an embedded installer."""

    def __init__(self, palette: Palette) -> None:
        """Create the hidden-until-opened setup section marked on engine installation."""
        super().__init__("Setup", ChoiceList(CHOICES), palette)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with receipt-aware setup details."""
        self.show_body(render_setup(snapshot))
