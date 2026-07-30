"""Tests for the lazy, read-only Textual command and its first overview shell."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from typer.testing import CliRunner

import bora_workbench.cli as cli_module
import bora_workbench.tui.app as tui_app
import bora_workbench.tui.terminal as terminal_module
from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench.cli import app
from bora_workbench.config import Config, ConfigResolution, ConfigSources
from bora_workbench.engine import EngineStatus
from bora_workbench.hardware import HardwareInfo
from bora_workbench.models import ModelInspection
from bora_workbench.pi_link import ContextWindow, PiInstallation
from bora_workbench.snapshot import (
    DoctorSnapshot,
    ModeRecordSnapshot,
    PublicPaths,
    SnapshotFailure,
    WorkbenchCollectionError,
    WorkbenchSnapshot,
)
from bora_workbench.tui.actions import (
    CommandSpec,
    TuiResult,
    compose_doctor,
    compose_mode,
    compose_pi_launch,
    compose_uninstall,
    compose_update,
)
from bora_workbench.tui.screens.calibration import CalibrationView
from bora_workbench.tui.screens.installation import InstallationView
from bora_workbench.tui.screens.modes import ModesView
from bora_workbench.tui.screens.overview import OverviewView
from bora_workbench.tui.screens.pi import PiView
from bora_workbench.tui.screens.settings import SettingsView
from bora_workbench.tui.screens.setup import SetupView
from bora_workbench.tui.terminal import TerminalMode
from bora_workbench.validation import ValidationResult

runner = CliRunner()
# One non-colour fact per section, in the order of the central menu.
_VIEW_CASES = (
    (ModesView, "verified baseline, ctx 8192"),
    (CalibrationView, "active absent, pending absent"),
    (SetupView, "does not match engine.lock"),
    (OverviewView, "backend       cpu"),
    (PiView, "8192 tokens from test baseline"),
    (SettingsView, "model [BORA_MODEL]"),
    (InstallationView, "Pinned Hugging Face cache copies need a"),
)


def _doctor() -> DoctorSnapshot:
    """Build deterministic local facts for overview rendering."""
    config = ConfigResolution(
        Config(),
        Path("config.toml"),
        ConfigSources("default", "default", "default", "default", "default"),
    )
    hardware = HardwareInfo(
        "linux", "test", "Test CPU", 12, 32.0, 24.0, "cpu", 0, None, None, None, None
    )
    record = ModeRecordSnapshot(
        "coding", RecordEvaluation("missing", None, None, ("no active record",))
    )
    paths = PublicPaths(Path("config"), Path("data"), Path("cache"), Path("state"))
    engine = EngineStatus(False, None, None, None, False, ("not installed",))
    return DoctorSnapshot(
        "0.test", config, hardware, ValidationResult(()), 1, (record,), engine, paths, {}
    )


def _snapshot() -> WorkbenchSnapshot:
    """Build one complete immutable snapshot without touching the host."""
    return WorkbenchSnapshot(
        _doctor(),
        (),
        ModelInspection("test-model", True, ()),
        PiInstallation(None, Path("models.json")),
        ContextWindow(8192, "test baseline"),
    )


def _overview_text(workbench: tui_app.WorkbenchApp) -> str:
    """Return the plain local report held by the Diagnostics section body."""
    return _view_text(workbench, OverviewView)


def _menu_text(workbench: tui_app.WorkbenchApp) -> str:
    """Return the plain rows of the central menu with their live state summaries."""
    return str(workbench.query_one("#menu-rows").render())


def _verdict_text(workbench: tui_app.WorkbenchApp) -> str:
    """Return the two home lines that carry the one deterministic next step."""
    verdict = str(workbench.query_one("#verdict").render())
    return f"{verdict}\n{workbench.query_one('#hint').render()}"


def _long_snapshot() -> WorkbenchSnapshot:
    """Extend the fake snapshot with enough diagnostics to require small-screen scrolling."""
    snapshot = _snapshot()
    diagnostics = tuple(f"diagnostic line {index}" for index in range(30))
    return WorkbenchSnapshot(
        snapshot.doctor,
        snapshot.service_roots,
        snapshot.model,
        snapshot.pi_installation,
        snapshot.pi_context,
        diagnostics,
    )


def _view_text(workbench: tui_app.WorkbenchApp, view_type: type) -> str:
    """Return the literal body text for one mounted read-only section."""
    return str(workbench.query_one(view_type).query_one(".section-body").render())


def _blocked_snapshot(
    releases: tuple[threading.Event, ...],
    starts: tuple[threading.Event, ...],
    state: dict[str, int],
    lock: threading.Lock,
) -> WorkbenchSnapshot:
    """Measure one serialized fake collector while waiting for its assigned release."""
    with lock:
        index = state["calls"]
        state["calls"] += 1
        state["active"] += 1
        state["maximum"] = max(state["maximum"], state["active"])
    starts[index].set()
    releases[index].wait(timeout=3)
    with lock:
        state["active"] -= 1
    return _snapshot()


def test_non_tty_refusal_does_not_import_textual() -> None:
    """Reject redirected use with exit 2 before any Textual module enters the process."""
    source_root = Path(__file__).parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_root)
    script = """
