"""Offline roundtrip tests for the lean private calibration record document."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bora_workbench._calibration_record import (
    RecordContext,
    RecordError,
    build_record,
    load_record,
    write_record,
)
from bora_workbench._calibration_runner import ModeResult
from bora_workbench._calibration_types import EnvelopeResult, GateResult
from bora_workbench.engine import load_engine_lock
from bora_workbench.profiles import load_catalog
from tests.sample_fixtures import sample


def _target() -> SimpleNamespace:
    """Build a duck-typed calibration target with a real engine lock and fake hardware."""
    lock = load_engine_lock()
    hardware = SimpleNamespace(
        cpu_name="Test CPU",
        cpu_cores=12,
        ram_total_gib=32.0,
        gpu_count=1,
        gpu_name="Test GPU",
        vram_total_gib=8.0,
        os_name="linux",
        backend="cuda",
    )
    return SimpleNamespace(
        config=SimpleNamespace(model=lock["default_model"]), hardware=hardware, lock=lock
    )


def _mode_result() -> ModeResult:
    """Build a coding ModeResult with one balanced cell and one confirmation input."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    envelope = EnvelopeResult("balanced", sample(65536, 41, 100.0), GateResult(True, True, None))
    return ModeResult(
        mode,
        envelope,
        (),
        ((100.0, 102.0),),
    )


def test_record_roundtrips_and_reconstructs_selection(tmp_path) -> None:
    """Build, atomically write, and reload a record with its selection inputs intact."""
    context = RecordContext(_target(), "a" * 32, "test-driver")
    document = build_record(context, _mode_result())
    path = tmp_path / "coding.candidate.json"

    write_record(document, path)
    loaded = load_record(path)

    assert loaded == document
    assert loaded["preference"] == "balanced"
    assert loaded["envelope"]["ctx"] == 65536
    assert loaded["envelope"]["n_cpu_moe"] == 41
    assert loaded["selection_input"]["round_medians"] == [[100.0, 102.0]]
    assert loaded["reserves"]["vram_gib"] == 0.5


def test_record_rejects_tampered_reserves(tmp_path) -> None:
    """Reject a record whose reserves no longer match the pinned calibration constants."""
    context = RecordContext(_target(), "a" * 32, "test-driver")
    document = build_record(context, _mode_result())
    reserves = document["reserves"]
    assert isinstance(reserves, dict)
    reserves["vram_gib"] = 0.3
    with pytest.raises(RecordError, match="reserves"):
        write_record(document, tmp_path / "coding.candidate.json")


def test_reuse_reads_recorded_envelope_and_headroom() -> None:
    """Select the one recorded cell and apply its own reserves at reuse time."""
    from bora_workbench._calibration_reuse import _headroom_for, _recorded_envelope

    document = build_record(RecordContext(_target(), "run-abc123", "test-driver"), _mode_result())
    assert _recorded_envelope(document)["ctx"] == 65536
    assert _headroom_for(document, vram_free_gib=10.0, ram_gib=10.0) == []
    assert _headroom_for(document, vram_free_gib=10.0, ram_gib=3.0) != []
    assert _headroom_for(document, vram_free_gib=1.0, ram_gib=10.0) != []
