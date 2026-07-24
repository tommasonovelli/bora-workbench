"""Serialize private spike output and reproducible manifests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from scripts.spike_ctx.models import SearchResult, TrialResult


def write_manifest(root: Path) -> None:
    """Hash every generated evidence file except the manifest itself."""
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}"
        for path in files
    ]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def successful_document(
    searches: dict[int, SearchResult], trials: list[TrialResult], reasoning: str | None
) -> dict[str, object]:
    """Build complete pending-review output without deciding the human Gate."""
    return {
        "schema": "cross-context-spike/v1",
        "decision": "pending-human-review",
        "criteria": {
            "short_e2e_ratio_max": 0.92,
            "long_prefill_ratio_min": 1.25,
            "deadband_pct": 3.0,
            "minimum_extra_free_vram_gib": 0.5,
        },
        "searches": {str(key): asdict(value) for key, value in searches.items()},
        "trials": [asdict(item) for item in trials],
        "reasoning_off_mechanism": reasoning,
    }


def incomplete_document(error: BaseException, trials: list[TrialResult]) -> dict[str, object]:
    """Preserve structured partial evidence when a run cannot reach review."""
    return {
        "schema": "cross-context-spike/v1",
        "decision": "incomplete-run",
        "error_type": type(error).__name__,
        "error": str(error),
        "trials": [asdict(item) for item in trials],
    }


def write_document(root: Path, document: dict[str, object]) -> None:
    """Write one strict, readable result document before computing its manifest."""
    path = root / "results.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
