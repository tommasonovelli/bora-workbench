"""Render installed version, managed roots, and the exact current removal boundary."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.snapshot import WorkbenchSnapshot


def render_installation(snapshot: WorkbenchSnapshot) -> str:
    """Render installation identity and removal scope without probing published releases."""
    doctor = snapshot.doctor
    paths = doctor.paths
    lines = (
        f"Installed version: {doctor.version}",
        "Published version: not queried; bora update --check is the explicit network action.",
        "",
        "Managed roots",
        f"Configuration: {paths.config}",
        f"Data: {paths.data}",
        f"Cache: {paths.cache}",
        f"State: {paths.state}",
        "",
        "Removal boundary",
        "bora uninstall confirms these roots and removes the Python tool only when uv-managed.",
        "The data root includes bora's managed model store.",
        "Pinned Hugging Face cache copies require a second, separate confirmation.",
        "uv itself, pi, unrelated cache content, and user-managed model paths stay untouched.",
    )
    return "\n".join(lines)


class InstallationView(Vertical):
    """Show this package and its managed roots without running update or uninstall."""

    def __init__(self) -> None:
        """Create the hidden-until-selected installation region."""
        super().__init__(classes="section-view")

    def compose(self) -> ComposeResult:
        """Yield the static title and literal detail body."""
        yield Static("This installation", classes="section-title", markup=False)
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with version, roots, and precise exclusions."""
        self.query_one(".section-body", Static).update(render_installation(snapshot))
