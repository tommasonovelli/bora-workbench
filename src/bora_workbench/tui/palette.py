"""Define foreground-only palettes that keep the terminal's own background visible."""

from __future__ import annotations

from dataclasses import dataclass

# Every surface asks for the terminal's default background instead of painting one, so the
# workbench sits inside the user's own theme (D-083 presentation boundary).
TERMINAL_BACKGROUND = "ansi_default"


@dataclass(frozen=True, slots=True)
class Palette:
    """Name the CSS colours of the chrome beside the Rich styles used for inline marking."""

    text: str
    muted: str
    accent: str
    wind: str
    sea: str
    border: str
    marker: str
    divider: str
    selected_style: str
    muted_style: str
    accent_style: str


COLOR_PALETTE = Palette(
    text=TERMINAL_BACKGROUND,
    muted="#7f8ea3",
    accent="#5fd7a7",
    wind="#a6c8e0",
    sea="#4d9fc9",
    border="#3c5a72",
    marker="▸",
    divider="·",
    selected_style="bold #5fd7a7",
    muted_style="#7f8ea3",
    accent_style="#5fd7a7",
)
PLAIN_PALETTE = Palette(
    text=TERMINAL_BACKGROUND,
    muted=TERMINAL_BACKGROUND,
    accent=TERMINAL_BACKGROUND,
    wind=TERMINAL_BACKGROUND,
    sea=TERMINAL_BACKGROUND,
    border=TERMINAL_BACKGROUND,
    marker=">",
    divider="|",
    selected_style="bold",
    muted_style="none",
    accent_style="bold",
)


def palette_for(is_plain: bool) -> Palette:
    """Return the reduced monochrome palette only when the terminal requires it."""
    return PLAIN_PALETTE if is_plain else COLOR_PALETTE


def _rules(palette: Palette, selector: str, border: str) -> str:
    """Build one complete colour block for either normal or reduced presentation."""
    return f"""
{selector} {{ color: {palette.text}; }}
{selector} #brand {{ color: {palette.accent}; }}
{selector} #tagline {{ color: {palette.muted}; }}
{selector} #verdict {{ color: {palette.text}; }}
{selector} #hint {{ color: {palette.muted}; }}
{selector} #menu {{ border: {border} {palette.border}; }}
{selector} #wind {{ color: {palette.wind}; }}
{selector} #sea {{ color: {palette.sea}; }}
{selector} .section-title {{ color: {palette.accent}; }}
{selector} .section-preview {{ color: {palette.accent}; }}
{selector} #status {{ color: {palette.muted}; }}
{selector} #keybar {{ color: {palette.muted}; }}
"""


def stylesheet() -> str:
    """Return static layout rules with a class-selected monochrome fallback."""
    layout = f"""
Screen {{ overflow: hidden; background: {TERMINAL_BACKGROUND}; }}
#shell {{ width: 100%; height: 100%; background: {TERMINAL_BACKGROUND}; }}
#home {{ width: 100%; height: 1fr; }}
#home-centre {{ width: 100%; height: 1fr; align: center middle; }}
#wind {{ dock: top; width: 100%; height: 2; padding: 0 2; }}
#sea {{ dock: bottom; width: 100%; height: 2; padding: 0 2; }}
#brand {{ width: 100%; height: 1; text-align: center; text-style: bold; }}
#tagline {{ width: 100%; height: 1; text-align: center; }}
#verdict {{ width: 100%; height: 1; text-align: center; margin-top: 1; }}
#hint {{ width: 100%; height: 1; text-align: center; }}
#menu-box {{ width: 100%; height: auto; align-horizontal: center; margin-top: 1; }}
#menu {{ width: 64; max-width: 100%; height: auto; padding: 0 2; }}
#menu-rows {{ width: 100%; height: auto; }}
#sections {{ width: 100%; height: 1fr; padding: 1 2; scrollbar-gutter: stable; }}
.section-view {{ width: 100%; height: auto; }}
.section-title {{ width: 100%; height: 2; text-style: bold; }}
.section-actions {{ width: 100%; height: auto; }}
.section-preview {{ width: 100%; height: 1; margin: 1 0; }}
.section-body {{ width: 100%; height: auto; }}
#status {{ width: 100%; height: 1; padding: 0 2; }}
#keybar {{ width: 100%; height: 1; padding: 0 2; }}
"""
    normal = _rules(COLOR_PALETTE, ".normal", "round")
    return layout + normal + _rules(PLAIN_PALETTE, ".plain", "ascii")
