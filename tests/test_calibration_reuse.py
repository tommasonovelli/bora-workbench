"""Offline tests for record reuse: identity invalidation and headroom (spec 5.5)."""

from __future__ import annotations

import copy
from dataclasses import replace

import qwen_launcher._calibration_record as record_module
import qwen_launcher._calibration_reuse as reuse_module
from qwen_launcher._calibration_record import build_record, candidate_record_path, write_record
from qwen_launcher._calibration_reuse import ReuseQuery, evaluate_record
from qwen_launcher._hardware_monitoring import GpuSnapshot
from qwen_launcher.config import Config
from qwen_launcher.engine import load_engine_lock
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import (
    RUN_ID,
    cpu_calibration,
    cpu_hardware,
    cuda_calibration,
    cuda_hardware,
    record_target,
)


def install_record(tmp_path, monkeypatch, calibration_builder, hardware) -> None:
    """Write one synthetic record into an isolated managed data directory."""
    monkeypatch.setattr(record_module, "data_dir", lambda: tmp_path / "data")
    target = record_target(hardware)
    mode = load_catalog().mode("coding")
    document = build_record(target, calibration_builder(mode), RUN_ID)
    write_record(document, record_module.record_path("coding"))


def snapshot(free: float = 7.0, driver: str = "test-driver") -> GpuSnapshot:
    """Build one live GPU observation for the reuse-time driver and headroom check."""
    return GpuSnapshot(8, free, driver, ())


def query(hardware) -> ReuseQuery:
    """Build the current-state query matching the fixture identities."""
    return ReuseQuery(Config(), "coding", hardware, load_engine_lock())


def test_matching_cuda_record_with_headroom_is_valid(tmp_path, monkeypatch) -> None:
    """Reuse the envelope when every identity matches and free memory covers the need."""
    install_record(tmp_path, monkeypatch, cuda_calibration, cuda_hardware())
    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot())

    evaluation = evaluate_record(query(cuda_hardware()))

    assert evaluation.status == "valid"
    assert (evaluation.ctx, evaluation.n_cpu_moe) == (131072, 38)
    assert evaluation.diagnostics == ()


def test_missing_record_reports_the_baseline_invitation(tmp_path, monkeypatch) -> None:
    """Invite local calibration when no record exists for the mode."""
    monkeypatch.setattr(record_module, "data_dir", lambda: tmp_path / "data")

    evaluation = evaluate_record(query(cpu_hardware()))

    assert evaluation.status == "missing"
    assert "qwen-launcher calibrate" in evaluation.diagnostics[0]


def test_hardware_identity_divergence_invalidates_with_diagnostics(tmp_path, monkeypatch) -> None:
    """Never apply a record measured on different components (D-034/D-035)."""
    install_record(tmp_path, monkeypatch, cuda_calibration, cuda_hardware())
    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot())
    changed = replace(cuda_hardware(), cpu_name="Other CPU")

    evaluation = evaluate_record(query(changed))

    assert evaluation.status == "incompatible"
    assert any("CPU changed" in message for message in evaluation.diagnostics)


def test_page_level_total_ram_jitter_keeps_record_compatible(tmp_path, monkeypatch) -> None:
    """Ignore tiny OS MemTotal drift while preserving exact capacity in the record."""
    install_record(tmp_path, monkeypatch, cpu_calibration, cpu_hardware())
    changed = replace(cpu_hardware(), ram_total_gib=32 + (3 * 4096 / 1024**3))

    evaluation = evaluate_record(query(changed))

    assert evaluation.status == "valid"


def test_material_total_ram_change_invalidates_record(tmp_path, monkeypatch) -> None:
    """Keep a real RAM capacity change outside the narrow reporting tolerance."""
    install_record(tmp_path, monkeypatch, cpu_calibration, cpu_hardware())
    changed = replace(cpu_hardware(), ram_total_gib=31.5)

    evaluation = evaluate_record(query(changed))

    assert evaluation.status == "incompatible"
    assert any("total RAM GiB changed" in message for message in evaluation.diagnostics)


