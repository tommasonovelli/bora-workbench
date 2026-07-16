"""Tests for exact profile matching, fallback, memory gates, and launch-plan identity."""

from pathlib import Path

import pytest

from qwen_launcher.config import DEFAULT_MODEL, Config
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import (
    LaunchRequest,
    PlanError,
    build_launch_plan,
    enforce_memory_gate,
    load_catalog,
)
from tests.content_fixtures import build_valid_content


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


@pytest.mark.parametrize("backend", ["cuda", "cpu"])
def test_exact_profile_matches_accepted_report(tmp_path, backend) -> None:
    """Select the calibrated CUDA or CPU envelope only inside its exact class."""
    files = build_valid_content(tmp_path, backend=backend)
    plan = build_launch_plan(
        request("owner/model:file"), load_catalog(files.root), hardware(backend)
    )

    assert plan.profile_id == "synthetic-profile"
    assert plan.ctx == 8192
    assert plan.n_cpu_moe == (48 if backend == "cuda" else None)
    assert plan.warnings == ()


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
    assert "no calibrated profile" in plan.warnings[0].casefold()


def test_different_model_gets_strengthened_fallback_warning() -> None:
    """Never attribute default-model calibration or guarantees to another identity."""
    plan = build_launch_plan(request("other/model:file"), load_catalog(), hardware("cpu"))

    assert plan.profile_id is None
    assert plan.n_cpu_moe is None
    assert "without performance or compatibility guarantees" in plan.warnings[0]


def test_profile_without_requested_mode_falls_back(tmp_path) -> None:
    """Treat a valid partial profile as uncalibrated for modes it does not cover."""
    files = build_valid_content(tmp_path)
    plan = build_launch_plan(
        request("owner/model:file", "studio"), load_catalog(files.root), hardware()
    )

    assert plan.profile_id is None
    assert plan.mode.id == "studio"


@pytest.mark.parametrize("ram,available", [(27.9, 24), (28, 23.9)])
def test_default_model_memory_gate_checks_total_and_available(ram, available) -> None:
    """Stop the default model before resolution when either normative RAM threshold fails."""
    with pytest.raises(PlanError, match="28 GiB total RAM"):
        enforce_memory_gate(Config(), hardware(ram=ram, available=available), force=False)


def test_force_bypasses_only_memory_gate_and_other_models_have_no_fixed_gate() -> None:
    """Allow the explicit bypass and avoid applying default-model numbers to other models."""
    low_memory = hardware(ram=1, available=1)

    enforce_memory_gate(Config(), low_memory, force=True)
    enforce_memory_gate(Config(model="other/model:file"), low_memory, force=False)
