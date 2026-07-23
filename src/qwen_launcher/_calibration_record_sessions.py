"""Reconstruct versioned record sessions and conservative resource aggregates."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from statistics import median
from typing import cast

from qwen_launcher._calibration_v5_types import RELEASE_TOLERANCE_GIB

JsonObject = dict[str, object]


def fail(path: Path, message: str) -> Exception:
    """Build one actionable semantic record rejection tied to its file."""
    from qwen_launcher._calibration_record import RecordError

    return RecordError(f"local calibration record {path} is invalid: {message}")


def _summary(measured: list[float]) -> dict[str, float]:
    """Derive the exact token-rate summary used throughout record reconstruction."""
    return {"min": min(measured), "median": median(measured), "max": max(measured)}


def verify_benchmark(entry: JsonObject, path: Path) -> None:
    """Require one benchmark summary to derive from its stored included measures."""
    measured = [float(value) for value in cast(list[float], entry["measured_tok_s"])]
    summary = cast(JsonObject, entry["tok_s"])
    for key, value in _summary(measured).items():
        if float(cast(float, summary[key])) != value:
            raise fail(path, f"benchmark summary {key} does not match stored measures")


def selected_entry(document: JsonObject, path: Path) -> tuple[int, JsonObject]:
    """Return the sole valid selected finalist and its original index."""
    finalists = cast(list[JsonObject], cast(JsonObject, document["search"])["finalists"])
    selected = [(index, entry) for index, entry in enumerate(finalists) if entry["is_selected"]]
    if len(selected) != 1:
        raise fail(path, "exactly one finalist must be selected")
    if selected[0][1]["outcome"] != "valid":
        raise fail(path, "the selected finalist must be valid")
    return selected[0]


def _session_medians(finalist: JsonObject, path: Path) -> tuple[float, ...]:
    """Recompute one valid finalist's two median rates from full sessions."""
    medians = []
    for session in cast(list[JsonObject], finalist["sessions"]):
        benchmark = cast(JsonObject | None, session["benchmark"])
        if benchmark is None:
            raise fail(path, "every valid finalist session requires benchmark/v1 evidence")
        verify_benchmark(benchmark, path)
        measured = [float(value) for value in cast(list[float], benchmark["measured_tok_s"])]
        medians.append(median(measured))
    return tuple(medians)


def _ram_values(sessions: list[JsonObject], path: Path, reserve_gib: float) -> tuple[float, float]:
    """Reconstruct conservative RAM need and minimum under the record's own reserve."""
    entries = [cast(JsonObject | None, session["ram"]) for session in sessions]
    if any(entry is None for entry in entries):
        raise fail(path, "every valid finalist session requires measured RAM evidence")
    complete = [entry for entry in entries if entry is not None]
    baselines = [float(cast(float, entry["baseline_available_gib"])) for entry in complete]
    minima = [float(cast(float, entry["minimum_available_gib"])) for entry in complete]
    if any(minimum > baseline for minimum, baseline in zip(minima, baselines, strict=True)):
        raise fail(path, "RAM minimum exceeds its own pre-trial baseline")
    if min(minima) < reserve_gib:
        raise fail(path, "valid finalist violates the universal RAM reserve")
    return max(baselines) - min(minima), min(minima)


def verify_vram_entry(entry: JsonObject, path: Path) -> None:
    """Require internally ordered peak evidence and release within tolerance."""
    baseline = float(cast(float, entry["baseline_used_gib"]))
    peak = float(cast(float, entry["peak_used_gib"]))
    release = float(cast(float, entry["release_used_gib"]))
    if peak < baseline or peak < release:
        raise fail(path, "VRAM peak is below baseline or release evidence")
    if release > baseline + RELEASE_TOLERANCE_GIB:
        raise fail(path, "VRAM release exceeds tolerance")


