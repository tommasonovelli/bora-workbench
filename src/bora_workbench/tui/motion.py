"""Generate bounded decorative TUI motion without owning an event loop."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

MAX_FRAMES_PER_SECOND = 12.0
FRAME_INTERVAL_SECONDS = 1.0 / 8.0
SETTLE_SECONDS = 3.0
_MINIMUM_WIDTH = 80
_MINIMUM_HEIGHT = 24
_MOTION_VALUES = frozenset(("auto", "off"))


class MotionConfigurationError(ValueError):
    """Report an unsupported TUI motion environment value as invalid CLI input."""


@dataclass(frozen=True, slots=True)
class MotionDimensions:
    """Group terminal dimensions so pure frame functions keep a narrow signature."""

    width: int
    height: int


@dataclass(frozen=True, slots=True)
class MotionDecision:
    """State whether optional motion is enabled and why it may be disabled."""

    is_enabled: bool
    reason: str | None = None


def read_motion_value(environment: Mapping[str, str]) -> str:
    """Read only the documented auto/off values from ``BORA_TUI_MOTION``."""
    value = environment.get("BORA_TUI_MOTION", "auto")
    if value not in _MOTION_VALUES:
        expected = ", ".join(sorted(_MOTION_VALUES))
        raise MotionConfigurationError(
            f"BORA_TUI_MOTION must be one of: {expected}; received {value!r}."
        )
    return value


def decide_motion(is_plain: bool, environment: Mapping[str, str]) -> MotionDecision:
    """Apply explicit and accessibility kill switches before Textual starts."""
    value = read_motion_value(environment)
    if is_plain:
        return MotionDecision(False, "plain presentation")
    if value == "off":
        return MotionDecision(False, "BORA_TUI_MOTION=off")
    return MotionDecision(True)


def supports_motion_size(dimensions: MotionDimensions) -> bool:
    """Keep decorative rows out of terminals smaller than the complete 80x24 layout."""
    return dimensions.width >= _MINIMUM_WIDTH and dimensions.height >= _MINIMUM_HEIGHT


def _bounded_elapsed(elapsed_seconds: float) -> float:
    """Clamp time to the finite animation window so settled frames never drift."""
    return min(max(elapsed_seconds, 0.0), SETTLE_SECONDS)


def gust(elapsed_seconds: float, dimensions: MotionDimensions, seed: int) -> str:
    """Return one deterministic sparse wind line for time, dimensions, and seed."""
    width = max(1, min(dimensions.width - 8, 96))
    elapsed = _bounded_elapsed(elapsed_seconds)
    step = int(elapsed * 10.0)
    particles = max(2, min(6, width // 16))
    line = [" "] * width
    for index in range(particles):
        position = (seed * 7 + dimensions.height + index * 19 + step) % width
        line[position] = "." if index % 2 else "*"
    return "".join(line).rstrip()


def sea(elapsed_seconds: float, dimensions: MotionDimensions, seed: int) -> str:
    """Return one deterministic settling sea line for time, dimensions, and seed."""
    width = max(1, min(dimensions.width - 8, 96))
    elapsed = _bounded_elapsed(elapsed_seconds)
    phase = seed * 0.13 + elapsed * 2.4
    amplitude = max(1.0, min(3.0, dimensions.height / 12.0))
    glyphs = []
    for column in range(width):
        wave = math.sin(column / 4.5 + phase) * amplitude
        glyphs.append("~" if wave >= 0.0 else "_")
    return "".join(glyphs)


def render_motion_frame(elapsed_seconds: float, dimensions: MotionDimensions, seed: int) -> str:
    """Combine decorative gust and sea rows without carrying unique information."""
    wind_line = gust(elapsed_seconds, dimensions, seed)
    sea_line = sea(elapsed_seconds, dimensions, seed)
    return f"wind  {wind_line}\nsea   {sea_line}"
