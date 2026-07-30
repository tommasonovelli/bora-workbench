"""Tests for deterministic, continuous, colourful, and optional TUI motion."""

from __future__ import annotations

import asyncio

import pytest
from rich.text import Text
from textual import events

import bora_workbench.tui.app as app_module
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.motion import (
    FRAME_INTERVAL_SECONDS,
    MAX_FRAMES_PER_SECOND,
    MOTION_FRAMES_PER_SECOND,
    SEA_ROWS,
    WIND_ROWS,
    MotionConfigurationError,
    MotionDimensions,
    decide_motion,
    gust,
    sea,
    supports_motion_size,
)
from bora_workbench.tui.terminal import TerminalMode


def _failed_collection(version: str):
    """End the unrelated snapshot worker without touching host state."""
    raise RuntimeError(f"no snapshot for {version}")


def _motion_terminal() -> TerminalMode:
    """Return a normal terminal mode with automatic motion enabled."""
    return TerminalMode(True, False, None, True, None)


def test_gust_and_sea_are_deterministic_continuous_pure_functions() -> None:
    """Bind ongoing decorative output only to elapsed time, dimensions, and seed."""
    dimensions = MotionDimensions(120, 40)

    for band in (gust, sea):
        first = band(0.75, dimensions, 41)
        assert isinstance(first, Text)
        assert first == band(0.75, dimensions, 41)
        assert first != band(1.75, dimensions, 41)
        assert band(3.0, dimensions, 41) != band(103.0, dimensions, 41)
        assert first != band(0.75, MotionDimensions(100, 30), 42)


def test_wind_and_sea_use_full_width_unicode_layers_and_multiple_colours() -> None:
    """Render richer cells than ASCII strokes and retain more than one colour per band."""
    dimensions = MotionDimensions(120, 40)
    wind = gust(0.75, dimensions, 41)
    water = sea(0.75, dimensions, 41)
    expected_width = dimensions.width - 4

    assert len(wind.plain.split("\n")) == WIND_ROWS
    assert len(water.plain.split("\n")) == SEA_ROWS
    assert all(len(row) == expected_width for row in wind.plain.split("\n"))
    assert all(len(row) == expected_width for row in water.plain.split("\n"))
    assert set(wind.plain) & set("·╌╍━")
    assert set(water.plain) & set("▁▂▃▄▅▆▇█▒▓")
    assert len({str(span.style) for span in wind.spans}) >= 3
    assert len({str(span.style) for span in water.spans}) >= 3


@pytest.mark.parametrize(
    ("environment", "is_plain", "is_enabled"),
    (
        ({}, False, True),
        ({"BORA_TUI_MOTION": "auto"}, False, True),
        ({}, True, False),
        ({"BORA_TUI_MOTION": "off"}, False, False),
    ),
)
def test_motion_decision_accepts_only_documented_modes(
    environment: dict[str, str], is_plain: bool, is_enabled: bool
) -> None:
    """Keep static presentation available under explicit and capability kill switches."""
    assert decide_motion(is_plain, environment).is_enabled is is_enabled


@pytest.mark.parametrize("value", ("", "on", "AUTO", "false", "0"))
def test_motion_decision_rejects_undocumented_values(value: str) -> None:
    """Reject ambiguous environment values instead of silently changing presentation."""
    with pytest.raises(MotionConfigurationError, match="BORA_TUI_MOTION"):
        decide_motion(False, {"BORA_TUI_MOTION": value})


def test_motion_size_boundary_keeps_small_layout_static() -> None:
    """Require the complete 80x24 layout before spending rows on decoration."""
    assert supports_motion_size(MotionDimensions(80, 24)) is True
    assert supports_motion_size(MotionDimensions(79, 24)) is False
    assert supports_motion_size(MotionDimensions(80, 23)) is False


