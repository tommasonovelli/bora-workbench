"""Verify calibration/v4 launch-time VRAM headroom."""

from __future__ import annotations

import qwen_launcher._calibration_record as record_module
import qwen_launcher._calibration_reuse as reuse_module
from qwen_launcher._calibration_record import build_record, write_record
from qwen_launcher._calibration_reuse import evaluate_record
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import RUN_ID, cuda_calibration, cuda_hardware, record_target
from tests.test_calibration_reuse import install_record, query, snapshot


def _install_v2(tmp_path, monkeypatch) -> None:
    """Install one historical v3 record under an isolated managed data root."""
    monkeypatch.setattr(record_module, "data_dir", lambda: tmp_path / "data")
    mode = load_catalog().mode("coding")
    document = build_record(record_target(cuda_hardware()), cuda_calibration(mode), RUN_ID)
    document["schema"] = "calibration-record/v2"
    document["calibration_protocol"] = "calibration/v3"
    document["search"]["vram_reserve_gib"] = 0.5
    write_record(document, record_module.record_path("coding"))


def test_reuse_requires_measured_need_plus_point_three_gib(tmp_path, monkeypatch) -> None:
    """Enforce the v4 reserve exactly instead of retaining v3's 0.5 GiB threshold."""
    install_record(tmp_path, monkeypatch, cuda_calibration, cuda_hardware())
    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot(free=5.399))

    below = evaluate_record(query(cuda_hardware()))

    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot(free=5.4))
    exact = evaluate_record(query(cuda_hardware()))
    assert below.status == "insufficient-headroom"
    assert exact.status == "valid"


def test_historical_v3_reuse_keeps_point_five_gib_reserve(tmp_path, monkeypatch) -> None:
    """Never weaken launch-time headroom for records measured under calibration/v3."""
    _install_v2(tmp_path, monkeypatch)
    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot(free=5.4))
    below = evaluate_record(query(cuda_hardware()))

    monkeypatch.setattr(reuse_module, "query_gpu_snapshot", lambda index: snapshot(free=5.6))
    exact = evaluate_record(query(cuda_hardware()))
    assert below.status == "insufficient-headroom"
    assert exact.status == "valid"
