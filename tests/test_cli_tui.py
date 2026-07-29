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
from bora_workbench.tui.terminal import TerminalMode
from bora_workbench.validation import ValidationResult

runner = CliRunner()


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
    """Return the plain content held by the markup-disabled overview widget."""
    overview = workbench.query_one("#overview")
    return str(overview.render())


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
    monkeypatch.setattr(tui_app, "run_tui", lambda version, mode: calls.append((version, mode)))

    result = runner.invoke(app, ["tui", "--plain"])

    assert result.exit_code == 0
    assert calls == [("0.3.2", selected)]


@pytest.mark.parametrize(
    ("term", "has_encoding", "reason"),
    (("dumb", True, "TERM=dumb"), ("xterm-256color", False, "output encoding")),
)
def test_terminal_limitations_select_plain_mode(monkeypatch, term, has_encoding, reason) -> None:
    """Use the monochrome layout when the environment cannot support normal chrome."""
    monkeypatch.setattr(terminal_module, "_has_interactive_streams", lambda: True)
    monkeypatch.setattr(terminal_module, "_has_layout_encoding", lambda: has_encoding)
    monkeypatch.setenv("TERM", term)

    selected = terminal_module.inspect_terminal(False)

    assert selected.is_interactive is True and selected.is_plain is True
    assert selected.plain_reason is not None and reason in selected.plain_reason


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
            assert "BORA WORKBENCH" in str(workbench.query_one("#brand").render())
            assert "Local facts will appear here" in _overview_text(workbench)
            await pilot.press("r")
            assert "Refresh queued" in str(workbench.query_one("#snapshot-status").render())
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
            assert "Version: 0.test" in _overview_text(workbench)
            assert "Suggested command: bora engine install" in _overview_text(workbench)
            assert state["maximum"] == 1 and state["calls"] == 2
            await pilot.press("enter")
            assert workbench.is_running is True and state["calls"] == 2
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
            await pilot.press("q")

    asyncio.run(exercise())