import json
import sys
from typer.testing import CliRunner
from bora_workbench.cli import app
result = CliRunner().invoke(app, ["tui"])
print(json.dumps({
    "exit_code": result.exit_code,
    "stderr": result.stderr,
    "textual_loaded": any(name == "textual" or name.startswith("textual.") for name in sys.modules),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], env=environment, text=True, capture_output=True, check=True
    )
    result = json.loads(completed.stdout)
    assert result["exit_code"] == 2
    assert "interactive stdin and stdout" in result["stderr"]
    assert result["textual_loaded"] is False


def test_cli_plain_mode_reaches_tui_after_capability_check(monkeypatch) -> None:
    """Pass explicit reduced presentation through the lazy CLI boundary."""
    selected = TerminalMode(True, True, "requested with --plain")
    calls = []
    monkeypatch.setattr(terminal_module, "inspect_terminal", lambda plain: selected)

    def run(version, mode, comparison):
        """Record lazy launch inputs and then model a user quitting immediately."""
        calls.append((version, mode, comparison))
        return TuiResult(None, None)

    monkeypatch.setattr(tui_app, "run_tui", run)

    result = runner.invoke(app, ["tui", "--plain"])

    assert result.exit_code == 0
    assert calls == [("0.4.1", selected, None)]


def test_returning_action_dispatches_after_teardown_then_reopens(monkeypatch) -> None:
    """Run one safe command in process and pass its before-snapshot to a fresh UI lifetime."""
    selected = TerminalMode(True, False)
    snapshot = _snapshot()
    results = iter((TuiResult(compose_doctor(), snapshot), TuiResult(None, _snapshot())))
    events = []

    def run(version, mode, comparison):
        """Model complete terminal teardown before returning one selection."""
        events.append(("tui-stopped", comparison))
        return next(results)

    def dispatch(arguments):
        """Assert dispatch observes a stopped UI and return CLI success."""
        assert events[-1][0] == "tui-stopped"
        events.append(("dispatch", arguments))
        return 0

    monkeypatch.setattr(terminal_module, "inspect_terminal", lambda plain: selected)
    monkeypatch.setattr(tui_app, "run_tui", run)
    monkeypatch.setattr(cli_module, "_dispatch_tui_arguments", dispatch)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("subprocess used"))

    result = runner.invoke(app, ["tui"])

    assert result.exit_code == 0
    assert "Selected command: bora doctor" in result.stdout
    assert events == [
        ("tui-stopped", None),
        ("dispatch", ("doctor",)),
        ("tui-stopped", snapshot),
    ]


@pytest.mark.parametrize(
    "command", (compose_mode("coding"), compose_pi_launch(), compose_update(), compose_uninstall())
)
def test_terminal_action_success_exits_without_reopening(monkeypatch, command: CommandSpec) -> None:
    """Keep foreground, replacement, and removal actions terminal after callback success."""
    selected = TerminalMode(True, False)
    calls = []

    def run(version, mode, comparison):
        """Return one terminal command and fail if another UI lifetime is requested."""
        calls.append(comparison)
        return TuiResult(command, _snapshot())

    monkeypatch.setattr(terminal_module, "inspect_terminal", lambda plain: selected)
    monkeypatch.setattr(tui_app, "run_tui", run)
    monkeypatch.setattr(cli_module, "_dispatch_tui_arguments", lambda arguments: 0)

    result = runner.invoke(app, ["tui"])

    assert result.exit_code == 0
    assert calls == [None]
    assert f"Selected command: {command.display}" in result.stdout


