"""Reconstruct calibration-record/v2 evidence that JSON Schema cannot cross-check."""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import cast

from qwen_launcher._calibration_record_sessions import (
    fail,
    finalist_medians,
    selected_entry,
    verify_abba,
    verify_benchmark,
    verify_finalists,
    verify_vram_entry,
)
from qwen_launcher._calibration_v3_search import select_candidate_index
from qwen_launcher._calibration_v3_types import (
    RAM_RESERVE_GIB,
    RELEASE_TOLERANCE_GIB,
    SELECTION_CPU_BASELINE,
    VRAM_RESERVE_GIB,
    SelectionCandidate,
)

JsonObject = dict[str, object]


def _search(document: JsonObject) -> JsonObject:
    """Return the schema-validated search object with a narrow cast."""
    return cast(JsonObject, document["search"])


def _finalists(document: JsonObject) -> list[JsonObject]:
    """Return schema-validated finalists with a narrow cast."""
    return cast(list[JsonObject], _search(document)["finalists"])


def _verify_envelope(document: JsonObject, path: Path) -> None:
    """Require one fixed context and the selected finalist's exact axis."""
    _, selected = selected_entry(document, path)
    envelope = cast(JsonObject, document["envelope"])
    target_ctx = _search(document)["target_ctx"]
    if target_ctx is not None and envelope["ctx"] != target_ctx:
        raise fail(path, "expert target context does not match the recorded envelope")
    if any(entry["ctx"] != envelope["ctx"] for entry in _finalists(document)):
        raise fail(path, "all finalists must use the recorded envelope context")
    if envelope["n_cpu_moe"] != selected["n_cpu_moe"]:
        raise fail(path, "envelope does not match the selected finalist")


def _verify_selected_evidence(document: JsonObject, path: Path) -> None:
    """Tie launch-time headroom fields exactly to the selected finalist aggregates."""
    _, selected = selected_entry(document, path)
    observed = cast(JsonObject, document["observed"])
    pairs = (
        ("ram_needed_gib", "ram_needed_gib"),
        ("minimum_ram_available_gib", "minimum_ram_available_gib"),
        ("vram_needed_gib", "vram_needed_gib"),
        ("minimum_vram_free_gib", "minimum_free_vram_gib"),
    )
    for observed_name, finalist_name in pairs:
        if observed[observed_name] != selected[finalist_name]:
            raise fail(path, f"observed {observed_name} does not match the selected finalist")


def _verify_selected_benchmark(document: JsonObject, path: Path) -> None:
    """Rebuild the selected two-session benchmark aggregate and summary."""
    _, selected = selected_entry(document, path)
    sessions = cast(list[JsonObject], selected["sessions"])
    benchmarks = [cast(JsonObject, session["benchmark"]) for session in sessions]
    for benchmark in benchmarks:
        verify_benchmark(benchmark, path)
    warmups = [entry["warmup_tok_s"] for entry in benchmarks]
    measured = [
        float(value) for entry in benchmarks for value in cast(list[float], entry["measured_tok_s"])
    ]
    stored = cast(JsonObject, document["benchmark"])
    expected_summary = {"min": min(measured), "median": median(measured), "max": max(measured)}
    if stored["warmup_tok_s"] != warmups or stored["measured_tok_s"] != measured:
        raise fail(path, "selected benchmark aggregate does not match paired sessions")
    if stored["round_medians"] != selected["round_medians"]:
        raise fail(path, "selected benchmark round medians do not match the finalist")
    if stored["tok_s"] != expected_summary:
        raise fail(path, "selected benchmark summary does not match paired sessions")


def _verify_probe_evidence(document: JsonObject, path: Path) -> None:
    """Require ordered probes and enforce RAM reserve only on completed feasible loads."""
    probes = cast(list[JsonObject], _search(document)["probes"])
    sequences = [cast(JsonObject, probe["trial"])["sequence"] for probe in probes]
    if sequences != list(range(1, len(probes) + 1)):
        raise fail(path, "screening probe sequence is not contiguous execution order")
    for probe in probes:
        if not probe["is_feasible"]:
            continue
        trial = cast(JsonObject, probe["trial"])
        ram = cast(JsonObject, trial["ram"])
        if float(cast(float, ram["minimum_available_gib"])) < RAM_RESERVE_GIB:
            raise fail(path, "feasible screening probe violates the universal RAM reserve")
        if document["backend"] != "cuda":
            continue
        vram = cast(JsonObject | None, trial["vram"])
        if vram is None:
            raise fail(path, "feasible CUDA probe requires measured VRAM evidence")
        if float(cast(float, vram["minimum_free_gib"])) < VRAM_RESERVE_GIB:
            raise fail(path, "feasible screening probe violates the universal VRAM reserve")
        verify_vram_entry(vram, path)


