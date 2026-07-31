"""Tests for the action rows and flag toggles that replace enumerated command menus."""

from __future__ import annotations

import pytest

import bora_workbench.tui.app as app_module
from bora_workbench.tui.actions import compose_engine_install, compose_pi
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.choices import Choice, ChoiceList, Flag

_FORCE = "force"
_NO_MODEL = "no-model"
_PRINT = "print-only"


def _engine_choices() -> tuple[Choice, ...]:
    """Build one flagged action beside one action that accepts no flag."""
    return (
        Choice(
            "install engine",
            lambda flags: compose_engine_install(_FORCE in flags, _NO_MODEL in flags),
            (Flag("f", _FORCE), Flag("n", _NO_MODEL)),
        ),
        Choice("download pinned model", lambda flags: compose_engine_install()),
    )


def test_marker_wraps_around_and_reports_the_visible_rows() -> None:
    """Move only inside one section's own actions and mark exactly one row."""
    choices = ChoiceList(_engine_choices())

    assert choices.rows() == (("install engine", True), ("download pinned model", False))
    choices.move(1)
    assert choices.rows()[1] == ("download pinned model", True)
    choices.move(1)
    assert choices.selected.label == "install engine"
    choices.move(-1)
    assert choices.selected.label == "download pinned model"


def test_flags_compose_the_exact_command_and_survive_a_move() -> None:
    """Keep each action's own flags while the marker visits another action."""
    choices = ChoiceList(_engine_choices())

    assert choices.toggle("f") is True
    assert choices.toggle("n") is True
    assert choices.command() == compose_engine_install(True, True)
    choices.move(1)
    assert choices.toggle("f") is False
    choices.move(-1)
    assert choices.command() == compose_engine_install(True, True)
    assert choices.toggle("f") is True
    assert choices.command() == compose_engine_install(False, True)


def test_contradictory_pi_forms_are_separate_rows_rather_than_one_flag_pair() -> None:
    """Keep printing and installing unreachable together by never offering them as one row."""
    printing = ChoiceList(
        (
            Choice(
                "connect pi to bora",
                lambda flags: compose_pi(_PRINT in flags),
                (Flag("p", _PRINT),),
            ),
        )
    )

    printing.toggle("p")
    assert printing.command() == compose_pi(is_printed=True)
    assert printing.toggle("i") is False
    with pytest.raises(ValueError, match="cannot be selected together"):
        compose_pi(is_printed=True, is_installed=True)


def test_flag_row_names_every_key_and_its_current_state() -> None:
    """Show the toggle keys in text so no colour is needed to read the flag state."""
    choices = ChoiceList(_engine_choices())

    assert choices.flag_row() == "[f] force off   [n] no-model off"
    choices.toggle("n")
    assert choices.flag_row() == "[f] force off   [n] no-model on"
    choices.move(1)
    assert choices.flag_row() == ""


def test_every_declared_flag_key_reaches_an_application_binding() -> None:
    """Keep a new flag from shipping without the key binding that switches it."""
    declared = {flag.key for choice in app_module._FLAGGED_CHOICES for flag in choice.flags}
    bound = {binding.key for binding in WorkbenchApp.BINDINGS}

    assert declared <= set(app_module._TOGGLE_KEYS)
    assert declared <= bound
    assert declared.isdisjoint({"q", "r", "j", "k"})


def test_a_section_without_actions_stays_empty_and_inert() -> None:
    """Let the read-only Settings section hold no action without special-casing it."""
    choices = ChoiceList(())

    assert choices.is_empty is True
    assert choices.rows() == () and choices.flag_row() == ""
    choices.move(1)
    assert choices.index == 0
    assert choices.toggle("f") is False
    with pytest.raises(IndexError):
        choices.command()