@pytest.mark.parametrize("exit_code", (1, 2, 130))
def test_returning_action_propagates_failure_without_reopening(monkeypatch, exit_code) -> None:
    """Exit with the exact real callback result instead of swallowing a failed handoff."""
    selected = TerminalMode(True, False)
    calls = []

    def run(version, mode, comparison):
        """Return one command and fail if the CLI tries to open another UI lifetime."""
        calls.append(comparison)
        return TuiResult(compose_doctor(), _snapshot())

    monkeypatch.setattr(terminal_module, "inspect_terminal", lambda plain: selected)
    monkeypatch.setattr(tui_app, "run_tui", run)
    monkeypatch.setattr(cli_module, "_dispatch_tui_arguments", lambda arguments: exit_code)

    result = runner.invoke(app, ["tui"])

    assert result.exit_code == exit_code
    assert calls == [None]


def test_same_process_dispatch_invokes_real_typer_leaf_and_maps_interrupt(monkeypatch) -> None:
    """Use the existing root parser directly and retain its successful and interrupted results."""
    calls = []
    monkeypatch.setattr(
        cli_module, "run_doctor", lambda version, stdout, stderr: calls.append(version)
    )

    assert cli_module._dispatch_tui_arguments(("doctor",)) == 0
    assert calls == ["0.4.1"]

    def interrupt(version, stdout, stderr):
        """Raise the interruption the Typer root maps to contractual exit 130."""
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "run_doctor", interrupt)
    assert cli_module._dispatch_tui_arguments(("doctor",)) == 130


def test_encoding_probe_covers_every_rich_home_glyph() -> None:
    """Select plain mode before a legacy encoding reaches wind, sea, or brand cells."""
    required = set("╌╍━▰▁▂▃▄▅▆▇█▒▓")

    assert required <= set(terminal_module._LAYOUT_GLYPHS)


@pytest.mark.parametrize(
    ("term", "has_encoding", "reason"),
    (("dumb", True, "TERM=dumb"), ("xterm-256color", False, "output encoding")),
)
def test_terminal_limitations_select_plain_mode(monkeypatch, term, has_encoding, reason) -> None:
    """Use the monochrome layout when the environment cannot support normal chrome."""
    monkeypatch.setattr(terminal_module, "_has_interactive_streams", lambda: True)
    monkeypatch.setattr(terminal_module, "_has_layout_encoding", lambda: has_encoding)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("BORA_TUI_MOTION", raising=False)
    monkeypatch.setenv("TERM", term)

    selected = terminal_module.inspect_terminal(False)

    assert selected.is_interactive is True and selected.is_plain is True
    assert selected.is_motion_enabled is False
    assert selected.plain_reason is not None and reason in selected.plain_reason


