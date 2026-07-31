"""Tests for the one-line state summaries carried by the central menu."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench.pi_link import PiInstallation
from bora_workbench.process import ServiceInspection
from bora_workbench.snapshot import ModeRecordSnapshot, ServiceRootSnapshot, WorkbenchSnapshot
from bora_workbench.tui.home import tagline
from bora_workbench.tui.menu import (
    ENTRIES,
    EXIT_INDEX,
    SECTION_COUNT,
    failure_summaries,
    summaries,
)
from bora_workbench.validation import ValidationIssue, ValidationResult
from tests.test_cli_tui import _snapshot
from tests.test_tui_advice import _engine, _model, _service

(
    _RUN,
    _CALIBRATION,
    _SETUP,
    _DIAGNOSTICS,
    _PI,
    _SETTINGS,
    _INSTALLATION,
    _EXIT,
) = range(len(ENTRIES))


def _with_records(evaluations: tuple[RecordEvaluation, ...]) -> WorkbenchSnapshot:
    """Replace the packaged records of the shared fake snapshot in packaged order."""
    modes = ("coding", "studio", "vstudio")
    records = tuple(
        ModeRecordSnapshot(mode, evaluation)
        for mode, evaluation in zip(modes, evaluations, strict=False)
    )
    return replace(_snapshot(), doctor=replace(_snapshot().doctor, records=records))


def test_every_entry_summarizes_a_freshly_installed_machine() -> None:
    """Report the baseline, the missing engine, and the absent pi in one line each."""
    result = summaries(_snapshot())

    assert len(result) == len(ENTRIES)
    assert result[_RUN] == "verified baseline"
    assert result[_CALIBRATION] == "no active record"
    assert result[_SETUP] == "engine not active"
    assert result[_DIAGNOSTICS] == "no blocking error"
    assert result[_PI] == "not found on PATH"
    assert result[_SETTINGS] == "all defaults"
    assert result[_INSTALLATION] == "version 0.test"
    assert result[_EXIT] == "leave the workbench"
    assert all(len(item) <= 34 for item in result)


def test_exit_closes_the_menu_and_owns_no_section() -> None:
    """Keep the way out at the bottom and outside the section order the app mirrors."""
    assert ENTRIES[EXIT_INDEX].label == "Exit"
    assert EXIT_INDEX == len(ENTRIES) - 1 == SECTION_COUNT
    assert failure_summaries() == ("unavailable",) * SECTION_COUNT + ("leave the workbench",)


def test_a_cell_this_machine_cannot_afford_outranks_the_tuned_count() -> None:
    """Report the one calibrated state a reader can still act on by freeing memory (D-097)."""
    active = RecordEvaluation("valid", 65536, 12, (), "missing", (), "balanced")
    blocked = RecordEvaluation("insufficient-headroom", 98304, 12, ("free VRAM low",))

    assert summaries(_with_records((active, blocked)))[_RUN] == "1 of 2 short on memory"


def _service_roots() -> tuple[ServiceRootSnapshot, ...]:
    """Wrap one verified live service in the root shape the snapshot exposes."""
    return (ServiceRootSnapshot(Path("state"), ServiceInspection((_service(),))),)


def test_a_live_service_outranks_measured_cells_on_the_run_entry() -> None:
    """Name what is serving now instead of counting records the reader cannot see."""
    with_service = replace(_snapshot(), service_roots=_service_roots())

    assert summaries(with_service)[_RUN] == "coding is serving ctx 65536"


def test_measured_and_candidate_records_change_two_entries() -> None:
    """Count tuned modes for Run and keep a ready candidate primary for Calibration."""
    active = RecordEvaluation("valid", 65536, 12, (), "missing", "balanced")
    pending = RecordEvaluation("missing", None, None, (), "valid")

    tuned = summaries(_with_records((active, pending)))

    assert tuned[_RUN] == "1 of 2 tuned"
    assert tuned[_CALIBRATION] == "1 candidate ready"
    assert summaries(_with_records((active, active)))[_CALIBRATION] == "2 of 2 active"


@pytest.mark.parametrize(
    ("engine", "model", "expected"),
    (
        (_engine(is_active=False), _model(), "engine not active"),
        (_engine(is_compatible=False), _model(), "engine does not match the lock"),
        (_engine(), _model("absent"), "model not verified"),
        (_engine(), _model(), "ready"),
    ),
)
def test_setup_names_only_the_first_missing_prerequisite(engine, model, expected: str) -> None:
    """Report the one step that blocks a launch rather than every incomplete fact."""
    snapshot = _snapshot()
    snapshot = replace(snapshot, doctor=replace(snapshot.doctor, engine=engine), model=model)

    assert summaries(snapshot)[_SETUP] == expected


def test_packaged_content_errors_outrank_unreadable_service_records() -> None:
    """Keep the blocking failure in the Diagnostics summary when both are present."""
    issue = ValidationIssue("error", "engine.lock", "$.release", "invalid release")
    snapshot = _snapshot()
    validation = ValidationResult((issue,))
    snapshot = replace(snapshot, doctor=replace(snapshot.doctor, validation=validation))

    assert summaries(snapshot)[_DIAGNOSTICS] == "1 packaged-content error(s)"


def test_installed_pi_reports_the_shared_context_window() -> None:
    """Show the context a linked agent would receive without reading the provider file."""
    snapshot = replace(_snapshot(), pi_installation=PiInstallation(Path("pi"), Path("models.json")))

    assert summaries(snapshot)[_PI] == "installed, ctx 8192"


def test_tagline_compresses_identity_into_one_line() -> None:
    """Keep version, processor, memory, and backend on the single line under the brand."""
    assert tagline(_snapshot(), "·") == "0.test · Test CPU · 32.0 GiB · cpu"
