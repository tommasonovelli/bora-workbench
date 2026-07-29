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
    compose_pi,
    compose_pull,
    compose_status,
    compose_stop,
    compose_validate,
    pi_commands,
    setup_commands,
    snapshot_changes,
)
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.screens.overview import OverviewView
from bora_workbench.tui.screens.pi import PiView
from bora_workbench.tui.screens.setup import SetupView
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
        if not hasattr(command, "get_command") or not protected:
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


def _expected_leaf(arguments: tuple[str, ...]) -> str:
    """Return the nested command name represented by one already composed argv."""
    if arguments[0] == "engine":
        return arguments[1]
    if arguments[0] == "pi" and len(arguments) > 1 and not arguments[1].startswith("--"):
        return arguments[1]
    return arguments[0]


def test_setup_commands_enumerate_every_reachable_option_state() -> None:
    """Cover every engine, optional model handle, cache, and dry-run combination."""
    expected_engine = (
        ("engine", "status"),
        ("engine", "install"),
        ("engine", "install", "--no-model"),
        ("engine", "install", "--force"),
        ("engine", "install", "--force", "--no-model"),
    )
    expected_pull = (("pull",), ("pull", "qwen"))
    expected_removal = tuple(
        tuple(token for token in ("rm", model, keep_hf, dry_run) if token is not None)
        for model in (None, "qwen")
        for keep_hf in (None, "--keep-hf")
        for dry_run in (None, "--dry-run")
    )

    commands = setup_commands()

    assert tuple(command.cli_arguments for command in commands) == (
        *expected_engine,
        *expected_pull,
        *expected_removal,
    )


def test_pi_commands_include_every_valid_form_and_no_contradiction() -> None:
    """Keep print-only, installation, and subcommands separate by construction."""
    assert tuple(command.cli_arguments for command in pi_commands()) == (
        ("pi",),
        ("pi", "--print"),
        ("pi", "--install"),
        ("pi", "remove"),
        ("pi", "uninstall"),
    )
    with pytest.raises(ValueError, match="cannot be selected together"):
        compose_pi(is_printed=True, is_installed=True)
    with pytest.raises(ValueError, match="pinned 'qwen'"):
        compose_pull("another-model")  # type: ignore[arg-type]


@pytest.mark.parametrize("command", (compose_stop(), *setup_commands(), *pi_commands()))
def test_every_setup_and_pi_command_recursively_parses(command: CommandSpec) -> None:
    """Parse every reachable E5 form through the real root and nested groups to its leaf."""
    leaf = _parse_leaf(get_command(app), command.cli_arguments)

    assert leaf == _expected_leaf(command.cli_arguments)


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


@pytest.mark.parametrize(
    ("view_type", "navigation_count", "tab_count", "expected"),
    (
        (OverviewView, 0, 4, compose_stop()),
        (SetupView, 3, 4, setup_commands()[4]),
        (PiView, 4, 4, pi_commands()[4]),
    ),
)
def test_actionable_screens_return_the_exact_marked_command(
    view_type, navigation_count: int, tab_count: int, expected: CommandSpec
) -> None:
    """Select stop, full engine flags, and pi uninstall from their visible screen menus."""

    async def exercise() -> None:
        """Navigate, move the action marker, and inspect the post-Textual result."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: _snapshot())
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            if navigation_count:
                await pilot.press(*(["down"] * navigation_count))
            selector = "#overview-actions" if view_type is OverviewView else ".section-actions"
            menu = workbench.query_one(view_type).query_one(selector)
            assert expected.display in str(menu.render())
            await pilot.press(*(["tab"] * tab_count), "enter")
            assert workbench.return_value is not None
            assert workbench.return_value.command == expected

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
