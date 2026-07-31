"""Tests for the workbench entry, output acknowledgement, and shared visual hierarchy."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from rich.text import Text
from typer.testing import CliRunner

import bora_workbench.cli as cli_module
import bora_workbench.tui.terminal as terminal_module
from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench.cli import app
from bora_workbench.pi_link import PiInstallation
from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.palette import COLOR_PALETTE, PLAIN_PALETTE
from bora_workbench.tui.screens.modes import ModesView, render_modes
from bora_workbench.tui.screens.pi import render_pi
from bora_workbench.tui.screens.setup import render_setup
from bora_workbench.tui.section import styled_details
from bora_workbench.tui.terminal import TerminalMode
from bora_workbench.webui import OPEN_WEBUI_VERSION, WebuiStatus
from tests.test_cli_tui import _snapshot

runner = CliRunner()


def test_encoding_probe_covers_every_rich_workbench_glyph() -> None:
    """Select plain mode before a legacy encoding reaches wind, sea, or title cells."""
    required = set("╌╍━▰▁▂▃▄▅▆▇█▒▓")

    assert required <= set(terminal_module._LAYOUT_GLYPHS)


def test_explicit_tui_command_is_removed() -> None:
    """Keep the workbench on bare bora instead of retaining a second invocation path."""
    result = runner.invoke(app, ["tui"])

    assert result.exit_code == 2
    assert "No such command 'tui'" in result.stderr


def test_plain_is_rejected_beside_an_explicit_command() -> None:
    """Prevent the root-only presentation flag from being silently ignored by CLI commands."""
    result = runner.invoke(app, ["--plain", "validate"])

    assert result.exit_code == 2
    assert "--plain is available only when opening bare bora" in Text.from_ansi(result.stderr).plain


def test_output_acknowledgement_waits_for_enter_on_a_real_terminal(monkeypatch) -> None:
    """Keep print-only output readable instead of immediately replacing it with Textual."""

    class InteractiveStream:
        """Expose only the terminal capability queried by the acknowledgement helper."""

        def isatty(self) -> bool:
            """Model an interactive stream."""
            return True

    prompts = []
    monkeypatch.setattr(cli_module.sys, "stdin", InteractiveStream())
    monkeypatch.setattr(cli_module.sys, "stdout", InteractiveStream())
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt))

    cli_module._pause_before_workbench_return()

    assert prompts == ["Press Enter to return to Bora Workbench. "]


def test_wide_sections_use_blue_white_hierarchy_and_more_width_than_home() -> None:
    """Give details more room while retaining one blue title and high-contrast panel accents."""

    async def exercise() -> None:
        """Inspect semantic styles and responsive widths in a representative Run section."""
        workbench = WorkbenchApp("0.test", TerminalMode(True, False), lambda version: _snapshot())
        async with workbench.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.1)
            menu_width = workbench.query_one("#menu").size.width
            brand = workbench.query_one("#brand").render()
            assert str(brand) == "▰  Bora Workbench  ▰"
            assert len(brand.spans) == 1 and "#58a9ff" in str(brand.spans[0].style)
            await pilot.press("enter")
            view = workbench.query_one(ModesView)
            assert view.size.width > menu_width
            styles = {
                str(span.style)
                for selector in (".section-actions", ".section-preview", ".section-body")
                for span in view.query_one(selector).render().spans
            }
            assert any("58,169,255" in style or "#58a9ff" in style for style in styles)
            assert any("238,246,255" in style for style in styles)
            assert all("5fd7a7" not in style for style in styles)
            await pilot.press("q")

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        (None, "opens         the integrated llama.cpp interface"),
        (OPEN_WEBUI_VERSION, "opens         Open WebUI, started beside the engine"),
    ],
)
def test_setup_names_which_interface_a_ui_mode_would_open(version, expected) -> None:
    """Answer on the Setup screen the question `studio` used to answer only once it had started."""
    snapshot = _snapshot()
    executable = Path("open-webui") if version else None
    interface = WebuiStatus(Path("open-webui"), version, executable)
    snapshot = replace(snapshot, doctor=replace(snapshot.doctor, webui=interface))

    body = render_setup(snapshot)

    assert "Browser interface" in body
    assert expected in body


def _blocked_snapshot() -> WorkbenchSnapshot:
    """Return the shared fake snapshot with one measured cell the machine cannot afford."""
    snapshot = _snapshot()
    evaluation = RecordEvaluation(
        "insufficient-headroom",
        98304,
        12,
        ("free VRAM 3.30 GiB is below measured need plus the 1.0 GiB reserve (7.40 GiB)",),
    )
    record = replace(snapshot.doctor.records[0], evaluation=evaluation)
    return replace(snapshot, doctor=replace(snapshot.doctor, records=(record,)))


def test_a_cell_short_on_memory_is_named_with_its_reason_and_its_remedy() -> None:
    """Stop the baseline fallback from looking like an ordinary uncalibrated machine (D-097)."""
    body = render_modes(_blocked_snapshot())

    assert "measured cell unavailable now, would launch at ctx 8192" in body
    assert "! Not enough free memory for the measured coding cell(s)." in body
    assert "! coding: free VRAM 3.30 GiB is below measured need" in body
    assert "! Close applications holding RAM or VRAM, then press r to refresh." in body


def test_an_alert_line_is_the_one_red_thing_on_a_blue_and_white_screen() -> None:
    """Render `!` lines in the alert style while every other line keeps the shared identity."""
    styled = styled_details("Launch cells\n! Not enough free memory.", COLOR_PALETTE)

    alert = [span for span in styled.spans if str(span.style) == COLOR_PALETTE.alert_style]
    assert len(alert) == 1
    assert styled.plain.splitlines()[1] == "! Not enough free memory."
    assert styled_details("! blocked", PLAIN_PALETTE).spans[0].style == "bold"


def test_an_absent_pi_is_shown_every_documented_installation_route() -> None:
    """Answer "which command installs it" on the screen itself instead of behind a flag."""
    absent = render_pi(_snapshot())
    installed = render_pi(
        replace(_snapshot(), pi_installation=PiInstallation(Path("pi"), Path("models.json")))
    )

    assert "Installing pi" in absent
    assert "curl -fsSL https://pi.dev/install.sh | sh" in absent
    assert 'powershell -c "irm https://pi.dev/install.ps1 | iex"' in absent
    assert "npm install -g --ignore-scripts @earendil-works/pi-coding-agent" in absent
    assert "npm uninstall -g @earendil-works/pi-coding-agent" in absent
    assert "Installing pi" not in installed
