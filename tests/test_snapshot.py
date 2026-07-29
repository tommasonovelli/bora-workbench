"""Tests for structured, presentation-free workbench snapshot collection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import bora_workbench.snapshot as snapshot_module
from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench.config import Config, ConfigResolution, ConfigSources
from bora_workbench.engine import EngineStatus
from bora_workbench.hardware import HardwareInfo
from bora_workbench.validation import ValidationResult


def _hardware() -> HardwareInfo:
    """Return deterministic CPU facts without probing the host."""
    return HardwareInfo(
        "linux",
        "test-version",
        "Test CPU",
        12,
        32.0,
        24.0,
        "cpu",
        0,
        None,
        None,
        None,
        None,
        ("test hardware warning",),
    )


def _configuration() -> ConfigResolution:
    """Return one all-default configuration resolution."""
    sources = ConfigSources("default", "default", "default", "default", "default")
    return ConfigResolution(Config(), Path("config.toml"), sources)


_COLLECTOR_FUNCTIONS = (
    ("configuration", "load_config_details", "config"),
    ("hardware", "detect_hardware", "hardware"),
    ("validation", "validate_resources", "validate"),
    ("catalog", "load_catalog", "catalog"),
    ("lock", "load_engine_lock", "lock"),
    ("engine", "engine_status", "engine"),
)

_COLLECTION_ORDER = (
    "config",
    "hardware",
    "validate",
    "catalog",
    "lock",
    "record:coding",
    "record:studio",
    "engine",
    "path:config",
    "path:data",
    "path:cache",
    "path:state",
)


def _install_collector_fakes(monkeypatch, calls: list[str]) -> SimpleNamespace:
    """Install deterministic collaborators and return the expected identity objects."""
    expected = SimpleNamespace(
        configuration=_configuration(),
        hardware=_hardware(),
        validation=ValidationResult(()),
        catalog=SimpleNamespace(
            modes=(SimpleNamespace(id="coding"), SimpleNamespace(id="studio")),
            profiles=(SimpleNamespace(is_engine_compatible=True),),
        ),
        lock={"release": "b10011"},
        engine=EngineStatus(False, None, None, None, False, ("not installed",)),
    )
    for name, function, label in _COLLECTOR_FUNCTIONS:
        value = getattr(expected, name)
        monkeypatch.setattr(
            snapshot_module, function, lambda label=label, value=value: calls.append(label) or value
        )
    monkeypatch.setattr(
        snapshot_module,
        "evaluate_record",
        lambda query: (
            calls.append(f"record:{query.mode.id}") or RecordEvaluation("missing", None, None, ())
        ),
    )
    for name in ("config", "data", "cache", "state"):
        monkeypatch.setattr(
            snapshot_module,
            f"{name}_dir",
            lambda name=name: calls.append(f"path:{name}") or Path(name),
        )
    return expected


def test_doctor_snapshot_collects_in_historical_order_without_a_console(monkeypatch) -> None:
    """Keep paths last and expose every prior doctor value as structured data."""
    calls: list[str] = []
    expected = _install_collector_fakes(monkeypatch, calls)

    snapshot = snapshot_module.collect_doctor_snapshot("0.test")

    assert snapshot.version == "0.test"
    assert snapshot.configuration is expected.configuration
    assert snapshot.hardware is expected.hardware and snapshot.validation is expected.validation
    assert snapshot.compatible_profiles == 1
    assert [record.mode_id for record in snapshot.records] == ["coding", "studio"]
    assert snapshot.engine is expected.engine and snapshot.lock is expected.lock
    assert calls == list(_COLLECTION_ORDER)


def test_invalid_content_skips_catalog_and_record_collection(monkeypatch) -> None:
    """Preserve doctor's behavior of reporting validation before derived content facts."""
    issue = SimpleNamespace(severity="error")
    validation = SimpleNamespace(errors=(issue,))
    monkeypatch.setattr(snapshot_module, "load_config_details", _configuration)
    monkeypatch.setattr(snapshot_module, "detect_hardware", _hardware)
    monkeypatch.setattr(snapshot_module, "validate_resources", lambda: validation)
    monkeypatch.setattr(
        snapshot_module, "load_catalog", lambda: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(
        snapshot_module, "load_engine_lock", lambda: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(
        snapshot_module,
        "engine_status",
        lambda: EngineStatus(False, None, None, None, False, ("not installed",)),
    )
    for name in ("config", "data", "cache", "state"):
        monkeypatch.setattr(snapshot_module, f"{name}_dir", lambda: Path("root"))

    snapshot = snapshot_module.collect_doctor_snapshot("0.test")

    assert snapshot.records == ()
    assert snapshot.lock is None
    assert snapshot.compatible_profiles == 0
