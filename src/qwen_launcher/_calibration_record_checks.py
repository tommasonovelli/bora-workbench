"""Semantic checks that make a loaded calibration record reproducible evidence.

Schema validation alone cannot prove that the recorded envelope actually follows the noise-robust
selection rule from its own measures. These checks reconstruct the selection (design document
section 3, step 4) and reject any record whose summary, finalists, or envelope disagree.
"""

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
    """Require the stored min/median/max to be derived from the five stored measures."""
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


def _verify_envelope(document: JsonObject, path: Path) -> None:
    """Require the envelope to repeat the selected finalist's exact axis value."""
    selected = _selected_entry(document, path)
    envelope = cast(JsonObject, document["envelope"])
    if envelope["n_cpu_moe"] != selected["n_cpu_moe"]:
        raise _fail(path, "envelope does not match the selected finalist")


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
    _verify_envelope(document, path)
    _verify_selection_rule(document, path)
