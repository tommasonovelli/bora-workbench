"""Offer pi provider actions and show the shared context-window source read-only."""

from __future__ import annotations

from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.actions import (
    compose_pi,
    compose_pi_launch,
    compose_pi_remove,
    compose_pi_uninstall,
)
from bora_workbench.tui.choices import Choice, ChoiceList, Flag
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section

_PRINT = "print-only"
_INSTALL = "install-pi"
_NOTE = (
    "Provider-file contents are not changed or inferred by this screen.",
    "Launch selects bora and the locked model alias; start `bora coding` elsewhere first.",
    "print-only and install-pi exclude each other, so no invalid pair is reachable.",
    "pi, npm, file, backup, and confirmation behavior begins after the workbench closes.",
)
CHOICES: tuple[Choice, ...] = (
    Choice("launch pi with bora", lambda flags: compose_pi_launch()),
    Choice(
        "link the bora provider",
        lambda flags: compose_pi(_PRINT in flags, _INSTALL in flags),
        (Flag("p", _PRINT, _INSTALL), Flag("i", _INSTALL, _PRINT)),
    ),
    Choice("remove the bora provider", lambda flags: compose_pi_remove()),
    Choice("uninstall pi itself", lambda flags: compose_pi_uninstall()),
)


def render_pi(snapshot: WorkbenchSnapshot) -> str:
    """Render only pi facts already carried by the shared non-mutating snapshot."""
    installation = snapshot.pi_installation
    context = snapshot.pi_context
    lines = [
        f"available     {'yes' if installation.is_installed else 'no'}",
        f"executable    {installation.executable or 'not found on PATH'}",
        f"provider      {installation.models_file}",
    ]
    if context is None:
        lines.append("context       unavailable")
    else:
        lines.append(f"context       {context.tokens} tokens from {context.source}")
        lines.extend(f"diagnostic    {item}" for item in context.diagnostics)
    return "\n".join((*lines, "", *_NOTE))


class PiView(Section):
    """Show the one supported pi integration without adding another agent or provider."""

    def __init__(self, palette: Palette) -> None:
        """Create the hidden-until-opened pi section marked on launching the linked agent."""
        super().__init__("Pi", ChoiceList(CHOICES), palette)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with installation and context-source details."""
        self.show_body(render_pi(snapshot))
