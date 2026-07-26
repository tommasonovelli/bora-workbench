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
    """Build a coding ModeResult with three gated envelopes and one confirmation input."""
    mode = load_catalog().mode("coding")
    assert mode is not None

    def envelope(preference: str, ctx: int, n_cpu_moe: int) -> EnvelopeResult:
        return EnvelopeResult(
            preference, sample(ctx, n_cpu_moe, 100.0), GateResult(True, True, None)
        )

    envelopes = {
        "fast": envelope("fast", 65536, 41),
        "balanced": envelope("balanced", 65536, 41),
        "max_context": envelope("max_context", 131072, 37),
    }
    return ModeResult(
        mode, envelopes, (), {"fast": ((100.0, 102.0),), "balanced": (), "max_context": ()}
    )


def test_record_roundtrips_and_reconstructs_selection(tmp_path) -> None:
    """Build, atomically write, and reload a record with its selection inputs intact."""
    context = RecordContext(_target(), "run-abc123", "balanced", "test-driver")
    document = build_record(context, _mode_result())
    path = tmp_path / "coding.candidate.json"

    write_record(document, path)
    loaded = load_record(path)

    assert loaded == document
    assert loaded["active_preference"] == "balanced"
    assert loaded["envelopes"]["max_context"]["ctx"] == 131072
    assert loaded["envelopes"]["fast"]["n_cpu_moe"] == 41
    assert loaded["selection_inputs"]["fast"]["round_medians"] == [[100.0, 102.0]]
    assert loaded["reserves"]["vram_gib"] == 0.5


def test_record_rejects_tampered_reserves(tmp_path) -> None:
    """Reject a record whose reserves no longer match the pinned calibration constants."""
    context = RecordContext(_target(), "run-abc123", "balanced", "test-driver")
    document = build_record(context, _mode_result())
    reserves = document["reserves"]
    assert isinstance(reserves, dict)
    reserves["vram_gib"] = 0.3
    with pytest.raises(RecordError, match="reserves"):
        write_record(document, tmp_path / "coding.candidate.json")


def test_reuse_reads_active_envelope_and_headroom() -> None:
    """Select the active envelope and apply the record's own reserves at reuse time."""
    from bora_workbench._calibration_reuse import _active_envelope, _headroom_for

    document = build_record(
        RecordContext(_target(), "run-abc123", "max_context", "test-driver"), _mode_result()
    )
    assert _active_envelope(document)["ctx"] == 131072
    assert _headroom_for(document, vram_free_gib=10.0, ram_gib=10.0) == []
    assert _headroom_for(document, vram_free_gib=10.0, ram_gib=3.0) != []
    assert _headroom_for(document, vram_free_gib=1.0, ram_gib=10.0) != []
