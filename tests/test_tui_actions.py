"""Tests for exact TUI command composition, parsing, selection, and snapshot comparison."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from itertools import combinations, product

import pytest
from typer.main import get_command

from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench._calibration_types import MEASURABLE_CONTEXT_SCALE, PREFERENCES
from bora_workbench.cli import app
from bora_workbench.pi_link import ContextWindow
from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui import actions as actions_module
from bora_workbench.tui.actions import (
    CalibrationSelection,
    CommandSpec,
    compose_calibration,
    compose_calibration_activation,
    compose_doctor,
    compose_engine_install,
    compose_engine_status,
    compose_mode,
    compose_pi,
    compose_pi_launch,
    compose_pi_uninstall,
    compose_status,
    compose_stop,
    compose_update,
    compose_update_check,
    compose_validate,
    snapshot_changes,
)
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.choices import Choice, Flag
from bora_workbench.tui.home import HomeView
from bora_workbench.tui.menu import EXIT_INDEX
from bora_workbench.tui.screens import installation as installation_screen
from bora_workbench.tui.screens import modes as modes_screen
from bora_workbench.tui.screens import overview as overview_screen
from bora_workbench.tui.screens import pi as pi_screen
from bora_workbench.tui.screens import setup as setup_screen
from bora_workbench.tui.screens.calibration import CalibrationView
from bora_workbench.tui.screens.installation import InstallationView, render_installation
from bora_workbench.tui.screens.modes import ModesView
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


def _flag_sets(flags: tuple[Flag, ...]) -> tuple[frozenset[str], ...]:
    """Return every flag combination one action's toggles can actually reach."""
    labels = [flag.label for flag in flags]
    return tuple(
        frozenset(names) for size in range(len(labels) + 1) for names in combinations(labels, size)
    )


def _reachable(choices: tuple[Choice, ...]) -> tuple[CommandSpec, ...]:
    """Enumerate every command one section can compose through its own toggles."""
    return tuple(choice.compose(flags) for choice in choices for flags in _flag_sets(choice.flags))


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


_GROUPS = frozenset({"engine", "pi", "webui"})


def _expected_leaf(arguments: tuple[str, ...]) -> str:
    """Return the nested command name represented by one already composed argv.

    A group invoked bare, as `pi` is, resolves to the group itself; every other form resolves to
    the subcommand that follows it.
    """
    if arguments[0] in _GROUPS and len(arguments) > 1 and not arguments[1].startswith("--"):
        return arguments[1]
    return arguments[0]


def _candidate_snapshot() -> WorkbenchSnapshot:
    """Add one valid pending coding candidate to the standard immutable fake snapshot."""
    snapshot = _snapshot()
    evaluation = RecordEvaluation("candidate", None, None, (), "valid")
    record = replace(snapshot.doctor.records[0], evaluation=evaluation)
    doctor = replace(snapshot.doctor, records=(record,))
    return replace(snapshot, doctor=doctor)


def test_setup_toggles_reach_every_engine_and_removal_option_state() -> None:
    """Cover every acquisition and removal state the Setup rows can toggle."""
    commands = _reachable(setup_screen.CHOICES)

    assert tuple(command.cli_arguments for command in commands) == (
        ("engine", "install"),
        ("engine", "install", "--force"),
        ("engine", "install", "--no-model"),
        ("engine", "install", "--no-webui"),
        ("engine", "install", "--force", "--no-model"),
        ("engine", "install", "--force", "--no-webui"),
        ("engine", "install", "--no-model", "--no-webui"),
        ("engine", "install", "--force", "--no-model", "--no-webui"),
        ("pull",),
        ("webui", "install"),
        ("webui", "install", "--force"),
        ("engine", "status"),
        ("rm",),
        ("rm", "--keep-hf"),
        ("rm", "--dry-run"),
        ("rm", "--keep-hf", "--dry-run"),
        ("webui", "remove"),
    )


def test_pi_rows_follow_installation_order_and_reach_every_valid_form() -> None:
    """Offer installation as its own first row and keep the contradictory pair unreachable."""
    commands = _reachable(pi_screen.CHOICES)

    assert tuple(command.cli_arguments for command in commands) == (
        ("pi", "--install"),
        ("pi",),
        ("pi", "--print"),
        ("pi", "launch"),
        ("pi", "remove"),
        ("pi", "uninstall"),
    )
    assert pi_screen.CHOICES[0].label == "install pi"
    assert compose_pi_launch().disposition == "terminal"
    with pytest.raises(ValueError, match="cannot be selected together"):
        compose_pi(is_printed=True, is_installed=True)


