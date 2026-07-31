"""Show this installation's version and managed roots beside the two update actions.

Removal is deliberately absent. `bora uninstall` refuses while a managed service is running and
replaces the environment of the process that dispatched it, so its refusals and its progress belong
in a terminal the workbench has not just torn down; it stays an explicit command line operation
(D-097).
"""

from __future__ import annotations

from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.actions import compose_update, compose_update_check
from bora_workbench.tui.choices import Choice, ChoiceList
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section

CHOICES: tuple[Choice, ...] = (
    Choice(
        "check for a newer release",
        lambda flags: compose_update_check(),
        description="Query GitHub Releases without installing or replacing anything.",
    ),
    Choice(
        "update to the newest release",
        lambda flags: compose_update(),
        description="Verify the newest wheel and schedule uv replacement after exit.",
    ),
)


def render_installation(snapshot: WorkbenchSnapshot) -> str:
    """Render installation identity and removal scope without probing published releases."""
    doctor = snapshot.doctor
    paths = doctor.paths
    lines = (
        "Installed release",
        f"version       {doctor.version} installed; the published version is not queried.",
        "",
        "Managed roots",
        f"config        {paths.config}",
        f"data          {paths.data}",
        f"cache         {paths.cache}",
        f"state         {paths.state}",
        "",
        "Removing bora",
        "- Removal is a command line operation: run `bora uninstall` in a terminal.",
        "- It stops for a running managed service, so run `bora stop` first.",
        "- It removes these four roots, including the managed model store and Open WebUI.",
        "- The Python tool is removed only when uv owns this installation.",
        "- Pinned Hugging Face copies require a second, separate confirmation.",
        "- uv, pi, and user-managed model paths remain outside the boundary.",
    )
    return "\n".join(lines)


class InstallationView(Section):
    """Show this package and its managed roots without running update or uninstall."""

    def __init__(self, palette: Palette) -> None:
        """Create the hidden-until-opened installation section marked on the update check."""
        super().__init__("This installation", ChoiceList(CHOICES), palette)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with version, roots, and precise removal boundary."""
        self.show_body(render_installation(snapshot))
