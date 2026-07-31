"""Define a blue-and-white foreground palette over the terminal's own background."""

from __future__ import annotations

from dataclasses import dataclass

# Every surface requests the terminal's default background, so bora never paints a window over the
# operator's chosen terminal theme (D-089, refined by D-092).
TERMINAL_BACKGROUND = "ansi_default"


@dataclass(frozen=True, slots=True)
class Palette:
    """Name CSS colours and Rich styles shared by every workbench surface."""

    is_plain: bool
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
    body_style: str
    command_style: str
    alert_style: str


COLOR_PALETTE = Palette(
    is_plain=False,
    text="#eef6ff",
    muted="#9bb3d1",
    accent="#58a9ff",
    wind="#8bc8ff",
    sea="#368bd6",
    border="#356da6",
    marker="▸",
    divider="·",
    selected_style="bold #78bcff",
    muted_style="#9bb3d1",
    accent_style="bold #58a9ff",
    body_style="#eef6ff",
    command_style="bold #73b9ff",
    # Red is the one colour that leaves the blue identity, because a blocked profile is the only
    # fact the workbench reports that the machine cannot currently satisfy (D-097).
    alert_style="bold #ff6b6b",
)
PLAIN_PALETTE = Palette(
    is_plain=True,
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
    body_style="none",
    command_style="bold",
    alert_style="bold",
)


def palette_for(is_plain: bool) -> Palette:
    """Return the reduced monochrome palette only when the terminal requires it."""
    return PLAIN_PALETTE if is_plain else COLOR_PALETTE


def _rules(palette: Palette, selector: str, border: str) -> str:
    """Build one complete colour block for normal or reduced presentation."""
    return f"""
{selector} {{ color: {palette.text}; }}
{selector} #brand {{ color: {palette.accent}; }}
{selector} #tagline {{ color: {palette.muted}; }}
{selector} #verdict {{ color: {palette.text}; }}
{selector} #hint {{ color: {palette.accent}; }}
{selector} #menu {{ border: {border} {palette.border}; }}
{selector} #wind {{ color: {palette.wind}; }}
{selector} #sea {{ color: {palette.sea}; }}
{selector} .section-title {{ color: {palette.accent}; }}
{selector} .section-actions {{ border: {border} {palette.border}; }}
{selector} .section-preview {{ border: {border} {palette.border}; }}
{selector} .section-body {{ border: {border} {palette.border}; }}
{selector} #status {{ color: {palette.muted}; }}
{selector} #keybar {{ color: {palette.muted}; }}
"""


def stylesheet() -> str:
    """Return centred responsive layout rules shared by home and all seven sections."""
    layout = f"""
Screen {{ overflow: hidden; background: {TERMINAL_BACKGROUND}; }}
#shell {{ width: 100%; height: 100%; background: {TERMINAL_BACKGROUND}; }}
#wind {{ width: 100%; height: 3; padding: 0 2; text-align: center; }}
#brand {{ width: 100%; height: 1; text-align: center; text-style: bold; }}
#content {{ width: 100%; height: 1fr; }}
#home {{ width: 100%; height: 1fr; }}
#home-centre {{ width: 100%; height: 1fr; align: center middle; }}
#sea {{ width: 100%; height: 3; padding: 0 2; text-align: center; }}
#tagline {{ width: 100%; height: 1; text-align: center; }}
#verdict {{ width: 100%; height: 1; text-align: center; margin-top: 1; text-style: bold; }}
#hint {{ width: 100%; height: 1; text-align: center; text-style: bold; }}
#menu-box {{ width: 100%; height: auto; align-horizontal: center; margin-top: 1; }}
#menu {{ width: 64; max-width: 100%; height: auto; padding: 0 2; }}
#menu-rows {{ width: 100%; height: auto; }}
#sections {{
    width: 100%; height: 1fr; padding: 1 2;
    scrollbar-gutter: stable; align-horizontal: center;
}}
.section-view {{ width: 112; max-width: 100%; height: auto; }}
.section-title {{ width: 100%; height: 1; margin-bottom: 1; text-align: center; text-style: bold; }}
.section-actions {{ width: 100%; height: auto; padding: 1 2; }}
.section-preview {{ width: 100%; height: auto; min-height: 3; margin-top: 1; padding: 0 2; }}
.section-body {{ width: 100%; height: auto; margin-top: 1; padding: 1 2; }}
#status {{ width: 100%; height: 1; padding: 0 2; }}
#keybar {{ width: 100%; height: 1; padding: 0 2; }}
"""
    normal = _rules(COLOR_PALETTE, ".normal", "round")
    return layout + normal + _rules(PLAIN_PALETTE, ".plain", "ascii")
