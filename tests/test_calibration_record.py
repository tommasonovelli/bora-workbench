"""Offline tests for record validation and the candidate/active/previous lifecycle."""

from __future__ import annotations

import json

import pytest

from qwen_launcher._calibration_record import (
    RecordError,
    RecordSupersededError,
    candidate_record_path,
    load_record,
    previous_record_path,
    promote_candidate,
    write_record,
)
from tests.record_fixtures import calibration_document, cpu_hardware, cuda_hardware


def written_record(tmp_path, hardware):
    """Build, write, and return one synthetic active record path."""
    return write_record(calibration_document(hardware), tmp_path / "records" / "coding.json")


def rewrite(path, mutate) -> None:
    """Apply one tampering mutation to a stored record."""
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_cuda_and_cpu_records_round_trip_their_three_envelopes(tmp_path) -> None:
    """Revalidate both backends and keep every measured envelope readable."""
    cuda_path = written_record(tmp_path / "cuda", cuda_hardware())
    cpu_path = written_record(tmp_path / "cpu", cpu_hardware())

    cuda = load_record(cuda_path)
    cpu = load_record(cpu_path)

    assert cuda["calibration_protocol"] == "calibration"
    assert cuda["reserves"]["vram_gib"] == 0.5
    assert sorted(cuda["envelopes"]) == ["balanced", "fast", "max_context"]
    assert cuda["envelopes"]["balanced"]["ctx"] == 131072
    assert cpu["envelopes"]["balanced"]["n_cpu_moe"] is None
    assert cpu["backend"] == "cpu"


def test_candidate_promotes_atomically_and_preserves_one_previous_slot(tmp_path) -> None:
    """Promote candidate to active while retaining the prior active bytes for rollback."""
    root = tmp_path / "records"
    active = write_record(calibration_document(cpu_hardware()), root / "coding.json")
    original = active.read_bytes()
    second = calibration_document(cpu_hardware())
    second["created_at"] = "2026-07-18T11:00:00Z"
    write_record(second, candidate_record_path("coding", root))

    promoted = promote_candidate("coding", root)

    assert load_record(promoted)["created_at"] == "2026-07-18T11:00:00Z"
    assert previous_record_path("coding", root).read_bytes() == original
    assert not candidate_record_path("coding", root).exists()


def test_record_written_by_an_older_launcher_is_actionably_superseded(tmp_path) -> None:
    """Diagnose an older record schema without attempting any migration."""
    path = tmp_path / "records" / "coding.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"schema":"calibration-record/v4"}', encoding="utf-8")

    with pytest.raises(RecordSupersededError, match="rerun"):
        load_record(path)


def test_tampered_reserves_and_active_preference_are_rejected(tmp_path) -> None:
    """Reject edits that detach the recorded margins or the active envelope from the evidence."""
    reserves = written_record(tmp_path / "reserves", cuda_hardware())
    rewrite(reserves, lambda record: record["reserves"].update(vram_gib=0.3))
    with pytest.raises(RecordError, match="reserves"):
        load_record(reserves)

    preference = written_record(tmp_path / "preference", cuda_hardware())
    rewrite(preference, lambda record: record.update(active_preference="fastest"))
    with pytest.raises(RecordError, match="is invalid"):
        load_record(preference)


def test_malformed_and_schema_invalid_records_are_rejected(tmp_path) -> None:
    """Diagnose malformed JSON and structural backend tampering."""
    malformed = tmp_path / "malformed" / "coding.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{broken", encoding="utf-8")
    with pytest.raises(RecordError, match="cannot read"):
        load_record(malformed)

    invalid = written_record(tmp_path / "invalid", cuda_hardware())
    rewrite(invalid, lambda record: record.update(backend="amd"))
    with pytest.raises(RecordError, match="is invalid"):
        load_record(invalid)


def test_record_file_name_must_match_the_recorded_mode(tmp_path) -> None:
    """Refuse a record stored under another mode's lifecycle name."""
    with pytest.raises(RecordError, match="mode must match file name"):
        write_record(calibration_document(cpu_hardware()), tmp_path / "studio.json")
