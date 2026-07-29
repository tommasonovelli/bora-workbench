"""Render managed-engine and receipt-aware model setup without installing or verifying."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.models import ArtifactInspection
from bora_workbench.snapshot import WorkbenchSnapshot


def _engine_lines(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Describe the active engine and every collected lock difference as text."""
    engine = snapshot.doctor.engine
    lines = (
        "Engine",
        f"Active: {'yes' if engine.is_active else 'no'}",
        f"Compatible: {'yes' if engine.is_compatible else 'no'}",
        f"Release: {engine.release or 'none'}",
        f"Backend: {engine.backend or 'none'}",
        f"Executable: {engine.executable or 'none'}",
    )
    differences = tuple(f"Difference: {item}" for item in engine.differences)
    return (*lines, *differences)


def _artifact_line(artifact: ArtifactInspection) -> str:
    """Render one artifact's receipt status, location, size, and literal path."""
    size = "absent" if artifact.size_bytes is None else f"{artifact.size_bytes} bytes"
    expected = (
        "not locked"
        if artifact.expected_size_bytes is None
        else f"{artifact.expected_size_bytes} bytes"
    )
    return (
        f"{artifact.label}: {artifact.status}; {artifact.location}; size {size}; "
        f"expected {expected}; path {artifact.path}"
    )


def _model_lines(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Describe model ownership and receipts without treating presence as verification."""
    model = snapshot.model
    if model is None:
        return ("", "Model", "Inspection unavailable until packaged content validates.")
    ownership = "locked managed model" if model.is_managed else "user-managed external model"
    verified = "yes" if model.is_verified else "no"
    lines = ("", "Model", f"Identity: {model.model}", f"Ownership: {ownership}")
    lines = (*lines, f"Receipt verified: {verified}")
    lines = (*lines, *(_artifact_line(artifact) for artifact in model.artifacts))
    return (*lines, *(f"Diagnostic: {item}" for item in model.diagnostics))


def render_setup(snapshot: WorkbenchSnapshot) -> str:
    """Render setup facts while keeping acquisition and digest work in existing CLI owners."""
    note = (
        "Opening this screen never downloads or hashes model payloads.",
        "bora pull applies only to artifacts pinned by engine.lock, not custom model paths.",
        "",
    )
    return "\n".join((*note, *_engine_lines(snapshot), *_model_lines(snapshot)))


class SetupView(Vertical):
    """Show engine and model setup facts without exposing an embedded installer."""

    def __init__(self) -> None:
        """Create the hidden-until-selected setup region."""
        super().__init__(classes="section-view")

    def compose(self) -> ComposeResult:
        """Yield the static title and literal detail body."""
        yield Static("Setup", classes="section-title", markup=False)
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with receipt-aware setup details."""
        self.query_one(".section-body", Static).update(render_setup(snapshot))
