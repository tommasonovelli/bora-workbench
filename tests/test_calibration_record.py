"""Offline tests for calibration-record/v2 building, reconstruction, and lifecycle promotion."""

from __future__ import annotations

import json

import pytest

from qwen_launcher._calibration_record import (
    RecordError,
    RecordSupersededError,
    build_record,
    candidate_record_path,
    load_record,
    previous_record_path,
    promote_candidate,
    write_record,
)
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import (
    RUN_ID,
    cpu_calibration,
    cpu_hardware,
    cuda_calibration,
    cuda_hardware,
    record_target,
)


def record_document(calibration_builder, hardware):
    """Build one coherent synthetic v2 record document."""
    target = record_target(hardware)
    mode = load_catalog().mode("coding")
    return build_record(target, calibration_builder(mode), RUN_ID)


def written_record(tmp_path, calibration_builder, hardware):
    """Build, write, and return one synthetic active record path."""
    document = record_document(calibration_builder, hardware)
    return write_record(document, tmp_path / "records" / "coding.json")


def rewrite(path, mutate) -> None:
    """Apply one tampering mutation to a stored record."""
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def remove_context_identity_evidence(record) -> None:
    """Reduce a document to the compatible pre-D-046 calibration-record/v2 shape."""
    search = record["search"]
    search.pop("context_identity_model")
    trials = [probe["trial"] for probe in search["probes"]]
    trials += [session for finalist in search["finalists"] for session in finalist["sessions"]]
    for trial in trials:
        if trial["vram"] is not None:
            trial["vram"].pop("context_replacement_count")


def test_cuda_and_cpu_records_round_trip_complete_paired_evidence(tmp_path) -> None:
    """Revalidate CUDA and CPU documents with ten selected benchmark measures."""
    cuda_path = written_record(tmp_path / "cuda", cuda_calibration, cuda_hardware())
    cpu_path = written_record(tmp_path / "cpu", cpu_calibration, cpu_hardware())

    cuda = load_record(cuda_path)
    cpu = load_record(cpu_path)

    assert cuda["schema"] == "calibration-record/v2"
    assert cuda["calibration_protocol"] == "calibration/v3"
    assert len(cuda["benchmark"]["measured_tok_s"]) == 10
    assert cuda["search"]["round_winners"] == [0, 0]
    assert cuda["search"]["context_identity_model"] == "executable-file-id/v1"
    first_vram = cuda["search"]["finalists"][0]["sessions"][0]["vram"]
    assert first_vram["telemetry"] is None
    assert first_vram["context_replacement_count"] == 0
    assert cpu["search"]["context_identity_model"] is None
    assert cpu["selection_rule"] == "cpu-baseline-confirmation"
    assert cpu["observed"]["vram_needed_gib"] is None


def test_pre_d046_v2_record_remains_compatibly_loadable(tmp_path) -> None:
    """Keep evidence-only D-046 fields additive within calibration-record/v2."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())
    rewrite(path, remove_context_identity_evidence)

    assert load_record(path)["calibration_protocol"] == "calibration/v3"


def test_candidate_promotes_atomically_and_preserves_one_previous_slot(tmp_path) -> None:
    """Promote candidate→active while retaining the prior active bytes for rollback."""
    root = tmp_path / "records"
    first = record_document(cpu_calibration, cpu_hardware())
    active = write_record(first, root / "coding.json")
    original = active.read_bytes()
    second = record_document(cpu_calibration, cpu_hardware())
    second["created_at"] = "2026-07-18T11:00:00Z"
    write_record(second, candidate_record_path("coding", root))

    promoted = promote_candidate("coding", root)

    assert load_record(promoted)["created_at"] == "2026-07-18T11:00:00Z"
    assert previous_record_path("coding", root).read_bytes() == original
    assert not candidate_record_path("coding", root).exists()


def test_historical_v1_record_is_actionably_superseded(tmp_path) -> None:
    """Neutralize rejected calibration/v2 evidence without attempting migration."""
    path = tmp_path / "records" / "coding.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"schema":"calibration-record/v1"}', encoding="utf-8")

    with pytest.raises(RecordSupersededError, match="rerun"):
        load_record(path)


def test_envelope_and_headroom_must_repeat_selected_finalist(tmp_path) -> None:
    """Reject edits that detach launch settings or resource needs from paired evidence."""
    envelope = written_record(tmp_path / "envelope", cuda_calibration, cuda_hardware())
    rewrite(envelope, lambda record: record["envelope"].update(n_cpu_moe=36))
    with pytest.raises(RecordError, match="envelope does not match"):
        load_record(envelope)

    headroom = written_record(tmp_path / "headroom", cuda_calibration, cuda_hardware())
    rewrite(headroom, lambda record: record["observed"].update(vram_needed_gib=0.0))
    with pytest.raises(RecordError, match="observed vram_needed_gib"):
        load_record(headroom)


def test_abba_order_and_round_winners_are_reconstructed(tmp_path) -> None:
    """Reject temporal-order and winner labels that contradict session evidence."""
    order = written_record(tmp_path / "order", cuda_calibration, cuda_hardware())
    rewrite(
        order,
        lambda record: record["search"]["finalists"][0]["sessions"][1].update(global_position=3),
    )
    with pytest.raises(RecordError, match="ABBA"):
        load_record(order)

    winners = written_record(tmp_path / "winners", cuda_calibration, cuda_hardware())
    rewrite(winners, lambda record: record["search"].update(round_winners=[1, 1]))
    with pytest.raises(RecordError, match="round winners"):
        load_record(winners)


def test_selection_and_rule_follow_unanimous_rounds(tmp_path) -> None:
    """Reject a selected finalist and label that contradict paired medians."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())

    def swap(record) -> None:
        """Move selection and envelope to the unanimously dominated finalist."""
        finalists = record["search"]["finalists"]
        finalists[0]["is_selected"] = False
        finalists[1]["is_selected"] = True
        record["envelope"]["n_cpu_moe"] = finalists[1]["n_cpu_moe"]

    rewrite(path, swap)
    with pytest.raises(RecordError, match="paired round dominance"):
        load_record(path)


def test_benchmark_summary_and_ram_reserve_are_reconstructed(tmp_path) -> None:
    """Reject fabricated selected summaries and confirmation below the RAM reserve."""
    summary = written_record(tmp_path / "summary", cuda_calibration, cuda_hardware())
    rewrite(summary, lambda record: record["benchmark"]["tok_s"].update(median=99.0))
    with pytest.raises(RecordError, match="benchmark summary"):
        load_record(summary)

    reserve = written_record(tmp_path / "reserve", cuda_calibration, cuda_hardware())
    rewrite(
        reserve,
        lambda record: record["search"]["finalists"][0]["sessions"][0]["ram"].update(
            minimum_available_gib=1.0
        ),
    )
    with pytest.raises(RecordError, match="RAM reserve"):
        load_record(reserve)


def test_malformed_and_schema_invalid_records_are_rejected(tmp_path) -> None:
    """Diagnose malformed JSON and structural backend tampering."""
    malformed = tmp_path / "malformed" / "coding.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{broken", encoding="utf-8")
    with pytest.raises(RecordError, match="cannot read"):
        load_record(malformed)

    invalid = written_record(tmp_path / "invalid", cuda_calibration, cuda_hardware())
    rewrite(invalid, lambda record: record.update(backend="cpu"))
    with pytest.raises(RecordError, match="is invalid"):
        load_record(invalid)
