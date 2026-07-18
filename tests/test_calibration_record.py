"""Offline tests for building, atomically writing, and revalidating local records."""

from __future__ import annotations

import json

import pytest

from qwen_launcher._calibration_record import RecordError, build_record, load_record, write_record
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import (
    cpu_calibration,
    cpu_hardware,
    cuda_calibration,
    cuda_hardware,
    record_target,
)


def written_record(tmp_path, calibration_builder, hardware):
    """Build, write, and return the path of one synthetic record."""
    target = record_target(hardware)
    mode = load_catalog().mode("coding")
    document = build_record(target, calibration_builder(mode))
    return write_record(document, tmp_path / "records" / "coding.json")


def rewrite(path, mutate) -> None:
    """Apply one tampering mutation to a stored record."""
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_written_cuda_record_is_atomic_and_revalidates(tmp_path) -> None:
    """Round-trip a coherent CUDA record without leaving temporary files behind."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())

    record = load_record(path)

    assert record["envelope"] == {"ctx": 131072, "n_cpu_moe": 38}
    assert record["calibration_protocol"] == "calibration/v2"
    assert record["observed"]["vram_needed_gib"] == pytest.approx(5.1)
    assert record["observed"]["ram_needed_gib"] == pytest.approx(4.0)
    assert record["hardware"]["gpu_driver"] == "test-driver"
    assert not list(path.parent.glob("*.tmp"))


def test_written_cpu_record_confirms_only_the_baseline(tmp_path) -> None:
    """Serialize a CPU record with null GPU evidence and the baseline rule."""
    path = written_record(tmp_path, cpu_calibration, cpu_hardware())

    record = load_record(path)

    assert record["backend"] == "cpu"
    assert record["envelope"] == {"ctx": 8192, "n_cpu_moe": None}
    assert record["observed"]["vram_needed_gib"] is None
    assert record["selection_rule"] == "cpu-baseline-confirmation"


def test_envelope_must_repeat_the_selected_finalist(tmp_path) -> None:
    """Reject a record whose envelope was edited away from its own evidence."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())
    rewrite(path, lambda record: record["envelope"].update(n_cpu_moe=36))

    with pytest.raises(RecordError, match="envelope does not match"):
        load_record(path)


def test_context_must_repeat_the_finalists(tmp_path) -> None:
    """Reject a record whose launch context was edited away from finalist evidence."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())
    rewrite(path, lambda record: record["envelope"].update(ctx=65536))

    with pytest.raises(RecordError, match="finalists must use"):
        load_record(path)


def test_headroom_must_repeat_the_selected_finalist(tmp_path) -> None:
    """Reject edited headroom values that could make an unsafe record look reusable."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())
    rewrite(path, lambda record: record["observed"].update(vram_needed_gib=0.0))

    with pytest.raises(RecordError, match="observed vram_needed_gib"):
        load_record(path)


def test_selection_must_follow_the_dominance_rule(tmp_path) -> None:
    """Reject a record whose selected finalist contradicts the reconstruction."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())

    def swap_selection(record) -> None:
        """Move the selection to the dominated finalist and align the envelope."""
        finalists = record["search"]["finalists"]
        finalists[0]["is_selected"] = False
        finalists[1]["is_selected"] = True
        record["envelope"]["n_cpu_moe"] = finalists[1]["n_cpu_moe"]

    rewrite(path, swap_selection)

    with pytest.raises(RecordError, match="deterministic dominance rule"):
        load_record(path)


def test_selection_rule_label_must_match_the_reconstruction(tmp_path) -> None:
    """Reject a rule label that does not describe the measured selection."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())
    rewrite(path, lambda record: record.update(selection_rule="equivalent-prefer-prudent"))

    with pytest.raises(RecordError, match="selection rule must be"):
        load_record(path)


def test_benchmark_summary_must_derive_from_the_measures(tmp_path) -> None:
    """Reject a summary median that the five stored measures do not produce."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())
    rewrite(path, lambda record: record["benchmark"]["tok_s"].update(median=99.0))

    with pytest.raises(RecordError, match="benchmark summary median"):
        load_record(path)


def test_schema_violations_are_rejected_with_context(tmp_path) -> None:
    """Reject structural tampering such as a CUDA envelope on a CPU record."""
    path = written_record(tmp_path, cuda_calibration, cuda_hardware())
    rewrite(path, lambda record: record.update(backend="cpu"))

    with pytest.raises(RecordError, match="is invalid"):
        load_record(path)


def test_unreadable_record_is_rejected(tmp_path) -> None:
    """Diagnose malformed JSON instead of silently ignoring a corrupt record."""
    path = tmp_path / "records" / "coding.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(RecordError, match="cannot read local calibration record"):
        load_record(path)
