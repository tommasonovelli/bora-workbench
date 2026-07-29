"""Render snapshot facts and deterministic advice in the read-only Overview view."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.snapshot import SnapshotFailure, WorkbenchSnapshot, record_display_label
from bora_workbench.tui.advice import Suggestion, next_step


def _engine_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize engine activation without hiding an incompatible installation."""
    engine = snapshot.doctor.engine
    if engine.is_compatible:
        return f"compatible {engine.release or 'managed release'} ({engine.backend or 'unknown'})"
    if engine.is_active:
        return "active but incompatible"
    return "not active"


def _model_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize model receipt state without reading or hashing model payloads."""
    model = snapshot.model
    if model is None:
        return "unavailable"
    if model.is_verified:
        return "receipt verified"
    if not model.is_managed:
        return "user managed"
    present = sum(artifact.status != "absent" for artifact in model.artifacts)
    return f"not verified ({present}/{len(model.artifacts)} copies present)"


def _record_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize packaged records using the shared canonical vocabulary."""
    records = snapshot.doctor.records
    if not records:
        return "unavailable"
    labels = [f"{item.mode_id}: {record_display_label(item.evaluation.status)}" for item in records]
    return ", ".join(labels)


def _validation_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize installed-resource validation without treating warnings as errors."""
    validation = snapshot.doctor.validation
    if validation.errors:
        return f"{len(validation.errors)} error(s)"
    return f"valid with {len(validation.warnings)} warning(s)"


def _service_label(snapshot: WorkbenchSnapshot) -> str:
    """Keep live, stale, and unreadable service state distinct in Overview text."""
    stale = sum(len(root.inspection.stale_services) for root in snapshot.service_roots)
    errors = sum(len(root.inspection.errors) for root in snapshot.service_roots)
    return f"{len(snapshot.services)} running; {stale} stale; {errors} unreadable"


def _diagnostic_lines(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Flatten already collected diagnostics without discovering or repairing more state."""
    lines = [*snapshot.diagnostics, *snapshot.doctor.hardware.warnings]
    lines.extend(snapshot.doctor.engine.differences)
    for issue in snapshot.doctor.validation.issues:
        lines.append(f"{issue.file}:{issue.field_path}: {issue.message}")
    for root in snapshot.service_roots:
        lines.extend(root.inspection.warnings)
        lines.extend(root.inspection.errors)
    for record in snapshot.doctor.records:
        lines.extend(record.evaluation.diagnostics)
        lines.extend(record.evaluation.candidate_diagnostics)
    if snapshot.model is not None:
        lines.extend(snapshot.model.diagnostics)
    if snapshot.pi_context is not None:
        lines.extend(snapshot.pi_context.diagnostics)
    return tuple(lines)


def _advice_lines(suggestion: Suggestion) -> tuple[str, ...]:
    """Render advice as text with its exact but not-yet-selectable command."""
    lines = (suggestion.headline, suggestion.detail)
    if suggestion.command is None:
        return lines
    return (*lines, f"Suggested command: {suggestion.command}")


def render_snapshot(snapshot: WorkbenchSnapshot) -> str:
    """Render the diagnosis first and then compact supporting local facts."""
    doctor = snapshot.doctor
    hardware = doctor.hardware
    pi_state = "installed" if snapshot.pi_installation.is_installed else "not found on PATH"
    context = (
        "unavailable" if snapshot.pi_context is None else f"{snapshot.pi_context.tokens} tokens"
    )
    facts = (
        f"Version: {doctor.version}",
        f"Hardware: {hardware.cpu_name} / {hardware.ram_total_gib:.2f} GiB RAM",
        f"Selected backend: {hardware.backend}",
        f"Engine: {_engine_label(snapshot)}",
        f"Services: {_service_label(snapshot)}",
        f"Model: {_model_label(snapshot)}",
        f"Calibration: {_record_label(snapshot)}",
        f"pi: {pi_state}; context: {context}",
        f"Packaged content: {_validation_label(snapshot)}",
    )
    diagnostics = _diagnostic_lines(snapshot)
    sections = (*_advice_lines(next_step(snapshot)), "", "Local snapshot", *facts)
    if diagnostics:
        sections = (*sections, "", "Diagnostics", *(f"- {item}" for item in diagnostics))
    return "\n".join(sections)


def render_failure(failure: SnapshotFailure | None, unexpected_detail: str | None) -> str:
    """Render failed collection truth and deterministic remediation when one is known."""
    if failure is not None:
        suggestion = next_step(failure)
        lines = (
            "Snapshot unavailable",
            *_advice_lines(suggestion),
            "",
            "No local state was changed.",
        )
        return "\n".join(lines)
    detail = unexpected_detail or "unknown failure"
    return f"Snapshot collection failed.\n{detail}\n\nNo local state was changed."


class OverviewView(Vertical):
    """Own Overview widgets while the application owns collection and navigation."""

    def __init__(self) -> None:
        """Create the fixed content region without collecting any machine facts."""
        super().__init__(id="content")

    def compose(self) -> ComposeResult:
        """Yield the static Overview title, status line, and detail pane."""
        yield Static("Overview", id="view-title", markup=False)
        yield Static("Waiting to inspect this machine...", id="snapshot-status", markup=False)
        yield Static("Local facts will appear here.", id="overview", markup=False)

    def update_status(self, text: str) -> None:
        """Replace the bounded collector-state line with literal text."""
        self.query_one("#snapshot-status", Static).update(text)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the detail pane with current immutable facts and advice."""
        self.query_one("#overview", Static).update(render_snapshot(snapshot))

    def show_failure(self, failure: SnapshotFailure | None, detail: str | None) -> None:
        """Replace stale detail with the current failed-attempt diagnosis."""
        self.query_one("#overview", Static).update(render_failure(failure, detail))
