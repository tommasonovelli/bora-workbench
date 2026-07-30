"""Tests for the workbench entry, output acknowledgement, and shared visual hierarchy."""

from __future__ import annotations

import asyncio

from typer.testing import CliRunner

import bora_workbench.cli as cli_module
import bora_workbench.tui.terminal as terminal_module
from bora_workbench.cli import app
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.screens.modes import ModesView
from bora_workbench.tui.terminal import TerminalMode
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
    assert "--plain is available only when opening bare bora" in result.stderr


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
