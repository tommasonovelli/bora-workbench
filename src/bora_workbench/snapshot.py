"""Collect synchronous, structured, non-mutating local diagnostics for CLI and TUI.

The collector keeps discovery out of both presentation layers. Its ordering deliberately matches the
historical ``doctor`` command, including resolving the four public roots last, so extracting the
model changes neither the first reported failure nor successful output (specification section 5.11,
D-084).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bora_workbench._calibration_reuse import RecordEvaluation, ReuseQuery, evaluate_record
from bora_workbench.config import Config, ConfigResolution, load_config_details
from bora_workbench.engine import EngineStatus, JsonObject, engine_status, load_engine_lock
from bora_workbench.hardware import HardwareInfo, detect_hardware
from bora_workbench.paths import cache_dir, config_dir, data_dir, state_dir
from bora_workbench.profiles import Catalog, load_catalog
from bora_workbench.validation import ValidationResult, validate_resources


class SnapshotError(RuntimeError):
    """Report an operational snapshot failure not owned by another domain."""


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
