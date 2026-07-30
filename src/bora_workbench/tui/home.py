"""Render the central menu, its one-line verdict, and the decorative wind and sea bands."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from bora_workbench.snapshot import SnapshotFailure, WorkbenchSnapshot
from bora_workbench.tui.advice import next_step
from bora_workbench.tui.menu import ENTRIES, PENDING_SUMMARY, summaries
from bora_workbench.tui.palette import Palette

_BRAND = "B O R A   W O R K B E N C H"
_BRAND_CAP = "▰"
_LABEL_WIDTH = 20


def tagline(snapshot: WorkbenchSnapshot, divider: str) -> str:
    """Compose the one compact fact line shown under the brand."""
    hardware = snapshot.doctor.hardware
    parts = (
        snapshot.doctor.version,
        hardware.cpu_name,
        f"{hardware.ram_total_gib:.1f} GiB",
        hardware.backend,
    )
    return f" {divider} ".join(parts)


class HomeView(Vertical):
    """Own the home surface so the application only routes keys and snapshots to it."""

    def __init__(self, palette: Palette) -> None:
        """Create the central menu marked on its first entry with no facts collected yet."""
        super().__init__(id="home")
        self._palette = palette
        self._index = 0
        self._summaries = (PENDING_SUMMARY,) * len(ENTRIES)

    def compose(self) -> ComposeResult:
        """Yield the wind band, the centred identity and menu, and the sea band."""
        yield Static("", id="wind", markup=False)
        yield Vertical(
            Static(self._brand_text(), id="brand", markup=False),
            Static("inspecting this machine...", id="tagline", markup=False),
            Static("Waiting to inspect this machine.", id="verdict", markup=False),
            Static("", id="hint", markup=False),
            Horizontal(
                Vertical(Static(self._menu_text(), id="menu-rows"), id="menu"), id="menu-box"
            ),
            id="home-centre",
        )
        yield Static("", id="sea", markup=False)

    def _brand_text(self) -> Text:
        """Render a multitone Unicode identity while keeping plain mode strictly ASCII."""
        if self._palette.is_plain:
            return Text(_BRAND, style="bold")
        brand = Text()
        brand.append(f"{_BRAND_CAP}  ", style="#35acc1")
        brand.append("B O R A", style="bold #5fd7a7")
        brand.append("   ", style=self._palette.muted_style)
        brand.append("W O R K B E N C H", style="bold #77b7cf")
        brand.append(f"  {_BRAND_CAP}", style="#35acc1")
        return brand

    @property
    def selected_index(self) -> int:
        """Return the menu position the application should open on Enter."""
        return self._index

    def _menu_text(self) -> Text:
        """Render menu rows with a text marker and a right-hand state summary."""
        text = Text()
        for position, entry in enumerate(ENTRIES):
            is_marked = position == self._index
            marker = f"{self._palette.marker} " if is_marked else "  "
            style = self._palette.selected_style if is_marked else ""
            text.append(f"{marker}{entry.label.ljust(_LABEL_WIDTH)}", style=style)
            text.append(self._summaries[position], style=self._palette.muted_style)
            if position < len(ENTRIES) - 1:
                text.append("\n")
        return text

    def move(self, offset: int) -> None:
        """Move the menu marker with wraparound and no snapshot recollection."""
        self._index = (self._index + offset) % len(ENTRIES)
        self.query_one("#menu-rows", Static).update(self._menu_text())

    def _show_advice(self, headline: str, hint: str) -> None:
        """Replace the two-line verdict and accent an exact suggested command."""
        self.query_one("#verdict", Static).update(Text(headline, style="bold"))
        style = (
            self._palette.accent_style if hint.startswith("bora ") else self._palette.muted_style
        )
        self.query_one("#hint", Static).update(Text(hint, style=style))

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the facts, the verdict, and every menu summary from one snapshot."""
        self.query_one("#tagline", Static).update(tagline(snapshot, self._palette.divider))
        suggestion = next_step(snapshot)
        self._show_advice(suggestion.headline, suggestion.command or suggestion.detail)
        self._summaries = summaries(snapshot)
        self.query_one("#menu-rows", Static).update(self._menu_text())

    def show_failure(self, failure: SnapshotFailure | None, detail: str | None) -> None:
        """Replace stale summaries with the current failed-attempt diagnosis."""
        self.query_one("#tagline", Static).update("local inspection failed")
        if failure is None:
            self._show_advice("Snapshot collection failed.", detail or "unknown failure")
        else:
            suggestion = next_step(failure)
            self._show_advice(suggestion.headline, suggestion.command or failure.detail)
        self._summaries = ("unavailable",) * len(ENTRIES)
        self.query_one("#menu-rows", Static).update(self._menu_text())
