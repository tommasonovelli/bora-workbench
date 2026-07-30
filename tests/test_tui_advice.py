"""Truth-table tests for deterministic snapshot-only TUI advice."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from bora_workbench._calibration_reuse import CandidateStatus, RecordEvaluation, RecordStatus
from bora_workbench.config import Config, ConfigResolution, ConfigSources
from bora_workbench.engine import EngineStatus
from bora_workbench.hardware import HardwareInfo
from bora_workbench.models import ArtifactInspection, ArtifactStatus, ModelInspection
from bora_workbench.pi_link import ContextWindow, PiInstallation
from bora_workbench.process import ServiceInspection, ServiceState
from bora_workbench.snapshot import (
    DoctorSnapshot,
    ModeRecordSnapshot,
    PublicPaths,
    ServiceRootSnapshot,
    SnapshotFailure,
    SnapshotFailureCategory,
    WorkbenchSnapshot,
)
from bora_workbench.tui.advice import next_step
from bora_workbench.tui.screens.overview import render_snapshot
from bora_workbench.validation import ValidationIssue, ValidationResult

_VALID_CONTENT = ValidationResult(())


def _record(
    mode_id: str,
    status: RecordStatus = "valid",
    candidate_status: CandidateStatus = "missing",
) -> ModeRecordSnapshot:
    """Build one packaged-mode record fact with optional pending-candidate state."""
    evaluation = RecordEvaluation(status, 8192, 0, (), candidate_status)
    return ModeRecordSnapshot(mode_id, evaluation)


def _engine(is_active: bool = True, is_compatible: bool = True) -> EngineStatus:
    """Build one managed-engine state for an advice scenario."""
    release = "b10011" if is_active else None
    backend = "cpu" if is_active else None
    executable = Path("llama-server") if is_active else None
    return EngineStatus(is_active, release, backend, executable, is_compatible)


def _model(status: ArtifactStatus = "receipt-verified") -> ModelInspection:
    """Build one receipt-aware managed-model state with a single locked artifact label."""
    size = None if status == "absent" else 10
    artifact = ArtifactInspection("weights", Path("model.gguf"), "managed-store", status, size, 10)
    return ModelInspection("locked-model", True, (artifact,))


def _service(mode: str = "coding") -> ServiceState:
    """Build one verified live service fact without inspecting a process."""
    return ServiceState(
        "llama-server",
        123,
        1.0,
        "llama-server",
        8080,
        "2026-07-29T00:00:00Z",
        "server.log",
        mode,
        "engine",
        "qwen",
        "b10011",
        None,
        65536,
        33,
        "cpu",
        None,
    )


def _doctor(
    validation: ValidationResult,
    engine: EngineStatus,
    records: tuple[ModeRecordSnapshot, ...],
) -> DoctorSnapshot:
    """Build supporting doctor facts whose values do not trigger unrequested side effects."""
    configuration = ConfigResolution(
        Config(),
        Path("config.toml"),
        ConfigSources(*(("default",) * len(fields(ConfigSources)))),
    )
    hardware = HardwareInfo(
        "linux", "test", "Test CPU", 12, 32.0, 24.0, "cpu", 0, None, None, None, None
    )
    paths = PublicPaths(Path("config"), Path("data"), Path("cache"), Path("state"))
    return DoctorSnapshot(
        "0.test", configuration, hardware, validation, 1, records, engine, paths, {}
    )


def _snapshot(
    *,
    validation: ValidationResult = _VALID_CONTENT,
    engine: EngineStatus | None = None,
    model: ModelInspection | None = None,
    records: tuple[ModeRecordSnapshot, ...] | None = None,
    services: tuple[ServiceState, ...] = (),
    service_errors: tuple[str, ...] = (),
) -> WorkbenchSnapshot:
    """Compose one complete advice input while allowing each priority fact to vary."""
    selected_records = (_record("coding"), _record("studio")) if records is None else records
    doctor = _doctor(validation, engine or _engine(), selected_records)
    roots = ()
    if services or service_errors:
        inspection = ServiceInspection(services, errors=service_errors)
        roots = (ServiceRootSnapshot(Path("state"), inspection),)
    selected_model = _model() if model is None else model
    return WorkbenchSnapshot(
        doctor,
        roots,
        selected_model,
        PiInstallation(None, Path("models.json")),
        ContextWindow(8192, "test baseline"),
    )


@pytest.mark.parametrize(
    ("category", "expected_command"),
    (
        ("configuration", None),
        ("hardware", None),
        ("content", "bora validate"),
        ("engine", None),
        ("paths", None),
        ("services", None),
        ("model", None),
        ("pi", None),
    ),
)
def test_collection_failures_remain_primary(
    category: SnapshotFailureCategory, expected_command: str | None
) -> None:
    """Show the reported collection remedy without inventing unsafe repair commands."""
    exit_code = 2 if category == "configuration" else 1
    failure = SnapshotFailure(category, "specific local failure", exit_code)

    suggestion = next_step(failure)

    assert "specific local failure" in suggestion.detail
    assert suggestion.command == expected_command


def test_unreadable_service_state_outranks_other_snapshot_facts() -> None:
    """Treat a partial state-inspection failure as unknown rather than as no service."""
    issue = ValidationIssue("error", "engine.lock", "$.release", "invalid release")
    snapshot = _snapshot(
        validation=ValidationResult((issue,)), service_errors=("services.json is unreadable",)
    )

    suggestion = next_step(snapshot)

    assert suggestion.command is None
    assert "could not be read safely" in suggestion.headline
    assert "services.json is unreadable" in suggestion.detail
    assert "0 running, 0 stale, 1 unreadable" in render_snapshot(snapshot)


def test_content_errors_outrank_every_derived_setup_fact() -> None:
    """Recommend validation before an absent engine, model, service, or candidate."""
    issue = ValidationIssue("error", "engine.lock", "$.release", "invalid release")
    candidate = (_record("coding", "candidate", "valid"),)
    snapshot = _snapshot(
        validation=ValidationResult((issue,)),
        engine=_engine(False, False),
        model=_model("absent"),
        records=candidate,
        services=(_service(),),
    )

    suggestion = next_step(snapshot)

    assert suggestion.command == "bora validate"
    assert "does not validate" in suggestion.headline


@pytest.mark.parametrize(
    ("engine", "headline"),
    ((_engine(False, False), "not active"), (_engine(True, False), "does not match")),
)
def test_engine_problem_outranks_model_and_runtime_facts(engine, headline) -> None:
    """Install the exact engine before considering model, service, or calibration state."""
    candidate = (_record("coding", "candidate", "valid"),)
    snapshot = _snapshot(
        engine=engine, model=_model("wrong-size"), records=candidate, services=(_service(),)
    )

    suggestion = next_step(snapshot)

    assert suggestion.command == "bora engine install"
    assert headline in suggestion.headline


@pytest.mark.parametrize(
    ("status", "headline"),
    (
        ("absent", "missing"),
        ("wrong-size", "unexpected size"),
        ("present-unverified", "need verification"),
    ),
)
def test_incomplete_default_model_outranks_service(status: ArtifactStatus, headline: str) -> None:
    """Use pull for every incomplete locked-artifact state before lower-priority advice."""
    snapshot = _snapshot(model=_model(status), services=(_service(),))

    suggestion = next_step(snapshot)

    assert suggestion.command == "bora pull"
    assert headline in suggestion.headline


def test_custom_model_never_receives_pull_advice() -> None:
    """Skip locked acquisition for a user-managed external model."""
    artifact = ArtifactInspection(
        "custom model", Path("custom.gguf"), "user-managed", "present-unverified", 10, None
    )
    custom = ModelInspection("custom/model", False, (artifact,))
    snapshot = _snapshot(model=custom, records=(_record("coding", "missing"),))

    suggestion = next_step(snapshot)

    assert suggestion.command == "bora calibrate --mode coding"
    assert suggestion.command != "bora pull"


def test_absent_custom_model_has_no_managed_repair_command() -> None:
    """Describe an unavailable external path without claiming bora can acquire it."""
    artifact = ArtifactInspection(
        "custom model", Path("missing.gguf"), "user-managed", "absent", None, None
    )
    custom = ModelInspection("custom/model", False, (artifact,))

    suggestion = next_step(_snapshot(model=custom))

    assert suggestion.command is None
    assert "user-managed model is unavailable" in suggestion.headline


@pytest.mark.parametrize(
    ("mode", "ui_text"),
    (
        ("coding", "UI disabled"),
        ("studio", "UI available"),
        ("vstudio", "UI available"),
        ("legacy", "availability unknown"),
    ),
)
def test_live_service_reports_mode_port_and_ui_before_candidate(mode: str, ui_text: str) -> None:
    """Describe the first verified service and choose stop before pending calibration."""
    records = (_record("coding", "valid", "valid"), _record("studio"))
    snapshot = _snapshot(records=records, services=(_service(mode),))

    suggestion = next_step(snapshot)

    assert suggestion.command == "bora stop"
    assert mode in suggestion.headline and "127.0.0.1:8080" in suggestion.headline
    assert ui_text in suggestion.detail


def test_first_pending_candidate_wins_in_packaged_mode_order() -> None:
    """Break candidate ties by the immutable order already carried by the snapshot."""
    records = (
        _record("studio", "valid", "valid"),
        _record("coding", "valid", "valid"),
    )

    suggestion = next_step(_snapshot(records=records))

    assert suggestion.command == "bora calibrate --mode studio --activate"
    assert "real calibration confirmation" in suggestion.detail


def test_first_mode_without_active_record_gets_calm_baseline_advice() -> None:
    """State that launch works before suggesting optional local calibration."""
    records = (_record("studio", "missing"), _record("coding", "missing"))

    suggestion = next_step(_snapshot(records=records))

    assert suggestion.command == "bora calibrate --mode studio"
    assert "verified baseline" in suggestion.headline
    assert "can run now" in suggestion.headline


def test_complete_setup_suggests_coding() -> None:
    """Offer coding only after higher-priority collected facts are complete."""
    suggestion = next_step(_snapshot())

    assert suggestion.command == "bora coding"
    assert suggestion.headline == "The local workbench is ready."