@pytest.mark.parametrize(
    "command",
    (
        compose_stop(),
        *_reachable(setup_screen.CHOICES),
        *_reachable(pi_screen.CHOICES),
        *_reachable(overview_screen.CHOICES),
    ),
)
def test_every_setup_and_pi_command_recursively_parses(command: CommandSpec) -> None:
    """Parse every reachable form through the real root and nested groups to its leaf."""
    leaf = _parse_leaf(get_command(app), command.cli_arguments)

    assert leaf == _expected_leaf(command.cli_arguments)


def test_mode_toggles_cover_force_and_stay_terminal() -> None:
    """Compose all three foreground modes with only the exact memory-gate override."""
    commands = _reachable(modes_screen.CHOICES)

    assert tuple(command.cli_arguments for command in commands) == (
        ("coding",),
        ("coding", "--force"),
        ("studio",),
        ("studio", "--force"),
        ("vstudio",),
        ("vstudio", "--force"),
    )
    assert all(command.disposition == "terminal" for command in commands)


def test_every_reachable_calibration_state_parses_without_forbidden_flags() -> None:
    """Enumerate measurement and activation routes through the real recursive parser."""
    root = get_command(app)
    states = product(
        ("coding", "studio", "vstudio", "all"),
        PREFERENCES,
        (False, True),
        (None, *MEASURABLE_CONTEXT_SCALE),
    )
    for mode, preference, is_candidate_only, target in states:
        selection = CalibrationSelection(mode, preference, is_candidate_only, target)
        command = compose_calibration(selection)
        assert command.disposition == "terminal"
        assert "--activate" not in command.cli_arguments
        assert _parse_leaf(root, command.cli_arguments) == "calibrate"
    for mode in ("coding", "studio", "vstudio"):
        command = compose_calibration_activation(mode)
        assert command.cli_arguments[-1] == "--activate"
        assert "--preference" not in command.cli_arguments
        assert "--target-ctx" not in command.cli_arguments
        assert _parse_leaf(root, command.cli_arguments) == "calibrate"


@pytest.mark.parametrize(
    "operation",
    (
        lambda: compose_mode("unknown"),  # type: ignore[arg-type]
        lambda: CalibrationSelection("unknown", "balanced"),  # type: ignore[arg-type]
        lambda: CalibrationSelection("coding", "unknown"),  # type: ignore[arg-type]
        lambda: CalibrationSelection("coding", "balanced", target_ctx=8192),
        lambda: compose_calibration_activation("all"),  # type: ignore[arg-type]
    ),
)
def test_invalid_mode_and_calibration_states_are_unrepresentable(operation) -> None:
    """Reject domains and combinations the wizard never offers."""
    with pytest.raises(ValueError):
        operation()


def test_installation_offers_only_the_two_update_actions() -> None:
    """Keep removal on the command line, where its refusals and prompts belong (D-097)."""
    commands = _reachable(installation_screen.CHOICES)

    assert commands == (compose_update_check(), compose_update())
    assert tuple(command.disposition for command in commands) == ("returning", "terminal")
    for command in commands:
        assert _parse_leaf(get_command(app), command.cli_arguments) == "update"


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