def test_no_color_selects_plain_motion_free_presentation(monkeypatch) -> None:
    """Honor the standard accessibility kill switch before Textual starts."""
    monkeypatch.setattr(terminal_module, "_has_interactive_streams", lambda: True)
    monkeypatch.setattr(terminal_module, "_has_layout_encoding", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("NO_COLOR", "")
    monkeypatch.delenv("BORA_TUI_MOTION", raising=False)

    selected = terminal_module.inspect_terminal(False)

    assert selected.is_plain is True
    assert selected.is_motion_enabled is False
    assert selected.plain_reason == "NO_COLOR is set"


def test_explicit_motion_off_keeps_normal_static_presentation(monkeypatch) -> None:
    """Disable only decoration when the terminal otherwise supports normal styling."""
    monkeypatch.setattr(terminal_module, "_has_interactive_streams", lambda: True)
    monkeypatch.setattr(terminal_module, "_has_layout_encoding", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("BORA_TUI_MOTION", "off")

    selected = terminal_module.inspect_terminal(False)

    assert selected.is_plain is False
    assert selected.is_motion_enabled is False
    assert selected.motion_reason == "BORA_TUI_MOTION=off"


def test_malformed_motion_value_exits_two_before_textual_run(monkeypatch) -> None:
    """Map presentation configuration errors to invalid CLI input without a traceback."""
    monkeypatch.setattr(terminal_module, "_has_interactive_streams", lambda: True)
    monkeypatch.setattr(terminal_module, "_has_layout_encoding", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("BORA_TUI_MOTION", "sometimes")
    monkeypatch.setattr(tui_app, "run_tui", lambda *args: pytest.fail("Textual started"))

    result = runner.invoke(app, ["tui"])

    assert result.exit_code == 2
    assert "BORA_TUI_MOTION must be one of: auto, off" in result.stderr
    assert result.exception is not None
    assert "Traceback" not in result.stderr


def test_first_shell_stays_responsive_while_snapshot_is_blocked() -> None:
    """Mount static chrome and accept refresh while the first collector remains blocked."""
    started = threading.Event()
    release = threading.Event()

    def collect(version: str) -> WorkbenchSnapshot:
        """Block one fake synchronous inspection until the test has observed the shell."""
        started.set()
        release.wait(timeout=3)
        return _snapshot()

    async def exercise() -> None:
        """Drive the headless app without requiring an asynchronous pytest plugin."""
        workbench = tui_app.WorkbenchApp("0.test", TerminalMode(True, False), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.05)
            assert started.is_set()
            assert "B O R A   W O R K B E N C H" in str(workbench.query_one("#brand").render())
            assert "Run" in _menu_text(workbench)
            assert "Waiting for the local snapshot" in _overview_text(workbench)
            await pilot.press("r")
            assert "Refresh queued" in str(workbench.query_one("#status").render())
            release.set()
            await pilot.pause(0.1)
            await pilot.press("q")

    try:
        asyncio.run(exercise())
    finally:
        release.set()


def test_repeated_refreshes_never_overlap_collectors() -> None:
    """Coalesce repeated r keys into one follow-up run after the active run completes."""
    releases = (threading.Event(), threading.Event())
    starts = (threading.Event(), threading.Event())
    state = {"calls": 0, "active": 0, "maximum": 0}
    lock = threading.Lock()

    def collect(version: str) -> WorkbenchSnapshot:
        """Delegate one collector call to the shared concurrency-measuring fake."""
        return _blocked_snapshot(releases, starts, state, lock)

    async def exercise() -> None:
        """Queue several refreshes and release the two expected calls in order."""
        workbench = tui_app.WorkbenchApp("0.test", TerminalMode(True, False), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.05)
            await pilot.press("r", "r", "r")
            await pilot.pause(0.05)
            assert starts[0].is_set() and state["calls"] == 1
            releases[0].set()
            await pilot.pause(0.1)
            assert starts[1].is_set() and state["calls"] == 2
            releases[1].set()
            await pilot.pause(0.1)
            assert "backend       cpu" in _overview_text(workbench)
            assert "bora engine install" in _verdict_text(workbench)
            assert "engine not active" in _menu_text(workbench)
            assert state["maximum"] == 1 and state["calls"] == 2
            await pilot.press("q")

    try:
        asyncio.run(exercise())
    finally:
        for release in releases:
            release.set()


@pytest.mark.parametrize("key", ("q", "ctrl+q", "escape"))
def test_quit_keys_work_while_snapshot_is_blocked(key) -> None:
    """Keep every advertised exit key available while the synchronous worker is busy."""
    started = threading.Event()
    release = threading.Event()

    def collect(version: str) -> WorkbenchSnapshot:
        """Hold the worker long enough for the presentation loop to receive a quit key."""
        started.set()
        release.wait(timeout=3)
        return _snapshot()

    async def exercise() -> None:
        """Press one exit binding while the worker remains inside its blocking callable."""
        workbench = tui_app.WorkbenchApp("0.test", TerminalMode(True, False), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.05)
            assert started.is_set()
            await pilot.press(key)
            assert workbench.is_running is False
            release.set()

    try:
        asyncio.run(exercise())
    finally:
        release.set()


@pytest.mark.parametrize("size", ((60, 20), (80, 24), (120, 40)))
def test_menu_opens_every_read_only_section_at_supported_sizes(size) -> None:
    """Open all seven text-complete sections from the central menu at each test size."""

    async def exercise() -> None:
        """Open each entry in turn and assert one non-colour fact from every section."""
        workbench = tui_app.WorkbenchApp(
            "0.test", TerminalMode(True, False), lambda version: _snapshot()
        )
        async with workbench.run_test(size=size) as pilot:
            await pilot.pause(0.1)
            for index, (view_type, expected) in enumerate(_VIEW_CASES):
                if index:
                    await pilot.press("down")
                await pilot.press("enter")
                assert workbench.query_one(view_type).display is True
                assert expected in _view_text(workbench, view_type)
                await pilot.press("escape")
                assert workbench.query_one(view_type).display is False
            assert "This installation" in _menu_text(workbench)
            await pilot.press("down")
            await pilot.press("enter")
            assert workbench.query_one(ModesView).display is True
            await pilot.press("q")

    asyncio.run(exercise())


def test_small_terminal_detail_can_scroll_without_leaving_the_section() -> None:
    """Reserve page keys for long detail while arrows continue to own the marker."""

    async def exercise() -> None:
        """Scroll a long Diagnostics section in the smallest required headless terminal."""
        workbench = tui_app.WorkbenchApp(
            "0.test", TerminalMode(True, False), lambda version: _long_snapshot()
        )
        async with workbench.run_test(size=(60, 20)) as pilot:
            await pilot.pause(0.1)
            await pilot.press("down", "down", "down", "enter")
            scroller = workbench.query_one("#sections")
            assert scroller.max_scroll_y > 0 and scroller.scroll_y == 0
            await pilot.press("pagedown")
            assert scroller.scroll_y > 0
            assert workbench.query_one(OverviewView).display is True
            await pilot.press("q")

    asyncio.run(exercise())


def test_refresh_and_help_preserve_the_open_section() -> None:
    """Support arrows and j/k while a refresh leaves the open section intact."""
    calls = []

    def collect(version: str) -> WorkbenchSnapshot:
        """Count complete immediate snapshots without touching the host."""
        calls.append(version)
        return _snapshot()

    async def exercise() -> None:
        """Open Settings with mixed keys, refresh it, and inspect expanded key help."""
        workbench = tui_app.WorkbenchApp("0.test", TerminalMode(True, False), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            await pilot.press("j", "down", "j", "j", "down", "right")
            assert workbench.query_one(SettingsView).display is True
            await pilot.press("r")
            await pilot.pause(0.1)
            assert workbench.query_one(SettingsView).display is True and len(calls) == 2
            await pilot.press("question_mark")
            assert "Esc leaves a section" in str(workbench.query_one("#keybar").render())
            await pilot.press("question_mark", "escape", "up", "k", "up", "enter")
            assert workbench.query_one(SetupView).display is True
            await pilot.press("q")

    asyncio.run(exercise())


def test_collection_failure_remains_visible_on_selected_detail_view() -> None:
    """Keep navigation focus while replacing stale detail with failed refresh truth."""
    calls = {"count": 0}
    failure = SnapshotFailure("services", "state became unreadable", 1)

    def collect(version: str) -> WorkbenchSnapshot:
        """Return one snapshot and fail the selected-screen refresh that follows."""
        calls["count"] += 1
        if calls["count"] == 1:
            return _snapshot()
        raise WorkbenchCollectionError(failure)

    async def exercise() -> None:
        """Open Pi, refresh, and assert the same section owns the failure text."""
        workbench = tui_app.WorkbenchApp("0.test", TerminalMode(True, False), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            await pilot.press("down", "down", "down", "down", "enter")
            assert workbench.query_one(PiView).display is True
            await pilot.press("r")
            await pilot.pause(0.1)
            assert workbench.query_one(PiView).display is True
            assert "state became unreadable" in _view_text(workbench, PiView)
            await pilot.press("q")

    asyncio.run(exercise())


def test_collection_failure_is_rendered_without_traceback() -> None:
    """Show structured collection truth in the shell without raising through Textual."""
    failure = SnapshotFailure("configuration", "llama_port must be positive", 2)

    def collect(version: str) -> WorkbenchSnapshot:
        """Raise the same structured expected failure produced by the shared collector."""
        raise WorkbenchCollectionError(failure)

    async def exercise() -> None:
        """Wait for the worker message and inspect the resulting plain presentation."""
        workbench = tui_app.WorkbenchApp("0.test", TerminalMode(True, True), collect)
        async with workbench.run_test() as pilot:
            await pilot.pause(0.1)
            content = _overview_text(workbench)
            assert "Snapshot unavailable" in content
            assert "Configuration error" in content
            assert "llama_port must be positive" in content
            assert "Traceback" not in content
            assert "Configuration error" in _verdict_text(workbench)
            assert "unavailable" in _menu_text(workbench)
            await pilot.press("q")

    asyncio.run(exercise())
