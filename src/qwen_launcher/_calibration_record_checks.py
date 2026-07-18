"""Reconstruct calibration-record/v1 evidence that JSON Schema cannot cross-check."""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import cast

from qwen_launcher._calibration_v2_types import SELECTION_CPU_BASELINE

JsonObject = dict[str, object]


def _fail(path: Path, message: str) -> Exception:
    """Build one actionable record rejection tied to its file."""
    from qwen_launcher._calibration_record import RecordError

    return RecordError(f"local calibration record {path} is invalid: {message}")


def _verify_benchmark_summary(document: JsonObject, path: Path) -> None:
    """Require the stored min/median/max to derive from the five measures."""
    benchmark = cast(JsonObject, document["benchmark"])
    measured = [float(value) for value in cast(list[float], benchmark["measured_tok_s"])]
    summary = cast(JsonObject, benchmark["tok_s"])
    expected = {"min": min(measured), "median": median(measured), "max": max(measured)}
    for key, value in expected.items():
        if float(cast(float, summary[key])) != value:
            raise _fail(path, f"benchmark summary {key} does not match the stored measures")


def _selected_entry(document: JsonObject, path: Path) -> JsonObject:
    """Return the single selected finalist, rejecting missing or duplicate selections."""
    finalists = cast(list[JsonObject], cast(JsonObject, document["search"])["finalists"])
    selected = [entry for entry in finalists if entry["is_selected"]]
    if len(selected) != 1:
        raise _fail(path, "exactly one finalist must be selected")
    if selected[0]["outcome"] != "valid":
        raise _fail(path, "the selected finalist must be valid")
    return selected[0]


def _verify_finalist_evidence(document: JsonObject, path: Path) -> None:
    """Require every valid finalist to carry backend-appropriate measured resources."""
    finalists = cast(list[JsonObject], cast(JsonObject, document["search"])["finalists"])
    is_cuda = document["backend"] == "cuda"
    for finalist in finalists:
        if finalist["outcome"] != "valid":
            continue
        if finalist["ram_needed_gib"] is None or finalist["minimum_ram_available_gib"] is None:
            raise _fail(path, "every valid finalist requires measured RAM evidence")
        vram_fields = (finalist["vram_needed_gib"], finalist["minimum_free_vram_gib"])
        if is_cuda and any(value is None for value in vram_fields):
            raise _fail(path, "every valid CUDA finalist requires measured VRAM evidence")
        if not is_cuda and any(value is not None for value in vram_fields):
            raise _fail(path, "CPU finalists must not contain VRAM evidence")


def _verify_envelope(document: JsonObject, path: Path) -> None:
    """Require one fixed finalist context and the selected finalist's exact axis."""
    selected = _selected_entry(document, path)
    envelope = cast(JsonObject, document["envelope"])
    finalists = cast(list[JsonObject], cast(JsonObject, document["search"])["finalists"])
    if any(entry["ctx"] != envelope["ctx"] for entry in finalists):
        raise _fail(path, "all finalists must use the recorded envelope context")
    if envelope["n_cpu_moe"] != selected["n_cpu_moe"]:
        raise _fail(path, "envelope does not match the selected finalist")


def _verify_selected_evidence(document: JsonObject, path: Path) -> None:
    """Tie launch-time benchmark and headroom fields to the selected finalist."""
    selected = _selected_entry(document, path)
    benchmark = cast(JsonObject, document["benchmark"])
    observed = cast(JsonObject, document["observed"])
    if benchmark["measured_tok_s"] != selected["measured_tok_s"]:
        raise _fail(path, "benchmark evidence does not match the selected finalist")
    field_pairs = (
        ("ram_needed_gib", "ram_needed_gib"),
        ("minimum_ram_available_gib", "minimum_ram_available_gib"),
        ("vram_needed_gib", "vram_needed_gib"),
        ("minimum_vram_free_gib", "minimum_free_vram_gib"),
    )
    for observed_name, finalist_name in field_pairs:
        if observed[observed_name] != selected[finalist_name]:
            raise _fail(path, f"observed {observed_name} does not match the selected finalist")


def _verify_degradation(document: JsonObject, path: Path) -> None:
    """Recompute whether final-context peak measures contradicted monotonic screening."""
    search = cast(JsonObject, document["search"])
    ctx = cast(JsonObject, document["envelope"])["ctx"]
    probes = cast(list[JsonObject], search["probes"])
    peaks = [
        (cast(int, probe["n_cpu_moe"]), float(cast(float, probe["peak_used_gib"])))
        for probe in probes
        if probe["ctx"] == ctx and probe["peak_used_gib"] is not None
    ]
    tolerance = float(cast(float, search["release_tolerance_gib"]))
    did_violate = any(
        aggressive < prudent and aggressive_peak + tolerance < prudent_peak
        for aggressive, aggressive_peak in peaks
        for prudent, prudent_peak in peaks
    )
    if bool(search["did_degrade"]) != did_violate:
        raise _fail(path, "degradation flag does not match measured screening peaks")


def _verify_selection_rule(document: JsonObject, path: Path) -> None:
    """Reconstruct the winner and rule from the stored finalists (D-038)."""
    from qwen_launcher._calibration_record import reconstruct_selection

    finalists = cast(list[JsonObject], cast(JsonObject, document["search"])["finalists"])
    if document["backend"] == "cpu":
        if document["selection_rule"] != SELECTION_CPU_BASELINE or len(finalists) != 1:
            raise _fail(path, "CPU records must confirm exactly the engine baseline")
        return
    valid = [entry for entry in finalists if entry["outcome"] == "valid"]
    index, rule = reconstruct_selection(finalists)
    if valid[index] is not _selected_entry(document, path):
        raise _fail(path, "selection does not follow the deterministic dominance rule")
    if document["selection_rule"] != rule:
        raise _fail(path, f"selection rule must be {rule!r}")


def verify_record(document: JsonObject, path: Path) -> None:
    """Run every semantic check a trustworthy local record must pass."""
    _verify_benchmark_summary(document, path)
    _verify_finalist_evidence(document, path)
    _verify_envelope(document, path)
    _verify_selection_rule(document, path)
    _verify_selected_evidence(document, path)
    _verify_degradation(document, path)
