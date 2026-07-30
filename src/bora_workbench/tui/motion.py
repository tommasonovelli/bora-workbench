"""Generate continuous multicolour wind and sea bands without owning an event loop."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from rich.text import Text

MAX_FRAMES_PER_SECOND = 12.0
MOTION_FRAMES_PER_SECOND = 6.0
FRAME_INTERVAL_SECONDS = 1.0 / MOTION_FRAMES_PER_SECOND
SEA_ROWS = 3
WIND_ROWS = 3
_MINIMUM_WIDTH = 80
_MINIMUM_HEIGHT = 24
_MAXIMUM_BAND_WIDTH = 160
_MOTION_VALUES = frozenset(("auto", "off"))
_WIND_GLYPHS = (" ", "·", "╌", "╍", "━")
_WIND_COLOURS = ("#3f79ad", "#64a8e8", "#9fd3ff", "#edf8ff")
_LOWER_BLOCKS = (" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")
_SEA_SURFACE_COLOURS = ("#4a9fe3", "#72baff", "#c8e7ff")
_SEA_DEPTH_COLOURS = (("#256ca8", "#368bd6"), ("#174b7d", "#23639d"))
_FOAM_COLOUR = "bold #f4f9ff"

Cell = tuple[str, str | None]
Row = tuple[Cell, ...]


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


@dataclass(frozen=True, slots=True)
class _BandFrame:
    """Carry shared frame values through helpers without broad parameter lists."""

    width: int
    elapsed: float
    seed: int


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


def _band_width(dimensions: MotionDimensions) -> int:
    """Return the bounded drawable width inside each band's horizontal padding."""
    return max(1, min(dimensions.width - 4, _MAXIMUM_BAND_WIDTH))


def _styled_row(cells: Row) -> Text:
    """Coalesce adjacent cell styles so colourful frames remain cheap to render."""
    line = Text()
    if not cells:
        return line
    current_style = cells[0][1]
    glyphs: list[str] = []
    for glyph, style in cells:
        if style != current_style:
            line.append("".join(glyphs), style=current_style)
            glyphs = []
            current_style = style
        glyphs.append(glyph)
    line.append("".join(glyphs), style=current_style)
    return line


def _styled_band(rows: tuple[Row, ...]) -> Text:
    """Join styled rows while preserving terminal-cell colour spans."""
    band = Text()
    for index, row in enumerate(rows):
        band.append_text(_styled_row(row))
        if index < len(rows) - 1:
            band.append("\n")
    return band


def _trail_strength(distance: float, trail: float, ripple: float) -> float:
    """Fade one moving wind trail while leaving rhythmic openings in it."""
    if distance > trail:
        return 0.0
    fade = 1.0 - distance / trail
    return max(0.0, fade * (0.68 + 0.32 * ripple) - 0.12)


def _wind_strength(frame: _BandFrame, row: int, column: int) -> float:
    """Return the strongest of two horizontally travelling ribbons at one cell."""
    cycle = frame.width * 1.32
    speed = 7.0 + row * 1.15
    head = (frame.elapsed * speed + frame.seed * 0.83 + row * cycle * 0.29) % cycle
    trail = frame.width * (0.24 + row * 0.035)
    ripple = 0.5 + 0.5 * math.sin(column * 0.57 - frame.elapsed * 2.2 + row)
    first = _trail_strength((head - column) % cycle, trail, ripple)
    second_head = (head + cycle * (0.47 + row * 0.03)) % cycle
    second = _trail_strength((second_head - column) % cycle, trail * 0.62, 1.0 - ripple)
    return max(first, second * 0.82)


def _wind_cell(strength: float) -> Cell:
    """Map wind intensity to a Unicode stroke and a lightening sky colour."""
    if strength < 0.14:
        return (" ", None)
    glyph_index = min(len(_WIND_GLYPHS) - 1, 1 + int(strength * 3.7))
    colour_index = min(len(_WIND_COLOURS) - 1, int(strength * len(_WIND_COLOURS)))
    return (_WIND_GLYPHS[glyph_index], _WIND_COLOURS[colour_index])


def _wind_row(frame: _BandFrame, row: int) -> Row:
    """Render one sparse wind ribbon row across the available band width."""
    return tuple(_wind_cell(_wind_strength(frame, row, column)) for column in range(frame.width))


def gust(elapsed_seconds: float, dimensions: MotionDimensions, seed: int) -> Text:
    """Return three continuously travelling Unicode wind ribbons with colour depth."""
    frame = _BandFrame(_band_width(dimensions), max(0.0, elapsed_seconds), seed)
    return _styled_band(tuple(_wind_row(frame, row) for row in range(WIND_ROWS)))


def _surface_height(frame: _BandFrame, column: int) -> float:
    """Place the sea surface within the eight vertical slices of its first cell row."""
    phase = frame.elapsed * 1.55 + frame.seed * 0.09
    wave = (
        math.sin(column / 4.7 + phase)
        + 0.48 * math.sin(column / 2.15 - phase * 1.35)
        + 0.28 * math.sin(column / 10.5 + phase * 0.58)
    )
    return min(7.2, max(0.8, 4.1 - wave * 1.65))


def _surface_cell(frame: _BandFrame, column: int) -> Cell:
    """Render one fractional wave cell, brightening occasional moving crests as foam."""
    height = _surface_height(frame, column)
    filled_slices = min(8, max(1, round(8.0 - height)))
    foam = math.sin(column * 0.73 - frame.elapsed * 2.4 + frame.seed) > 0.63
    if height < 2.55 and foam:
        return (_LOWER_BLOCKS[filled_slices], _FOAM_COLOUR)
    colour_index = min(2, max(0, filled_slices // 3))
    return (_LOWER_BLOCKS[filled_slices], _SEA_SURFACE_COLOURS[colour_index])


def _depth_cell(frame: _BandFrame, row: int, column: int) -> Cell:
    """Render one full or shaded water cell with a slowly travelling subsurface current."""
    current = math.sin(column * (0.19 + row * 0.025) - frame.elapsed * (0.7 + row * 0.12))
    crossing = math.sin(column * 0.47 + frame.elapsed * 0.42 + frame.seed * 0.17)
    light = current + crossing * 0.35
    glyph = "▒" if light > 0.92 else ("▓" if light > -0.3 else "█")
    colours = _SEA_DEPTH_COLOURS[row - 1]
    return (glyph, colours[1 if light > 0.25 else 0])


def _sea_row(frame: _BandFrame, row: int) -> Row:
    """Render the fractional surface or one denser water row beneath it."""
    if row == 0:
        return tuple(_surface_cell(frame, column) for column in range(frame.width))
    return tuple(_depth_cell(frame, row, column) for column in range(frame.width))


def sea(elapsed_seconds: float, dimensions: MotionDimensions, seed: int) -> Text:
    """Return a layered fractional-block sea that keeps moving while the home is focused."""
    frame = _BandFrame(_band_width(dimensions), max(0.0, elapsed_seconds), seed)
    return _styled_band(tuple(_sea_row(frame, row) for row in range(SEA_ROWS)))