def _vram_values(sessions: list[JsonObject], path: Path, reserve_gib: float) -> tuple[float, float]:
    """Reconstruct conservative VRAM need and minimum under the record's own reserve."""
    entries = [cast(JsonObject | None, session["vram"]) for session in sessions]
    if any(entry is None for entry in entries):
        raise fail(path, "every valid CUDA finalist session requires measured VRAM evidence")
    complete = [entry for entry in entries if entry is not None]
    baselines = [float(cast(float, entry["baseline_used_gib"])) for entry in complete]
    peaks = [float(cast(float, entry["peak_used_gib"])) for entry in complete]
    minima = [float(cast(float, entry["minimum_free_gib"])) for entry in complete]
    if min(minima) < reserve_gib:
        raise fail(path, "valid finalist violates the universal VRAM reserve")
    for entry in complete:
        verify_vram_entry(entry, path)
    return max(peaks) - min(baselines), min(minima)


def verify_finalists(document: JsonObject, path: Path) -> None:
    """Recompute valid-finalist round medians and conservative resource fields."""
    search = cast(JsonObject, document["search"])
    finalists = cast(list[JsonObject], search["finalists"])
    ram_reserve_gib = float(cast(float, search["ram_reserve_gib"]))
    vram_reserve_gib = float(cast(float, search["vram_reserve_gib"]))
    is_cuda = document["backend"] == "cuda"
    for finalist in finalists:
        if finalist["outcome"] != "valid":
            continue
        sessions = cast(list[JsonObject], finalist["sessions"])
        medians = _session_medians(finalist, path)
        if list(medians) != finalist["round_medians"]:
            raise fail(path, "finalist round medians do not match stored sessions")
        ram_needed, ram_minimum = _ram_values(sessions, path, ram_reserve_gib)
        if finalist["ram_needed_gib"] != ram_needed:
            raise fail(path, "finalist RAM need does not match stored sessions")
        if finalist["minimum_ram_available_gib"] != ram_minimum:
            raise fail(path, "finalist RAM minimum does not match stored sessions")
        if is_cuda:
            vram_needed, vram_minimum = _vram_values(sessions, path, vram_reserve_gib)
            if finalist["vram_needed_gib"] != vram_needed:
                raise fail(path, "finalist VRAM need does not match stored sessions")
            if finalist["minimum_free_vram_gib"] != vram_minimum:
                raise fail(path, "finalist VRAM minimum does not match stored sessions")
        elif finalist["vram_needed_gib"] is not None:
            raise fail(path, "CPU finalists must not contain VRAM evidence")


def _parse_time(value: object, path: Path) -> datetime:
    """Parse a schema-validated UTC timestamp for temporal-order checks."""
    try:
        return datetime.fromisoformat(cast(str, value).replace("Z", "+00:00"))
    except ValueError as error:
        raise fail(path, "session timestamp is not a valid date-time") from error


def verify_abba(document: JsonObject, path: Path) -> None:
    """Require exact A→B/B→A positions, rounds, and non-reversed session boundaries."""
    finalists = cast(list[JsonObject], cast(JsonObject, document["search"])["finalists"])
    expected = ((1, 2),) if len(finalists) == 1 else ((1, 4), (2, 3))
    ordered: list[tuple[int, datetime]] = []
    for index, finalist in enumerate(finalists):
        sessions = cast(list[JsonObject], finalist["sessions"])
        positions = tuple(cast(int, item["global_position"]) for item in sessions)
        rounds = tuple(cast(int, item["round"]) for item in sessions)
        if positions != expected[index] or rounds != (1, 2):
            raise fail(path, "confirmation sessions do not follow deterministic ABBA order")
        for session in sessions:
            started = _parse_time(session["started_at"], path)
            finished = _parse_time(session["finished_at"], path)
            if finished < started:
                raise fail(path, "confirmation session finishes before it starts")
            ordered.append((cast(int, session["global_position"]), started))
    starts = [item[1] for item in sorted(ordered)]
    if starts != sorted(starts):
        raise fail(path, "confirmation timestamps contradict ABBA global positions")


def finalist_medians(finalist: JsonObject) -> tuple[float, ...]:
    """Return schema-validated per-round medians for paired selection reconstruction."""
    return tuple(float(value) for value in cast(list[float], finalist["round_medians"]))
