"""Derive one deterministic next step from collected facts without performing an action."""

from __future__ import annotations

from dataclasses import dataclass

from bora_workbench.models import ArtifactStatus
from bora_workbench.snapshot import SnapshotFailure, WorkbenchSnapshot


@dataclass(frozen=True, slots=True)
class Suggestion:
    """Present one truthful diagnosis, explanation, and optional exact CLI command."""

    headline: str
    detail: str
    command: str | None = None


def _failure_advice(failure: SnapshotFailure) -> Suggestion:
    """Keep a collection failure primary and offer only a command that can clarify it."""
    if failure.category == "configuration":
        remedy = "Correct the reported configuration value, then refresh the snapshot."
    else:
        remedy = "Resolve the reported local inspection error, then refresh the snapshot."
    command = "bora validate" if failure.category == "content" else None
    if command is not None:
        remedy = "Run validation to print the packaged-content errors, then refresh."
    heading = failure.category.replace("-", " ").title()
    headline = f"{heading} error prevents local inspection."
    return Suggestion(headline, f"{failure.detail}\n{remedy}", command)


def _inspection_advice(snapshot: WorkbenchSnapshot) -> Suggestion | None:
    """Keep unreadable service state from being presented as an empty healthy machine."""
    errors = tuple(error for root in snapshot.service_roots for error in root.inspection.errors)
    if not errors:
        return None
    detail = f"{errors[0]}\nResolve the state inspection error, then refresh the snapshot."
    return Suggestion("Service state could not be read safely.", detail)


def _content_advice(snapshot: WorkbenchSnapshot) -> Suggestion | None:
    """Prioritize blocking packaged-content errors before derived setup state."""
    errors = snapshot.doctor.validation.errors
    if not errors:
        return None
    detail = f"{len(errors)} packaged-content error(s) block trusted mode and model details."
    return Suggestion("Packaged content does not validate.", detail, "bora validate")


def _engine_advice(snapshot: WorkbenchSnapshot) -> Suggestion | None:
    """Recommend the locked installer when the active engine is absent or incompatible."""
    engine = snapshot.doctor.engine
    if engine.is_active and engine.is_compatible:
        return None
    if engine.is_active:
        headline = "The active engine does not match engine.lock."
    else:
        headline = "The pinned engine is not active."
    detail = "Install the exact managed engine selected for this machine."
    return Suggestion(headline, detail, "bora engine install")


def _artifact_problem(statuses: set[ArtifactStatus]) -> str:
    """Describe the strongest receipt-aware problem among incomplete default artifacts."""
    if "wrong-size" in statuses:
        return "Pinned model artifacts have an unexpected size."
    if "present-unverified" in statuses:
        return "Pinned model artifacts are present but need verification."
    return "Pinned model artifacts are missing."


def _model_advice(snapshot: WorkbenchSnapshot) -> Suggestion | None:
    """Recommend pull only for an incomplete model owned by the locked distribution."""
    model = snapshot.model
    if model is None:
        detail = "The snapshot contains no trusted model inspection."
        return Suggestion("Model readiness is unavailable.", detail)
    if not model.is_managed:
        if model.diagnostics or any(item.status == "absent" for item in model.artifacts):
            detail = "Correct the configured external model path, then refresh the snapshot."
            return Suggestion("The user-managed model is unavailable.", detail)
        return None
    if model.is_verified:
        return None
    statuses = {artifact.status for artifact in model.artifacts}
    detail = "Acquire or verify only the artifacts pinned by engine.lock."
    return Suggestion(_artifact_problem(statuses), detail, "bora pull")


def _ui_availability(mode: str) -> str:
    """Describe the fixed current mode contract without claiming for an unknown mode id."""
    if mode == "coding":
        return "integrated UI disabled"
    if mode in {"studio", "vstudio"}:
        return "integrated UI available"
    return "integrated UI availability unknown"


def _service_advice(snapshot: WorkbenchSnapshot) -> Suggestion | None:
    """Describe the first verified live service before considering calibration work."""
    if not snapshot.services:
        return None
    service = snapshot.services[0]
    headline = f"{service.mode} is serving ctx {service.ctx} on 127.0.0.1:{service.port}."
    detail = f"{_ui_availability(service.mode)}; stop the verified service through the CLI."
    return Suggestion(headline, detail, "bora stop")


def _candidate_advice(snapshot: WorkbenchSnapshot) -> Suggestion | None:
    """Select the first valid pending candidate in packaged mode order."""
    for record in snapshot.doctor.records:
        if record.evaluation.candidate_status != "valid":
            continue
        headline = f"A {record.mode_id} calibration candidate is ready."
        detail = "Activation still uses the real calibration confirmation path."
        command = f"bora calibrate --mode {record.mode_id} --activate"
        return Suggestion(headline, detail, command)
    return None


def _calibration_advice(snapshot: WorkbenchSnapshot) -> Suggestion | None:
    """Suggest measuring the first mode without an active record while affirming its baseline."""
    for record in snapshot.doctor.records:
        if record.evaluation.status == "valid":
            continue
        headline = f"{record.mode_id} uses the verified baseline and can run now."
        detail = "Calibration is optional and measures a locally optimized preference cell."
        return Suggestion(headline, detail, f"bora calibrate --mode {record.mode_id}")
    return None


def _ready_advice(snapshot: WorkbenchSnapshot) -> Suggestion:
    """Offer coding only when collected packaged records include that complete mode."""
    mode_ids = {record.mode_id for record in snapshot.doctor.records}
    if "coding" not in mode_ids:
        detail = "The snapshot contains no coding-mode calibration fact."
        return Suggestion("Coding readiness is unavailable.", detail)
    detail = "Engine, model, and active calibration facts are ready for the coding mode."
    return Suggestion("The local workbench is ready.", detail, "bora coding")


def next_step(snapshot: WorkbenchSnapshot | SnapshotFailure) -> Suggestion:
    """Return the first truthful suggestion in the approved deterministic priority order."""
    if isinstance(snapshot, SnapshotFailure):
        return _failure_advice(snapshot)
    choosers = (
        _inspection_advice,
        _content_advice,
        _engine_advice,
        _model_advice,
        _service_advice,
        _candidate_advice,
        _calibration_advice,
    )
    for choose in choosers:
        if suggestion := choose(snapshot):
            return suggestion
    return _ready_advice(snapshot)
