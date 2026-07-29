"""Define the normal and reduced palettes used by the first read-only TUI shell."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Palette:
    """Name the colors needed by static chrome without coupling them to widgets."""

    background: str
    panel: str
    raised: str
    text: str
    muted: str
    accent: str
    border: str


COLOR_PALETTE = Palette(
    background="#0c1117",
    panel="#111923",
    raised="#172331",
    text="#e7edf4",
    muted="#8fa2b7",
    accent="#69d2a7",
    border="#30475f",
)
PLAIN_PALETTE = Palette(
    background="#000000",
    panel="#000000",
    raised="#000000",
    text="#ffffff",
    muted="#c0c0c0",
    accent="#ffffff",
    border="#ffffff",
)


def _rules(palette: Palette, selector: str, border: str) -> str:
    """Build one complete palette block for either normal or reduced presentation."""
    return f"""
{selector} {{ background: {palette.background}; color: {palette.text}; }}
{selector} #brand {{ background: {palette.raised}; color: {palette.accent}; }}
{selector} #rail {{ background: {palette.panel}; border-right: {border} {palette.border}; }}
{selector} #rail-label {{ color: {palette.muted}; }}
{selector} #selected-view {{ background: {palette.raised}; color: {palette.accent}; }}
{selector} #view-title {{ color: {palette.accent}; }}
{selector} #snapshot-status {{ color: {palette.muted}; }}
{selector} #keybar {{ background: {palette.raised}; color: {palette.muted}; }}
"""


def stylesheet() -> str:
    """Return static layout rules with a class-selected monochrome fallback."""
    layout = """
Screen { overflow: hidden; }
#shell { width: 100%; height: 100%; }
#brand { height: 3; padding: 1 2; text-style: bold; }
#body { height: 1fr; }
#rail { width: 24; padding: 1; }
#rail-label { height: 2; text-style: bold; }
#selected-view { height: 3; padding: 1; text-style: bold; }
#content { width: 1fr; padding: 1 2; }
#view-title { height: 2; text-style: bold; }
#snapshot-status { height: 2; }
#overview { height: 1fr; }
#keybar { height: 3; padding: 1 2; }
"""
    return (
        layout + _rules(COLOR_PALETTE, ".normal", "tall") + _rules(PLAIN_PALETTE, ".plain", "none")
    )
