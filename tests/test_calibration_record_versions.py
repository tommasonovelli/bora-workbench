"""Test calibration record version migration and reserve reconstruction."""

from __future__ import annotations

import pytest

from qwen_launcher._calibration_record import RecordError, build_record, load_record, write_record
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import RUN_ID, cuda_calibration, cuda_hardware, record_target


def _record_document():
    """Build one coherent synthetic calibration-record/v4 document."""
    mode = load_catalog().mode("coding")
    return build_record(record_target(cuda_hardware()), cuda_calibration(mode), RUN_ID)


def _as_v3(record):
    """Convert compatible synthetic evidence to the historical v4 method contract."""
    record["schema"] = "calibration-record/v3"
    record["calibration_protocol"] = "calibration/v4"
    record["search"]["context_scale"] = [131072, 65536, 32768, 16384, 8192]
    record["search"]["probe_cap"] = 12
    return record


def _as_v2(record):
    """Convert compatible synthetic evidence to the historical v3 method contract."""
    _as_v3(record)
    record["schema"] = "calibration-record/v2"
    record["calibration_protocol"] = "calibration/v3"
    record["search"]["vram_reserve_gib"] = 0.5
    return record


def _remove_context_identity_evidence(record) -> None:
    """Reduce a document to the compatible pre-D-046 calibration-record/v2 shape."""
    search = record["search"]
    search.pop("context_identity_model")
    trials = [probe["trial"] for probe in search["probes"]]
    trials += [session for finalist in search["finalists"] for session in finalist["sessions"]]
    for trial in trials:
        if trial["vram"] is not None:
            trial["vram"].pop("context_replacement_count")


def _set_selected_vram_minimum(record, value: float) -> None:
    """Keep selected aggregate fields coherent while changing measured free VRAM."""
    selected = record["search"]["finalists"][0]
    for session in selected["sessions"]:
        session["vram"]["minimum_free_gib"] = value
    selected["minimum_free_vram_gib"] = value
    record["observed"]["minimum_vram_free_gib"] = value


def test_pre_d046_v2_record_remains_compatibly_loadable(tmp_path) -> None:
    """Keep historical v3 records readable under their original 0.5 GiB reserve."""
    document = _as_v2(_record_document())
    _remove_context_identity_evidence(document)
    path = write_record(document, tmp_path / "records" / "coding.json")

    assert load_record(path)["calibration_protocol"] == "calibration/v3"


def test_historical_v4_record_remains_compatibly_loadable(tmp_path) -> None:
    """Keep the prior automatic scale readable after 96K and 48K join v5."""
    document = _as_v3(_record_document())
    path = write_record(document, tmp_path / "records" / "coding.json")

    assert load_record(path)["calibration_protocol"] == "calibration/v4"


def test_each_record_version_enforces_its_own_vram_reserve(tmp_path) -> None:
    """Accept 0.4 GiB for v4/v5 while retaining strict v3 reconstruction."""
    current = _record_document()
    _set_selected_vram_minimum(current, 0.4)
    path = write_record(current, tmp_path / "v5" / "coding.json")
    assert load_record(path)["calibration_protocol"] == "calibration/v5"

    prior = _as_v3(_record_document())
    _set_selected_vram_minimum(prior, 0.4)
    path = write_record(prior, tmp_path / "v4" / "coding.json")
    assert load_record(path)["calibration_protocol"] == "calibration/v4"

    historical = _as_v2(_record_document())
    _set_selected_vram_minimum(historical, 0.4)
    with pytest.raises(RecordError, match="VRAM reserve"):
        write_record(historical, tmp_path / "v3" / "coding.json")