def test_motion_timer_is_capped_and_stops_on_navigation_and_focus_loss() -> None:
    """Stay below 12 fps on the central menu and stop immediately on runtime switches."""
    intervals: list[float] = []

    async def exercise() -> None:
        """Capture timer requests while driving home navigation and focus events."""
        workbench = WorkbenchApp("0.test", _motion_terminal(), _failed_collection)
        original = workbench.set_interval

        def capture_interval(interval, callback=None, **kwargs):
            """Record the requested frame period and delegate to Textual's real timer."""
            intervals.append(interval)
            return original(interval, callback, **kwargs)

        workbench.set_interval = capture_interval
        async with workbench.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.05)
            assert intervals == [FRAME_INTERVAL_SECONDS]
            assert MOTION_FRAMES_PER_SECOND <= MAX_FRAMES_PER_SECOND
            assert intervals[0] >= 1.0 / MAX_FRAMES_PER_SECOND
            assert workbench.query_one("#wind").display is True
            assert workbench.query_one("#sea").display is True
            await pilot.press("enter")
            assert workbench._motion_timer is None
            assert workbench.query_one("#wind").display is True
            assert workbench.query_one("#sea").display is True
            frozen = str(workbench.query_one("#sea").render())
            await pilot.pause(FRAME_INTERVAL_SECONDS * 1.5)
            assert str(workbench.query_one("#sea").render()) == frozen
            await pilot.press("escape")
            assert intervals == [FRAME_INTERVAL_SECONDS, FRAME_INTERVAL_SECONDS]
            workbench.on_app_blur(events.AppBlur())
            assert workbench._motion_timer is None
            workbench.on_app_focus(events.AppFocus())
            assert len(intervals) == 3
            await pilot.press("q")

    asyncio.run(exercise())


def test_motion_off_retains_static_graphics_on_home_and_sections() -> None:
    """Keep the requested visual identity while removing every periodic wakeup."""

    async def exercise() -> None:
        """Open one section and require the same static decorative frame around it."""
        terminal = TerminalMode(True, False, None, False, "BORA_TUI_MOTION=off")
        workbench = WorkbenchApp("0.test", terminal, _failed_collection)
        async with workbench.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.05)
            initial = str(workbench.query_one("#sea").render())
            assert workbench._motion_timer is None
            assert workbench.query_one("#wind").display is True
            assert workbench.query_one("#sea").display is True
            await pilot.press("enter")
            assert workbench._motion_timer is None
            assert str(workbench.query_one("#sea").render()) == initial
            await pilot.press("q")

    asyncio.run(exercise())


def test_motion_continues_while_the_home_remains_focused(monkeypatch) -> None:
    """Keep changing frames beyond the former three-second settlement boundary."""
    clock = {"now": 0.0}
    monkeypatch.setattr(app_module, "monotonic", lambda: clock["now"])

    async def exercise() -> None:
        """Advance the fake clock twice and require the same active timer to survive."""
        workbench = WorkbenchApp("0.test", _motion_terminal(), _failed_collection)
        async with workbench.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.05)
            initial = str(workbench.query_one("#sea").render())
            clock["now"] = 4.0
            workbench._advance_motion()
            later = str(workbench.query_one("#sea").render())
            assert workbench._motion_timer is not None
            assert later != initial
            clock["now"] = 104.0
            workbench._advance_motion()
            assert workbench._motion_timer is not None
            assert str(workbench.query_one("#sea").render()) != later
            await pilot.press("q")

    asyncio.run(exercise())


def test_small_terminal_never_creates_motion_timer() -> None:
    """Retain the complete static dashboard without periodic work at 60x20."""

    async def exercise() -> None:
        """Mount below the motion size boundary and inspect the presentation state."""
        workbench = WorkbenchApp("0.test", _motion_terminal(), _failed_collection)
        async with workbench.run_test(size=(60, 20)) as pilot:
            await pilot.pause(0.1)
            assert workbench._motion_timer is None
            assert workbench.query_one("#wind").display is False
            assert workbench.query_one("#sea").display is False
            await pilot.press("q")

    asyncio.run(exercise())
