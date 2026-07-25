"""Promote one calibration run's private logs and rotate the managed evidence slot safely."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

_RUN_ID = re.compile(r"^[0-9a-f]{32}$")


def evidence_directory(calibration_root: Path) -> Path:
    """Return the managed evidence directory without creating it."""
    return calibration_root / "evidence"


def _rotate(destination: Path) -> None:
    """Delete only older UUID-named managed evidence after the new run is in place."""
    for child in destination.parent.iterdir():
        if child == destination or not child.is_dir() or not _RUN_ID.fullmatch(child.name):
            continue
        shutil.rmtree(child)


def preserve_evidence(calibration_root: Path, runtime_root: Path, run_id: str) -> Path:
    """Promote runtime logs to the latest evidence slot before removing the prior slot."""
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("calibration evidence run id must be 32 lowercase hexadecimal characters")
    directory = evidence_directory(calibration_root)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / run_id
    if destination.exists():
        raise FileExistsError(f"calibration evidence destination already exists: {destination}")
    runtime_root.replace(destination)
    _rotate(destination)
    return destination
