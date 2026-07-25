"""Rank the failures a calibration trial can raise while it is being torn down.

Cleanup runs even when the workload already failed, so two errors can compete for the same trial.
D-058 fixes the order: control flow first, then evidence that invalidates the whole run, then the
diagnostics that only discard one candidate.
"""

from __future__ import annotations

from bora_workbench._calibration_ram import RamError
from bora_workbench._calibration_vram import VramEnvironmentError


def prefer_cleanup_error(current: BaseException | None, new: BaseException) -> BaseException:
    """Prefer control flow, then run-invalidating failures, over candidate diagnostics."""
    if current is not None and not isinstance(current, Exception):
        return current
    if not isinstance(new, Exception):
        return new
    if isinstance(current, (VramEnvironmentError, RamError)):
        return current
    if isinstance(new, (VramEnvironmentError, RamError)):
        return new
    return new if current is None else current
