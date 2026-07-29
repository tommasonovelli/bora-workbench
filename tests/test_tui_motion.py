"""Tests for deterministic, bounded, and optional TUI motion."""

from __future__ import annotations

import asyncio

import pytest
from textual import events

import bora_workbench.tui.app as app_module
from bora_workbench.tui.app import WorkbenchApp
from bora_workbench.tui.motion import (
    FRAME_INTERVAL_SECONDS,
    MAX_FRAMES_PER_SECOND,
    SETTLE_SECONDS,
    MotionConfigurationError,
    MotionDimensions,
    decide_motion,
    gust,
    render_motion_frame,
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


def test_gust_and_sea_are_deterministic_pure_functions() -> None:
    """Bind decorative output only to elapsed time, dimensions, and seed."""
    dimensions = MotionDimensions(120, 40)

    assert gust(0.75, dimensions, 41) == gust(0.75, dimensions, 41)
    assert sea(0.75, dimensions, 41) == sea(0.75, dimensions, 41)
    assert render_motion_frame(0.75, dimensions, 41) != render_motion_frame(1.75, dimensions, 41)
    assert render_motion_frame(SETTLE_SECONDS, dimensions, 41) == render_motion_frame(
        SETTLE_SECONDS + 100.0, dimensions, 41
    )
    assert render_motion_frame(0.75, dimensions, 41) != render_motion_frame(
        0.75, MotionDimensions(100, 30), 42
    )


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
    """Stay below 12 fps on Overview and stop immediately on two runtime switches."""
    intervals: list[float] = []

    async def exercise() -> None:
        """Capture timer requests while driving Overview, navigation, and focus events."""
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
            assert intervals[0] >= 1.0 / MAX_FRAMES_PER_SECOND
            assert workbench.query_one("#motion").display is True
            await pilot.press("down")
            assert workbench._motion_timer is None
            assert workbench.query_one("#motion").display is False
            await pilot.press("up")
            assert intervals == [FRAME_INTERVAL_SECONDS, FRAME_INTERVAL_SECONDS]
            workbench.on_app_blur(events.AppBlur())
            assert workbench._motion_timer is None
            workbench.on_app_focus(events.AppFocus())
            assert len(intervals) == 3
            await pilot.press("q")

    asyncio.run(exercise())


def test_motion_settles_once_without_periodic_wakeups(monkeypatch) -> None:
    """Freeze time beyond three seconds and require Textual's interval to be removed."""
    clock = {"now": 0.0}
    monkeypatch.setattr(app_module, "monotonic", lambda: clock["now"])

    async def exercise() -> None:
        """Advance the fake clock once and verify the settled frame remains static."""
        workbench = WorkbenchApp("0.test", _motion_terminal(), _failed_collection)
        async with workbench.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.05)
            assert workbench._motion_timer is not None
            clock["now"] = SETTLE_SECONDS + 0.1
            workbench._advance_motion()
            settled = str(workbench.query_one("#motion").render())
            assert workbench._motion_timer is None
            clock["now"] = 100.0
            await pilot.pause(0.15)
            assert workbench._motion_timer is None
            assert str(workbench.query_one("#motion").render()) == settled
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
            assert workbench.query_one("#motion").display is False
            await pilot.press("q")

    asyncio.run(exercise())
