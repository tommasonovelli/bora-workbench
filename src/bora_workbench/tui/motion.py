"""Generate the bounded decorative wind and sea bands without owning an event loop."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

MAX_FRAMES_PER_SECOND = 12.0
FRAME_INTERVAL_SECONDS = 1.0 / 8.0
SETTLE_SECONDS = 3.0
SEA_ROWS = 2
_MINIMUM_WIDTH = 80
_MINIMUM_HEIGHT = 24
_MAXIMUM_BAND_WIDTH = 160
_MOTION_VALUES = frozenset(("auto", "off"))
# Each row anchors a long streak on one edge and a short one on the other, and the two rows
# swap which edge is long, so the gusts frame the title without mirroring each other (D-087).
_WIND_SHARES = ((0.34, 0.14), (0.15, 0.29))
WIND_ROWS = len(_WIND_SHARES)


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


def _band_width(dimensions: MotionDimensions) -> int:
    """Return the drawable width inside the decorative widget's horizontal padding."""
    return max(1, min(dimensions.width - 4, _MAXIMUM_BAND_WIDTH))


def _streak(length: int, phase: float) -> str:
    """Return one gust that is dense at its anchored edge and thins toward the centre."""
    glyphs = []
    for index in range(length):
        density = 1.0 - index / length
        wave = math.sin(index * 0.8 - phase)
        if wave > 1.0 - density * 1.7:
            glyphs.append("~")
        elif wave > 1.0 - density * 2.2:
            glyphs.append("·")
        else:
            glyphs.append(" ")
    return "".join(glyphs)


def gust(elapsed_seconds: float, dimensions: MotionDimensions, seed: int) -> str:
    """Return the wind rows whose left and right gusts complete each other asymmetrically."""
    width = _band_width(dimensions)
    elapsed = _bounded_elapsed(elapsed_seconds)
    rows = []
    for row, (left_share, right_share) in enumerate(_WIND_SHARES):
        phase = elapsed * 2.6 + row * 1.4 + seed * 0.07
        left = _streak(max(1, int(width * left_share)), phase)
        right = _streak(max(1, int(width * right_share)), phase + 2.1)[::-1]
        gap = max(1, width - len(left) - len(right))
        rows.append(f"{left}{' ' * gap}{right}".rstrip())
    return "\n".join(rows)


def _wave_row(width: int, phase: float, swell: float) -> str:
    """Return one sea row whose crests flatten as the finite animation settles."""
    glyphs = []
    for column in range(width):
        wave = (
            math.sin(column / 3.4 + phase)
            + 0.5 * math.sin(column / 1.7 - phase * 1.6)
            + 0.35 * math.sin(column / 9.0 + phase * 0.5)
        )
        height = wave * swell
        glyphs.append("~" if height >= 0.6 else ("-" if height >= -0.55 else "_"))
    return "".join(glyphs)


def sea(elapsed_seconds: float, dimensions: MotionDimensions, seed: int) -> str:
    """Return the sea rows drawn under the central menu for one bounded moment."""
    width = _band_width(dimensions)
    elapsed = _bounded_elapsed(elapsed_seconds)
    swell = 1.0 - 0.4 * elapsed / SETTLE_SECONDS
    # A per-row column drift keeps the second row from reading as a shifted copy of the first.
    rows = [
        _wave_row(width + row * 11, seed * 0.13 + elapsed * 2.4 + row * 2.3, swell)[row * 11 :]
        for row in range(SEA_ROWS)
    ]
    return "\n".join(rows)