def _verify_degradation(document: JsonObject, path: Path) -> None:
    """Recompute monotonic degradation from feasible final-context peaks only (D-045)."""
    search = _search(document)
    ctx = cast(JsonObject, document["envelope"])["ctx"]
    probes = cast(list[JsonObject], search["probes"])
    peaks = []
    for probe in probes:
        if probe["ctx"] != ctx or not probe["is_feasible"]:
            continue
        vram = cast(JsonObject | None, cast(JsonObject, probe["trial"])["vram"])
        if vram is not None:
            peaks.append((cast(int, probe["n_cpu_moe"]), float(cast(float, vram["peak_used_gib"]))))
    did_violate = any(
        aggressive < prudent and aggressive_peak + RELEASE_TOLERANCE_GIB < prudent_peak
        for aggressive, aggressive_peak in peaks
        for prudent, prudent_peak in peaks
    )
    if bool(search["did_degrade"]) != did_violate:
        raise fail(path, "degradation flag does not match feasible screening peaks")


def _baseline_drift(document: JsonObject, path: Path) -> float | None:
    """Recompute aggregate confirmation baseline excursion from all CUDA sessions."""
    baselines = []
    for finalist in _finalists(document):
        for session in cast(list[JsonObject], finalist["sessions"]):
            vram = cast(JsonObject | None, session["vram"])
            if vram is not None:
                baselines.append(float(cast(float, vram["baseline_used_gib"])))
    drift = max(baselines) - min(baselines) if len(baselines) > 1 else None
    if _search(document)["baseline_drift_gib"] != drift:
        raise fail(path, "baseline drift does not match paired session evidence")
    return drift


def _selection_candidates(document: JsonObject) -> list[tuple[int, SelectionCandidate]]:
    """Project valid serialized finalists onto paired selection fields."""
    result = []
    for index, finalist in enumerate(_finalists(document)):
        if finalist["outcome"] != "valid":
            continue
        free = cast(float | None, finalist["minimum_free_vram_gib"])
        moe = cast(int | None, finalist["n_cpu_moe"])
        result.append((index, SelectionCandidate(finalist_medians(finalist), free, moe)))
    return result


def _verify_selection(document: JsonObject, path: Path, drift: float | None) -> None:
    """Reconstruct round winners, drift degradation, tie-break, and selected finalist."""
    finalists = _finalists(document)
    selected_index, _ = selected_entry(document, path)
    if document["backend"] == "cpu":
        if document["selection_rule"] != SELECTION_CPU_BASELINE or len(finalists) != 1:
            raise fail(path, "CPU records must confirm exactly the engine baseline")
        if _search(document)["round_winners"] != [None, None]:
            raise fail(path, "CPU baseline rounds must not claim a comparison winner")
        return
    pairs = _selection_candidates(document)
    candidates = tuple(item[1] for item in pairs)
    winner, rule, rounds = select_candidate_index(
        candidates,
        has_baseline_drift=bool(drift and drift > RELEASE_TOLERANCE_GIB),
    )
    expected_rounds = [None if item is None else pairs[item][0] for item in rounds]
    if _search(document)["round_winners"] != expected_rounds:
        raise fail(path, "round winners do not match paired session medians")
    if selected_index != pairs[winner][0]:
        raise fail(path, "selection does not follow paired round dominance and tie-breaks")
    if document["selection_rule"] != rule:
        raise fail(path, f"selection rule must be {rule!r}")


def verify_record(document: JsonObject, path: Path) -> None:
    """Run every semantic check required for a trustworthy local v2 record."""
    verify_abba(document, path)
    verify_finalists(document, path)
    _verify_envelope(document, path)
    _verify_probe_evidence(document, path)
    _verify_degradation(document, path)
    drift = _baseline_drift(document, path)
    _verify_selection(document, path, drift)
    _verify_selected_evidence(document, path)
    _verify_selected_benchmark(document, path)
