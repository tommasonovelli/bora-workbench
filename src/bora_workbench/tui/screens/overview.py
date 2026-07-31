"""Render the full local report and the returning diagnostic commands."""

from __future__ import annotations

from bora_workbench.snapshot import SnapshotFailure, WorkbenchSnapshot, record_display_label
from bora_workbench.tui.actions import (
    compose_doctor,
    compose_engine_status,
    compose_status,
    compose_stop,
    compose_validate,
)
from bora_workbench.tui.advice import next_step
from bora_workbench.tui.choices import Choice, ChoiceList
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section

# The four read-only reports come first, widest first, and the one action that changes this
# machine stays last (D-097).
CHOICES: tuple[Choice, ...] = (
    Choice(
        "full local report",
        lambda flags: compose_doctor(),
        description="Print configuration, hardware, engine, records, paths, and validation.",
    ),
    Choice(
        "check managed services",
        lambda flags: compose_status(),
        description="Show verified live services and clean stale process state.",
    ),
    Choice(
        "check the managed engine",
        lambda flags: compose_engine_status(),
        description="Compare the active engine with the exact packaged lock.",
    ),
    Choice(
        "validate packaged content",
        lambda flags: compose_validate(),
        description="Check schemas, references, digests, and cross-cutting contracts.",
    ),
    Choice(
        "stop managed services",
        lambda flags: compose_stop(),
        description="Stop only services whose process identity still verifies.",
    ),
)


def _engine_label(snapshot: WorkbenchSnapshot) -> str:
    """Summarize engine activation without hiding an incompatible installation."""
    engine = snapshot.doctor.engine
    if engine.is_compatible:
        return f"compatible {engine.release or 'managed release'} ({engine.backend or 'unknown'})"
    return "active but incompatible" if engine.is_active else "not active"


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


def _service_label(snapshot: WorkbenchSnapshot) -> str:
    """Keep live, stale, and unreadable service state distinct in one line."""
    stale = sum(len(root.inspection.stale_services) for root in snapshot.service_roots)
    errors = sum(len(root.inspection.errors) for root in snapshot.service_roots)
    return f"{len(snapshot.services)} running, {stale} stale, {errors} unreadable"


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


def _facts(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Render the compact local facts a reader checks before running anything."""
    hardware = snapshot.doctor.hardware
    context = (
        "unavailable" if snapshot.pi_context is None else f"{snapshot.pi_context.tokens} tokens"
    )
    validation = snapshot.doctor.validation
    return (
        f"hardware      {hardware.cpu_name}, {hardware.ram_total_gib:.2f} GiB RAM",
        f"backend       {hardware.backend}",
        f"engine        {_engine_label(snapshot)}",
        f"services      {_service_label(snapshot)}",
        f"model         {_model_label(snapshot)}",
        f"calibration   {_record_label(snapshot)}",
        f"pi            {'installed' if snapshot.pi_installation.is_installed else 'not installed'}"
        f", context {context}",
        f"content       {len(validation.errors)} error(s), {len(validation.warnings)} warning(s)",
    )


def render_snapshot(snapshot: WorkbenchSnapshot) -> str:
    """Render compact local facts followed by every collected diagnostic."""
    diagnostics = _diagnostic_lines(snapshot)
    sections = ("System overview", *_facts(snapshot))
    if diagnostics:
        sections = (*sections, "", "Notes", *(f"- {item}" for item in diagnostics))
    return "\n".join(sections)


def render_failure(failure: SnapshotFailure | None, unexpected_detail: str | None) -> str:
    """Render failed collection truth and deterministic remediation when one is known."""
    if failure is None:
        detail = unexpected_detail or "unknown failure"
        return f"Snapshot collection failed.\n{detail}\n\nNo local state was changed."
    suggestion = next_step(failure)
    lines = (
        "Snapshot unavailable",
        suggestion.headline,
        suggestion.detail,
        "",
        "No local state was changed.",
    )
    return "\n".join(lines)


class OverviewView(Section):
    """Show the whole local report without running any of the diagnostics it names."""

    def __init__(self, palette: Palette) -> None:
        """Create the hidden-until-opened Diagnostics section with no comparison yet."""
        super().__init__("Diagnostics", ChoiceList(CHOICES), palette)
        self._changes: tuple[str, ...] = ()

    def show_changes(self, changes: tuple[str, ...]) -> None:
        """Keep concise recollected differences until the next successful collection."""
        self._changes = changes

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with current immutable facts and any pending comparison."""
        report = render_snapshot(snapshot)
        if not self._changes:
            self.show_body(report)
            return
        changed = "\n".join(f"- {item}" for item in self._changes)
        self.show_body(f"Since the returning command\n{changed}\n\n{report}")

    def show_failure(self, failure: SnapshotFailure | None, detail: str | None) -> None:
        """Replace stale detail with the current failed-attempt diagnosis."""
        self._changes = ()
        self.show_body(render_failure(failure, detail))
