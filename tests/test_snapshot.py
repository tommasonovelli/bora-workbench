"""Tests for structured, presentation-free workbench snapshot collection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import bora_workbench._model_verification as model_verification
import bora_workbench._process_state as process_state
import bora_workbench.engine as engine_module
import bora_workbench.models as models_module
import bora_workbench.process as process_module
import bora_workbench.snapshot as snapshot_module
from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench.config import Config, ConfigError, ConfigResolution, ConfigSources
from bora_workbench.engine import EngineError, EngineStatus
from bora_workbench.hardware import HardwareError, HardwareInfo
from bora_workbench.models import ModelInspection
from bora_workbench.pi_link import ContextWindow, PiInstallation
from bora_workbench.process import ServiceInspection, ServiceState
from bora_workbench.profiles import ContentError
from bora_workbench.validation import ValidationResult
from tests.model_store_fixtures import tiny_lock


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


def _configuration(config: Config | None = None) -> ConfigResolution:
    """Return one all-default configuration resolution."""
    sources = ConfigSources("default", "default", "default", "default", "default")
    return ConfigResolution(config or Config(), Path("config.toml"), sources)


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


def _doctor(config: Config, lock) -> snapshot_module.DoctorSnapshot:
    """Build one complete doctor snapshot for workbench composition tests."""
    record = snapshot_module.ModeRecordSnapshot(
        "coding", RecordEvaluation("missing", None, None, ("no active coding record",))
    )
    return snapshot_module.DoctorSnapshot(
        "0.test",
        _configuration(config),
        _hardware(),
        ValidationResult(()),
        0,
        (record,),
        EngineStatus(False, None, None, None, False, ("not installed",)),
        snapshot_module.PublicPaths(Path("config"), Path("data"), Path("cache"), Path("state")),
        lock,
    )


def _service() -> ServiceState:
    """Return one verified service fact without starting a process."""
    return ServiceState(
        "llama-server",
        4321,
        1.0,
        "llama-server",
        8080,
        "2026-07-29T00:00:00Z",
        "server.log",
        "coding",
        "qwen",
        "b10011",
        None,
        65536,
        33,
        "cuda",
        0,
    )


def test_workbench_snapshot_composes_services_model_pi_and_existing_record(monkeypatch) -> None:
    """Pass already collected facts to shared services without rediscovering them."""
    lock = tiny_lock()
    doctor = _doctor(Config(model="owner/model:file"), lock)
    service = _service()
    inspection = ServiceInspection((service,))
    model = ModelInspection("owner/model:file", True, ())
    installation = PiInstallation(Path("pi"), Path("models.json"))
    context = ContextWindow(65536, "shared context")
    queries = []
    monkeypatch.setattr(snapshot_module, "collect_doctor_snapshot", lambda version: doctor)
    monkeypatch.setattr(snapshot_module, "service_roots", lambda: (Path("state"),))
    monkeypatch.setattr(snapshot_module, "inspect_services", lambda root: inspection)
    monkeypatch.setattr(snapshot_module, "inspect_model", lambda config, selected: model)
    monkeypatch.setattr(snapshot_module, "inspect_pi", lambda: installation)
    monkeypatch.setattr(
        snapshot_module,
        "resolve_context_window",
        lambda query: queries.append(query) or context,
    )

    snapshot = snapshot_module.collect_workbench_snapshot("0.test")

    assert snapshot.doctor is doctor and snapshot.model is model
    assert snapshot.pi_installation is installation and snapshot.pi_context is context
    assert snapshot.services == (service,)
    assert queries[0].services == (service,)
    assert queries[0].coding_record is doctor.records[0].evaluation


def test_invalid_content_yields_a_partial_workbench_snapshot(monkeypatch) -> None:
    """Keep diagnostics usable when validation prevented lock-derived facts."""
    doctor = _doctor(Config(), None)
    monkeypatch.setattr(snapshot_module, "collect_doctor_snapshot", lambda version: doctor)
    monkeypatch.setattr(snapshot_module, "service_roots", lambda: ())
    monkeypatch.setattr(
        snapshot_module, "inspect_pi", lambda: PiInstallation(None, Path("models.json"))
    )

    snapshot = snapshot_module.collect_workbench_snapshot("0.test")

    assert snapshot.model is None and snapshot.pi_context is None
    assert "until packaged content validates" in snapshot.diagnostics[0]


@pytest.mark.parametrize(
    ("error", "category", "exit_code"),
    (
        (ConfigError("bad config"), "configuration", 2),
        (HardwareError("bad hardware"), "hardware", 1),
        (ContentError("bad content"), "content", 1),
        (EngineError("bad engine"), "engine", 1),
        (snapshot_module.SnapshotError("bad paths"), "paths", 1),
        (OSError("bad resource"), "content", 1),
    ),
)
def test_workbench_collection_exposes_structured_failures(
    monkeypatch, error, category, exit_code
) -> None:
    """Preserve expected domain and exit category without choosing presentation."""
    monkeypatch.setattr(
        snapshot_module,
        "collect_doctor_snapshot",
        lambda version: (_ for _ in ()).throw(error),
    )

    with pytest.raises(snapshot_module.WorkbenchCollectionError) as captured:
        snapshot_module.collect_workbench_snapshot("0.test")

    assert captured.value.failure.category == category
    assert captured.value.failure.detail == str(error)
    assert captured.value.failure.exit_code == exit_code


def test_workbench_collection_calls_no_prohibited_effect(tmp_path, monkeypatch) -> None:
    """Compose real read-only inspections while every prohibited effect is armed to fail."""
    config = Config(model="custom/model:file", model_path=tmp_path / "missing.gguf")
    doctor = _doctor(config, tiny_lock())

    def reject(*args, **kwargs):
        """Fail immediately if collection reaches one prohibited side effect."""
        raise AssertionError(f"prohibited effect: {args!r} {kwargs!r}")

    monkeypatch.setattr(snapshot_module, "collect_doctor_snapshot", lambda version: doctor)
    monkeypatch.setattr(snapshot_module, "service_roots", lambda: (tmp_path / "state",))
    monkeypatch.setattr(
        snapshot_module, "inspect_pi", lambda: PiInstallation(None, tmp_path / "models.json")
    )
    for module, name in (
        (httpx, "get"),
        (engine_module, "_sha256"),
        (models_module, "download_file"),
        (models_module, "remember"),
        (model_verification, "_write"),
        (process_state, "write_state"),
        (process_state, "_quarantine"),
        (process_module, "acquire_start_lock"),
    ):
        monkeypatch.setattr(module, name, reject)

    snapshot = snapshot_module.collect_workbench_snapshot("0.test")

    assert snapshot.model is not None
    assert snapshot.model.is_managed is False
    assert snapshot.pi_context is not None
    assert list(tmp_path.iterdir()) == []
