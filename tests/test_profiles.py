"""Tests for catalog loading, record reuse, seed matching, memory gates, and plan identity."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import bora_workbench._calibration_record as record_module
import bora_workbench._calibration_reuse as reuse_module
from bora_workbench._calibration_record import write_record
from bora_workbench._hardware_monitoring import GpuSnapshot
from bora_workbench.config import DEFAULT_MODEL, Config
from bora_workbench.hardware import HardwareInfo
from bora_workbench.profiles import (
    ContentError,
    LaunchRequest,
    PlanError,
    build_launch_plan,
    enforce_memory_gate,
    load_catalog,
)
from tests.content_fixtures import build_valid_content, copy_resource_root, read_json, write_json
from tests.record_fixtures import calibration_document, cuda_hardware


def hardware(backend: str = "cuda", *, ram: float = 32, available: float = 24) -> HardwareInfo:
    """Build deterministic exact hardware measurements for matching tests."""
    is_cuda = backend == "cuda"
    return HardwareInfo(
        "linux",
        "test",
        "Test CPU",
        12,
        ram,
        available,
        backend,  # type: ignore[arg-type]
        1 if is_cuda else 0,
        0 if is_cuda else None,
        "Test GPU" if is_cuda else None,
        8 if is_cuda else None,
        7 if is_cuda else None,
    )


def request(model: str, mode: str = "coding") -> LaunchRequest:
    """Build one launch request with an already resolved physical path."""
    config = Config(model=model, model_path=Path("model.gguf"))
    return LaunchRequest(config, mode, Path("/resolved/model.gguf"))


def install_cuda_record(tmp_path, monkeypatch) -> None:
    """Write one valid CUDA coding record into an isolated managed data directory."""
    monkeypatch.setattr(record_module, "data_dir", lambda: tmp_path / "data")
    write_record(calibration_document(cuda_hardware()), record_module.record_path("coding"))


def test_packaged_catalog_loads_modes_and_allows_no_profiles() -> None:
    """Load verified mode behavior while preserving the valid empty-profile state."""
    catalog = load_catalog()

    assert tuple(mode.id for mode in catalog.modes) == ("coding", "studio", "vstudio")
    assert catalog.profiles == ()
    coding = catalog.mode("coding")
    assert coding is not None
    assert coding.services.ui is False
    assert coding.services.vision is False
    assert coding.sampling.temp == 0.6
    assert coding.sampling.top_p == 0.95
    assert coding.sampling.top_k == 20


def test_runtime_models_are_frozen(tmp_path) -> None:
    """Prevent validated content from being mutated after catalog construction."""
    files = build_valid_content(tmp_path)
    catalog = load_catalog(files.root)

    with pytest.raises(FrozenInstanceError):
        catalog.modes[0].id = "changed"  # type: ignore[misc]


def test_synthetic_profile_loads_exact_envelope(tmp_path) -> None:
    """Construct immutable profile values only after full validation succeeds."""
    files = build_valid_content(tmp_path)

    profile = load_catalog(files.root).profiles[0]

    assert profile.id == "synthetic-profile"
    assert profile.is_engine_compatible is True
    assert profile.match.ram_gib.minimum_gib == 31
    assert profile.match.vram_gib.maximum_gib == 9
    envelope = profile.envelope_for("coding")
    assert envelope is not None
    assert envelope.ctx == 8192
    assert envelope.n_cpu_moe == 48
    assert envelope.tok_s is not None
    assert envelope.tok_s.median == 3


def test_loader_refuses_invalid_content(tmp_path) -> None:
    """Never construct runtime models from a schema-invalid mode."""
    root = copy_resource_root(tmp_path)
    path = root / "content/modes/coding.json"
    mode = read_json(path)
    mode["sampling"]["top_p"] = 0  # type: ignore[index]
    write_json(path, mode)

    with pytest.raises(ContentError, match="top_p"):
        load_catalog(root)


@pytest.mark.parametrize("backend", ["cuda", "cpu"])
def test_shared_profile_is_seed_only_even_inside_its_exact_class(tmp_path, backend) -> None:
    """Never transfer a measured envelope to another machine without local calibration."""
    files = build_valid_content(tmp_path, backend=backend)
    detected = hardware(backend)
    detected = replace(
        detected,
        cpu_name="Different CPU",
        gpu_name="Different GPU" if backend == "cuda" else None,
    )
    plan = build_launch_plan(request("owner/model:file"), load_catalog(files.root), detected)

    assert plan.profile_id is None
    assert plan.ctx == 8192
    assert plan.n_cpu_moe == (48 if backend == "cuda" else None)
    assert any("reference-only" in warning for warning in plan.warnings)


def test_valid_local_record_steers_the_launch_plan(tmp_path, monkeypatch) -> None:
    """Use the locally measured envelope immediately once every identity matches."""
    install_cuda_record(tmp_path, monkeypatch)
    monkeypatch.setattr(
        reuse_module, "query_gpu_snapshot", lambda index: GpuSnapshot(8, 7, "test-driver", ())
    )

    plan = build_launch_plan(request(DEFAULT_MODEL), load_catalog(), cuda_hardware())

    assert plan.profile_id == "local-calibration-record"
    assert (plan.ctx, plan.n_cpu_moe) == (131072, 38)
    assert plan.warnings == ()


def test_stale_local_record_falls_back_with_diagnostics(tmp_path, monkeypatch) -> None:
    """Explain exactly why an incompatible record was ignored before using the baseline."""
    install_cuda_record(tmp_path, monkeypatch)
    monkeypatch.setattr(
        reuse_module, "query_gpu_snapshot", lambda index: GpuSnapshot(8, 7, "620.00", ())
    )

    plan = build_launch_plan(request(DEFAULT_MODEL), load_catalog(), cuda_hardware())

    assert plan.profile_id is None
    assert (plan.ctx, plan.n_cpu_moe) == (8192, 48)
    assert "non-optimized" in plan.warnings[0]
    assert any("GPU driver changed" in warning for warning in plan.warnings)


def test_empty_catalog_uses_declared_default_baseline() -> None:
    """Keep coding usable without presenting the spike baseline as calibrated."""
    plan = build_launch_plan(request(DEFAULT_MODEL), load_catalog(), hardware())

    assert plan.profile_id is None
    assert plan.ctx == 8192
    assert plan.n_cpu_moe == 48
    assert "non-optimized" in plan.warnings[0]


def test_outside_profile_class_never_uses_nearest_match(tmp_path) -> None:
    """Use fallback rather than extrapolating from a nearby nominal RAM class."""
    files = build_valid_content(tmp_path)
    plan = build_launch_plan(
        request("owner/model:file"), load_catalog(files.root), hardware(ram=64)
    )

    assert plan.profile_id is None
    assert "no local calibration record" in plan.warnings[0].casefold()


def test_different_model_gets_strengthened_fallback_warning() -> None:
    """Never attribute default-model calibration or guarantees to another identity."""
    plan = build_launch_plan(request("other/model:file"), load_catalog(), hardware("cpu"))

    assert plan.profile_id is None
    assert plan.n_cpu_moe is None
    assert "without performance or compatibility guarantees" in plan.warnings[0]


@pytest.mark.parametrize("mode_id", ["studio", "vstudio"])
def test_profile_without_requested_mode_falls_back(tmp_path, mode_id) -> None:
    """Treat a valid partial profile as uncalibrated for either uncovered UI mode."""
    files = build_valid_content(tmp_path)
    plan = build_launch_plan(
        request("owner/model:file", mode_id), load_catalog(files.root), hardware()
    )

    assert plan.profile_id is None
    assert plan.mode.id == mode_id


@pytest.mark.parametrize("ram,available", [(27.9, 22), (28, 21.9)])
def test_default_model_memory_gate_checks_total_and_available(ram, available) -> None:
    """Stop the default model before resolution when either normative RAM threshold fails."""
    with pytest.raises(PlanError, match="28 GiB total RAM and 22 GiB available RAM"):
        enforce_memory_gate(Config(), hardware(ram=ram, available=available), force=False)


def test_default_model_memory_gate_accepts_exact_thresholds() -> None:
    """Accept the inclusive total and available RAM boundaries required by section 5.5."""
    enforce_memory_gate(Config(), hardware(ram=28, available=22), force=False)


def test_force_bypasses_only_memory_gate_and_other_models_have_no_fixed_gate() -> None:
    """Allow the explicit bypass and avoid applying default-model numbers to other models."""
    low_memory = hardware(ram=1, available=1)

    enforce_memory_gate(Config(), low_memory, force=True)
    enforce_memory_gate(Config(model="other/model:file"), low_memory, force=False)
