"""Tests for exact TUI command composition, parsing, selection, and snapshot comparison."""

from __future__ import annotations

import asyncio

import pytest
from typer.main import get_command

from bora_workbench.cli import app
from bora_workbench.pi_link import ContextWindow
from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.actions import (
    CommandSpec,
    compose_doctor,
    compose_engine_status,
    compose_status,
    compose_validate,
    snapshot_changes,
)
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.screens.overview import OverviewView
from bora_workbench.tui.terminal import TerminalMode
from tests.test_cli_tui import _snapshot

_COMPOSERS = (
    (compose_doctor, ("bora", "doctor"), ("doctor",)),
    (compose_validate, ("bora", "validate"), ("validate",)),
    (compose_status, ("bora", "status"), ("status",)),
    (compose_engine_status, ("bora", "engine", "status"), ("engine", "status")),
)


def _parse_leaf(command, arguments: tuple[str, ...], parent=None) -> str:
    """Recursively parse groups to one leaf without invoking any callback."""
    name = command.name or "bora"
    context = command.make_context(name, list(arguments), parent=parent)
    with context:
        protected = tuple(getattr(context, "_protected_args", ()))
        if not hasattr(command, "get_command"):
            assert context.args == [] and protected == ()
            return name
        assert len(protected) == 1
        selected = command.get_command(context, protected[0])
        assert selected is not None
        return _parse_leaf(selected, tuple(context.args), context)


@pytest.mark.parametrize(("compose", "display", "arguments"), _COMPOSERS)
def test_safe_composers_keep_exact_display_and_cli_tokens(compose, display, arguments) -> None:
    """Keep each shown command identical to the real parser arguments after canonical bora."""
    command = compose()

    assert command.display_tokens == display
    assert command.cli_arguments == arguments
    assert command.display == " ".join(display)
    assert command.disposition == "returning"


@pytest.mark.parametrize(("compose", "display", "arguments"), _COMPOSERS)
def test_every_composed_command_recursively_parses_to_a_real_leaf(
    compose, display, arguments
) -> None:
    """Parse through nested Typer groups without executing a command callback."""
    del display
    root = get_command(app)

    leaf = _parse_leaf(root, compose().cli_arguments)

    assert leaf == arguments[-1]


def test_command_spec_rejects_display_argument_divergence() -> None:
    """Prevent a visible command from differing from what same-process dispatch receives."""
    with pytest.raises(ValueError, match="display tokens"):
        CommandSpec(("bora", "doctor"), ("validate",), "returning")


def test_snapshot_comparison_reports_none_or_only_changed_facts() -> None:
    """Keep post-command comparison concise and based on two immutable snapshots."""
    before = _snapshot()
    after = WorkbenchSnapshot(
        before.doctor,
        before.service_roots,
        before.model,
        before.pi_installation,
        ContextWindow(4096, "changed test source"),
        before.diagnostics,
    )

    assert snapshot_changes(before, before) == ("No local snapshot changes detected.",)
    assert snapshot_changes(before, after) == (
        "pi context: (8192, 'test baseline') -> (4096, 'changed test source')",
    )


def test_overview_enter_returns_the_exact_visible_action_after_collection() -> None:
    """Exit Textual with the tab-selected command and its current before-snapshot."""

    async def exercise() -> None:
        """Select status from the visible menu and inspect the app return value."""
        snapshot = _snapshot()
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: snapshot)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            menu = str(workbench.query_one("#overview-actions").render())
            assert "bora doctor" in menu and "bora engine status" in menu
            await pilot.press("tab", "tab", "enter")
            assert workbench.is_running is False
            assert workbench.return_value is not None
            assert workbench.return_value.command == compose_status()
            assert workbench.return_value.snapshot is snapshot

    asyncio.run(exercise())


def test_enter_waits_for_active_snapshot_worker() -> None:
    """Do not dispatch while the sole collector thread still owns incomplete truth."""
    import threading

    started = threading.Event()
    release = threading.Event()

    def collect(version: str) -> WorkbenchSnapshot:
        """Block the fake collector until selection refusal has been observed."""
        started.set()
        release.wait(timeout=3)
        return _snapshot()

    async def exercise() -> None:
        """Press Enter while blocked and assert Textual remains in control."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.05)
            assert started.is_set()
            await pilot.press("enter")
            assert workbench.is_running is True
            assert "Wait for a successful" in str(workbench.query_one("#keybar").render())
            release.set()
            await pilot.pause(0.1)
            await pilot.press("q")

    try:
        asyncio.run(exercise())
    finally:
        release.set()


def test_reopened_app_shows_before_after_difference() -> None:
    """Render a concise comparison only after the reopened app recollects successfully."""
    before = _snapshot()
    after = WorkbenchSnapshot(
        before.doctor,
        before.service_roots,
        before.model,
        before.pi_installation,
        ContextWindow(4096, "after command"),
        (),
    )

    async def exercise() -> None:
        """Inject the before snapshot and inspect comparison text after collection."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: after)
        workbench.set_comparison_snapshot(before)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            changes = str(workbench.query_one(OverviewView).query_one("#changes").render())
            assert "Since the returning command" in changes
            assert "pi context" in changes and "4096" in changes
            await pilot.press("q")

    asyncio.run(exercise())
