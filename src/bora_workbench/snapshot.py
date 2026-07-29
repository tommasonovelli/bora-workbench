"""Collect synchronous, structured, non-mutating local diagnostics for CLI and TUI.

The collector keeps discovery out of both presentation layers. Its ordering deliberately matches the
historical ``doctor`` command, including resolving the four public roots last, so extracting the
model changes neither the first reported failure nor successful output (specification section 5.11,
D-084).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bora_workbench._calibration_reuse import (
    RecordEvaluation,
    RecordStatus,
    ReuseQuery,
    evaluate_record,
)
from bora_workbench.calibration import service_roots
from bora_workbench.config import Config, ConfigError, ConfigResolution, load_config_details
from bora_workbench.engine import (
    EngineError,
    EngineStatus,
    JsonObject,
    engine_status,
    load_engine_lock,
)
from bora_workbench.hardware import HardwareError, HardwareInfo, detect_hardware
from bora_workbench.models import ModelInspection, inspect_model
from bora_workbench.paths import cache_dir, config_dir, data_dir, state_dir
from bora_workbench.pi_link import (
    ContextWindow,
    ContextWindowQuery,
    PiInstallation,
    inspect_pi,
    resolve_context_window,
)
from bora_workbench.process import ServiceInspection, ServiceState, inspect_services
from bora_workbench.profiles import Catalog, ContentError, load_catalog
from bora_workbench.validation import ValidationResult, validate_resources


class SnapshotError(RuntimeError):
    """Report an operational snapshot failure not owned by another domain."""


SnapshotFailureCategory = Literal[
    "configuration", "hardware", "content", "engine", "paths", "services", "model", "pi"
]
_RECORD_LABELS: dict[RecordStatus, str] = {
    "valid": "active",
    "missing": "absent",
    "candidate": "candidate",
    "superseded": "superseded",
    "invalid": "invalid",
    "incompatible": "incompatible",
    "insufficient-headroom": "insufficient headroom",
}


def record_display_label(status: RecordStatus) -> str:
    """Return the one CLI/TUI label approved for a record evaluation state."""
    return _RECORD_LABELS[status]


@dataclass(frozen=True, slots=True)
class SnapshotFailure:
    """Describe an expected collection failure for non-CLI presentation."""

    category: SnapshotFailureCategory
    detail: str
    exit_code: Literal[1, 2]


class WorkbenchCollectionError(RuntimeError):
    """Carry one structured collection failure out of the synchronous collector."""

    def __init__(self, failure: SnapshotFailure) -> None:
        """Retain the category and contractual exit class without rendering it."""
        super().__init__(failure.detail)
        self.failure = failure


@dataclass(frozen=True, slots=True)
class PublicPaths:
    """Hold the four computed public roots without creating any of them."""

    config: Path
    data: Path
    cache: Path
    state: Path


@dataclass(frozen=True, slots=True)
class ModeRecordSnapshot:
    """Pair one packaged mode id with its local record evaluation."""

    mode_id: str
    evaluation: RecordEvaluation


@dataclass(frozen=True, slots=True)
class DoctorSnapshot:
    """Contain every value rendered by ``bora doctor`` and no presentation state."""

    version: str
    configuration: ConfigResolution
    hardware: HardwareInfo
    validation: ValidationResult
    compatible_profiles: int
    records: tuple[ModeRecordSnapshot, ...]
    engine: EngineStatus
    paths: PublicPaths
    lock: JsonObject | None


@dataclass(frozen=True, slots=True)
class ServiceRootSnapshot:
    """Keep one read-only service inspection associated with its source root."""

    root: Path
    inspection: ServiceInspection


@dataclass(frozen=True, slots=True)
class WorkbenchSnapshot:
    """Compose all local facts consumed by the read-only TUI screens."""

    doctor: DoctorSnapshot
    service_roots: tuple[ServiceRootSnapshot, ...]
    model: ModelInspection | None
    pi_installation: PiInstallation
    pi_context: ContextWindow | None
    diagnostics: tuple[str, ...] = ()

    @property
    def services(self) -> tuple[ServiceState, ...]:
        """Flatten verified live services across current and unrotated trial roots."""
        return tuple(service for root in self.service_roots for service in root.inspection.services)


def _record_snapshots(
    config: Config, hardware: HardwareInfo, catalog: Catalog
) -> tuple[JsonObject, tuple[ModeRecordSnapshot, ...]]:
    """Evaluate every packaged mode against one already detected machine."""
    lock = load_engine_lock()
    records = tuple(
        ModeRecordSnapshot(mode.id, evaluate_record(ReuseQuery(config, mode, hardware, lock)))
        for mode in catalog.modes
    )
    return lock, records


def _configuration() -> ConfigResolution:
    """Load configuration while naming an unavailable platform path operationally."""
    try:
        return load_config_details()
    except RuntimeError as error:
        raise SnapshotError(f"cannot resolve configuration path: {error}") from error


def _public_paths() -> PublicPaths:
    """Compute the public roots last without creating or probing them."""
    try:
        return PublicPaths(config_dir(), data_dir(), cache_dir(), state_dir())
    except (OSError, RuntimeError) as error:
        raise SnapshotError(f"cannot resolve public paths: {error}") from error


def collect_doctor_snapshot(version: str) -> DoctorSnapshot:
    """Collect doctor diagnostics in the established failure and probe order."""
    configuration = _configuration()
    hardware = detect_hardware()
    validation = validate_resources()
    compatible_profiles = 0
    records: tuple[ModeRecordSnapshot, ...] = ()
    lock: JsonObject | None = None
    if not validation.errors:
        catalog = load_catalog()
        compatible_profiles = sum(profile.is_engine_compatible for profile in catalog.profiles)
        lock, records = _record_snapshots(configuration.config, hardware, catalog)
    managed_engine = engine_status()
    paths = _public_paths()
    return DoctorSnapshot(
        version,
        configuration,
        hardware,
        validation,
        compatible_profiles,
        records,
        managed_engine,
        paths,
        lock,
    )


def _collection_error(
    category: SnapshotFailureCategory, detail: str, exit_code: Literal[1, 2]
) -> WorkbenchCollectionError:
    """Build one structured expected failure without choosing terminal presentation."""
    return WorkbenchCollectionError(SnapshotFailure(category, detail, exit_code))


def _workbench_doctor(version: str) -> DoctorSnapshot:
    """Collect the doctor core while preserving its expected failure categories."""
    try:
        return collect_doctor_snapshot(version)
    except ConfigError as error:
        raise _collection_error("configuration", str(error), 2) from error
    except HardwareError as error:
        raise _collection_error("hardware", str(error), 1) from error
    except ContentError as error:
        raise _collection_error("content", str(error), 1) from error
    except EngineError as error:
        raise _collection_error("engine", str(error), 1) from error
    except SnapshotError as error:
        raise _collection_error("paths", str(error), 1) from error
    except OSError as error:
        raise _collection_error("content", str(error), 1) from error


def _service_root_snapshots() -> tuple[ServiceRootSnapshot, ...]:
    """Inspect every current service root without invoking status cleanup."""
    try:
        roots = service_roots()
        return tuple(ServiceRootSnapshot(root, inspect_services(root)) for root in roots)
    except (OSError, RuntimeError) as error:
        raise _collection_error("services", str(error), 1) from error


def _pi_installation() -> PiInstallation:
    """Inspect pi without running it and classify an unavailable PATH operationally."""
    try:
        return inspect_pi()
    except OSError as error:
        raise _collection_error("pi", str(error), 1) from error


def _coding_evaluation(doctor: DoctorSnapshot) -> RecordEvaluation | None:
    """Return the already collected coding record evaluation, if content supplied it."""
    record = next((item for item in doctor.records if item.mode_id == "coding"), None)
    return None if record is None else record.evaluation


def _model_inspection(doctor: DoctorSnapshot) -> ModelInspection:
    """Inspect the locked model while retaining a model-specific failure category."""
    assert doctor.lock is not None
    try:
        return inspect_model(doctor.configuration.config, doctor.lock)
    except EngineError as error:
        raise _collection_error("model", str(error), 1) from error


def _pi_context(doctor: DoctorSnapshot, services: tuple[ServiceState, ...]) -> ContextWindow:
    """Resolve D-082 from already collected service and coding-record facts."""
    query = ContextWindowQuery(
        doctor.configuration.config.llama_port,
        services,
        _coding_evaluation(doctor),
    )
    try:
        return resolve_context_window(query)
    except EngineError as error:
        raise _collection_error("pi", str(error), 1) from error


def collect_workbench_snapshot(version: str) -> WorkbenchSnapshot:
    """Compose all read-only workbench data or raise one structured expected failure."""
    doctor = _workbench_doctor(version)
    roots = _service_root_snapshots()
    installation = _pi_installation()
    if doctor.lock is None:
        diagnostic = "model and pi context are unavailable until packaged content validates"
        return WorkbenchSnapshot(doctor, roots, None, installation, None, (diagnostic,))
    services = tuple(service for root in roots for service in root.inspection.services)
    model = _model_inspection(doctor)
    context = _pi_context(doctor, services)
    return WorkbenchSnapshot(doctor, roots, model, installation, context)