def test_opened_section_enter_returns_the_exact_visible_action_after_collection() -> None:
    """Exit Textual with the marked command of an opened section and its before-snapshot."""

    async def exercise() -> None:
        """Open Diagnostics from the central menu and select its third action."""
        snapshot = _snapshot()
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: snapshot)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            await pilot.press("down", "down", "down", "enter")
            actions = workbench.query_one(OverviewView).query_one(".section-actions")
            assert "full local report" in str(actions.render())
            await pilot.press("down", "down", "enter")
            assert workbench.is_running is False
            assert workbench.return_value is not None
            assert workbench.return_value.command == compose_engine_status()
            assert workbench.return_value.snapshot is snapshot

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("view_type", "menu_count", "move_count", "toggles", "expected"),
    (
        (OverviewView, 3, 4, (), compose_stop()),
        (ModesView, 0, 2, ("f",), compose_mode("vstudio", True)),
        (SetupView, 2, 0, ("f", "n"), compose_engine_install(True, True)),
        (PiView, 4, 4, (), compose_pi_uninstall()),
        (InstallationView, 6, 1, (), compose_update()),
    ),
)
def test_opened_sections_return_the_exact_marked_command(
    view_type, menu_count: int, move_count: int, toggles: tuple[str, ...], expected: CommandSpec
) -> None:
    """Select stop, forced vstudio, fully flagged installation, and pi uninstall."""

    async def exercise() -> None:
        """Open one section, move its marker, switch its flags, and inspect the result."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: _snapshot())
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            await pilot.press(*(["down"] * menu_count), "enter")
            await pilot.press(*(["down"] * move_count), *toggles)
            preview = workbench.query_one(view_type).query_one(".section-preview")
            assert expected.display in str(preview.render())
            await pilot.press("enter")
            assert workbench.return_value is not None
            assert workbench.return_value.command == expected

    asyncio.run(exercise())


def test_calibration_wizard_reaches_review_before_returning_measurement() -> None:
    """Ask every measurement question and expose the exact command only at final review."""

    async def exercise() -> None:
        """Choose max-context, candidate-only, and one approved target step by step."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: _snapshot())
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            await pilot.press("down", "enter")
            assert workbench.is_running is True
            await pilot.press("enter", "down", "enter")
            assert workbench.is_running is True
            await pilot.press("down", "enter", "down", "down", "down", "enter")
            wizard = workbench.query_one(CalibrationView)
            review = str(wizard.query_one(".section-actions").render())
            expected = (
                "bora calibrate --mode coding --preference max-context "
                "--no-activate --target-ctx 65536"
            )
            assert expected in str(wizard.query_one(".section-preview").render())
            assert "real CLI preflight and confirmation follow" in review
            assert workbench.is_running is True and workbench.return_value is None
            await pilot.press("enter")
            assert workbench.return_value is not None
            assert workbench.return_value.command is not None
            assert workbench.return_value.command.display == expected
            assert workbench.return_value.command.disposition == "terminal"

    asyncio.run(exercise())


def test_candidate_activation_skips_preference_and_target_questions() -> None:
    """Offer only snapshot-valid candidate routes and jump directly to exact activation review."""

    async def exercise() -> None:
        """Choose the appended coding candidate route and confirm its two-stage Enter behavior."""
        workbench = WorkbenchApp(
            "0.test", TerminalMode(True, False), lambda version: _candidate_snapshot()
        )
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            await pilot.press("down", "enter", "down", "down", "down", "down", "enter")
            wizard = workbench.query_one(CalibrationView)
            review = str(wizard.query_one(".section-preview").render())
            assert "bora calibrate --mode coding --activate" in review
            assert "--preference" not in review and "--target-ctx" not in review
            assert workbench.is_running is True
            await pilot.press("enter")
            assert workbench.return_value is not None
            assert workbench.return_value.command == compose_calibration_activation("coding")

    asyncio.run(exercise())


def test_the_exit_entry_leaves_without_selecting_a_command() -> None:
    """Give the menu a visible way out that runs nothing, at its last position (D-097)."""

    async def exercise() -> None:
        """Mark the final menu entry and confirm Enter ends the lifetime empty-handed."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: _snapshot())
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            await pilot.press(*(["down"] * EXIT_INDEX))
            assert workbench.query_one(HomeView).selected_index == EXIT_INDEX
            await pilot.press("enter")
            assert workbench.is_running is False
            assert workbench.return_value is not None
            assert workbench.return_value.command is None

    asyncio.run(exercise())


def test_the_workbench_composes_no_removal_of_itself() -> None:
    """Keep `bora uninstall` off every reachable action while still naming it (D-097)."""
    reachable = {
        command.cli_arguments
        for choices in (
            installation_screen.CHOICES,
            modes_screen.CHOICES,
            overview_screen.CHOICES,
            pi_screen.CHOICES,
            setup_screen.CHOICES,
        )
        for command in _reachable(choices)
    }

    assert ("uninstall",) not in reachable
    assert not hasattr(actions_module, "compose_uninstall")
    assert "run `bora uninstall` in a terminal" in render_installation(_snapshot())


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
        """Press Enter inside a section while blocked and assert Textual remains in control."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.05)
            assert started.is_set()
            await pilot.press("enter", "enter")
            assert workbench.is_running is True
            assert "Wait for a successful" in str(workbench.query_one("#status").render())
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
            report = ""
            for _ in range(100):
                await pilot.pause(0.02)
                body = workbench.query_one(OverviewView).query_one(".section-body")
                report = str(body.render())
                if "Since the returning command" in report:
                    break
            assert "Since the returning command" in report
            assert "pi context" in report and "4096" in report
            assert "1 change(s) listed in Diagnostics" in str(
                workbench.query_one("#status").render()
            )
            await pilot.press("q")

    asyncio.run(exercise())
