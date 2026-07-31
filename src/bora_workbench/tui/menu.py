"""Summarize each central-menu entry in one short line derived only from the snapshot.

The dashboard answers "what is on this machine" from the menu itself, so a reader never has to
open a section to learn whether it needs attention (`docs/tui.md`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bora_workbench.snapshot import WorkbenchSnapshot

_ACTIVE = "valid"
_BLOCKED = "insufficient-headroom"
EXIT_SUMMARY = "leave the workbench"
PENDING_SUMMARY = "..."
UNAVAILABLE_SUMMARY = "unavailable"


def _run_summary(snapshot: WorkbenchSnapshot) -> str:
    """Report a live service, then blocked cells, then how many modes are tuned.

    A cell the machine cannot afford right now outranks the tuned count, because it is the one
    state the reader can still act on by freeing memory (D-097).
    """
    services = snapshot.services
    if services:
        return f"{services[0].mode} is serving ctx {services[0].ctx}"
    records = snapshot.doctor.records
    if not records:
        return "modes unavailable"
    blocked = sum(record.evaluation.status == _BLOCKED for record in records)
    if blocked:
        return f"{blocked} of {len(records)} short on memory"
    tuned = sum(record.evaluation.status == _ACTIVE for record in records)
    if not tuned:
        return "verified baseline"
    return f"{tuned} of {len(records)} tuned"


def _calibration_summary(snapshot: WorkbenchSnapshot) -> str:
    """Report a ready candidate first, because activation is the one waiting decision."""
    records = snapshot.doctor.records
    if not records:
        return "unavailable"
    candidates = sum(record.evaluation.candidate_status == _ACTIVE for record in records)
    if candidates:
        return f"{candidates} candidate ready"
    active = sum(record.evaluation.status == _ACTIVE for record in records)
    return f"{active} of {len(records)} active" if active else "no active record"


def _setup_summary(snapshot: WorkbenchSnapshot) -> str:
    """Report the first missing prerequisite between the engine and the pinned model."""
    engine = snapshot.doctor.engine
    if not engine.is_active:
        return "engine not active"
    if not engine.is_compatible:
        return "engine does not match the lock"
    model = snapshot.model
    if model is None:
        return "model unavailable"
    if not model.is_managed:
        return "user-managed model"
    return "ready" if model.is_verified else "model not verified"


def _diagnostics_summary(snapshot: WorkbenchSnapshot) -> str:
    """Count blocking packaged-content errors before reporting non-blocking notes."""
    errors = len(snapshot.doctor.validation.errors)
    if errors:
        return f"{errors} packaged-content error(s)"
    unreadable = sum(len(root.inspection.errors) for root in snapshot.service_roots)
    return f"{unreadable} unreadable service record(s)" if unreadable else "no blocking error"


def _pi_summary(snapshot: WorkbenchSnapshot) -> str:
    """Report availability on PATH beside the shared context window when it is known."""
    if not snapshot.pi_installation.is_installed:
        return "not found on PATH"
    context = snapshot.pi_context
    return "installed" if context is None else f"installed, ctx {context.tokens}"


def _settings_summary(snapshot: WorkbenchSnapshot) -> str:
    """Count how many resolved values come from something other than the code defaults."""
    sources = snapshot.doctor.configuration.sources
    values = (
        sources.model,
        sources.model_path,
        sources.llama_port,
        sources.webui_port,
        sources.engine_path,
        sources.open_browser,
    )
    overridden = sum(source != "default" for source in values)
    return "all defaults" if not overridden else f"{overridden} override(s)"


def _installation_summary(snapshot: WorkbenchSnapshot) -> str:
    """Name the installed version without querying any published release."""
    return f"version {snapshot.doctor.version}"


def _exit_summary(snapshot: WorkbenchSnapshot) -> str:
    """Describe the one entry that opens no section, whatever the snapshot holds."""
    del snapshot
    return EXIT_SUMMARY


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """One central-menu row: its label and how it summarizes current local state."""

    label: str
    summarize: Callable[[WorkbenchSnapshot], str]


# Run comes first because launching a mode is the reason the workbench exists; the rest follow
# the order in which a new machine needs them, and Exit closes the list because a reader looks for
# the way out at the bottom (D-097).
ENTRIES: tuple[MenuEntry, ...] = (
    MenuEntry("Run a mode", _run_summary),
    MenuEntry("Calibration", _calibration_summary),
    MenuEntry("Setup", _setup_summary),
    MenuEntry("Diagnostics", _diagnostics_summary),
    MenuEntry("Pi agent", _pi_summary),
    MenuEntry("Settings", _settings_summary),
    MenuEntry("This installation", _installation_summary),
    MenuEntry("Exit", _exit_summary),
)
# Every entry but the last opens the section holding the same position in the application's own
# view order; Exit leaves instead, so it owns no section.
EXIT_INDEX = len(ENTRIES) - 1
SECTION_COUNT = EXIT_INDEX


def summaries(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Summarize every menu entry from one already collected snapshot."""
    return tuple(entry.summarize(snapshot) for entry in ENTRIES)


def failure_summaries() -> tuple[str, ...]:
    """Mark every section unavailable while keeping Exit's own meaning after a failure."""
    return (UNAVAILABLE_SUMMARY,) * SECTION_COUNT + (EXIT_SUMMARY,)