def test_engine_contract_divergence_invalidates_the_record(tmp_path, monkeypatch) -> None:
    """Ignore a record measured against a different engine release."""
    install_record(tmp_path, monkeypatch, cpu_calibration, cpu_hardware())
    lock = copy.deepcopy(load_engine_lock())
    lock["release"] = "b99999"

    evaluation = evaluate_record(ReuseQuery(Config(), "coding", cpu_hardware(), lock))

    assert evaluation.status == "incompatible"
    assert any("engine release changed" in message for message in evaluation.diagnostics)


def test_model_identity_divergence_invalidates_the_record(tmp_path, monkeypatch) -> None:
    """Never carry a default-model record onto a different configured model."""
    install_record(tmp_path, monkeypatch, cpu_calibration, cpu_hardware())
    changed = ReuseQuery(
        Config(model="other/model:file"), "coding", cpu_hardware(), load_engine_lock()
    )

    evaluation = evaluate_record(changed)

    assert evaluation.status == "incompatible"
    assert any("model changed" in message for message in evaluation.diagnostics)


def test_driver_change_invalidates_the_record(tmp_path, monkeypatch) -> None:
    """Ignore a record after a GPU driver update until it is re-measured."""
    install_record(tmp_path, monkeypatch, cuda_calibration, cuda_hardware())
    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot(driver="620.00"))

    evaluation = evaluate_record(query(cuda_hardware()))

    assert evaluation.status == "incompatible"
    assert any("GPU driver changed" in message for message in evaluation.diagnostics)


def test_insufficient_vram_headroom_defers_reuse(tmp_path, monkeypatch) -> None:
    """Refuse the envelope when free VRAM cannot cover the measured need plus reserve."""
    install_record(tmp_path, monkeypatch, cuda_calibration, cuda_hardware())
    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot(free=5.0))

    evaluation = evaluate_record(query(cuda_hardware()))

    assert evaluation.status == "insufficient-headroom"
    assert any("free VRAM" in message for message in evaluation.diagnostics)


def test_insufficient_ram_headroom_defers_reuse(tmp_path, monkeypatch) -> None:
    """Refuse the envelope when available RAM is below the measured need."""
    install_record(tmp_path, monkeypatch, cpu_calibration, cpu_hardware())
    low_ram = replace(cpu_hardware(), ram_available_gib=2.0)

    evaluation = evaluate_record(query(low_ram))

    assert evaluation.status == "insufficient-headroom"
    assert any("available RAM" in message for message in evaluation.diagnostics)


def test_pending_candidate_never_steers_reuse(tmp_path, monkeypatch) -> None:
    """Report a valid pending candidate while leaving the launch on its baseline."""
    monkeypatch.setattr(record_module, "data_dir", lambda: tmp_path / "data")
    target = record_target(cpu_hardware())
    mode = load_catalog().mode("coding")
    document = build_record(target, cpu_calibration(mode), RUN_ID)
    write_record(document, candidate_record_path("coding"))

    evaluation = evaluate_record(query(cpu_hardware()))

    assert evaluation.status == "candidate"
    assert evaluation.ctx is None
    assert evaluation.candidate_status == "valid"


def test_superseded_v1_record_is_distinct_from_corruption(tmp_path, monkeypatch) -> None:
    """Give rejected v2-protocol evidence an actionable schema-superceded diagnosis."""
    monkeypatch.setattr(record_module, "data_dir", lambda: tmp_path / "data")
    path = record_module.record_path("coding")
    path.parent.mkdir(parents=True)
    path.write_text('{"schema":"calibration-record/v1"}', encoding="utf-8")

    evaluation = evaluate_record(query(cpu_hardware()))

    assert evaluation.status == "superseded"
    assert "rerun" in evaluation.diagnostics[0]


def test_corrupt_record_is_reported_as_invalid(tmp_path, monkeypatch) -> None:
    """Fall back with the exact validation failure when a record cannot be trusted."""
    monkeypatch.setattr(record_module, "data_dir", lambda: tmp_path / "data")
    path = record_module.record_path("coding")
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")

    evaluation = evaluate_record(query(cpu_hardware()))

    assert evaluation.status == "invalid"
    assert "cannot read local calibration record" in evaluation.diagnostics[0]
