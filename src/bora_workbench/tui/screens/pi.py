"""Offer pi actions in installation order and show the shared context-window source read-only."""

from __future__ import annotations

from bora_workbench.pi_link import (
    UBUNTU_INSTALLER,
    WINDOWS_INSTALLER,
    install_command,
    uninstall_command,
)
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
_NOTE = (
    "- Provider-file contents are not changed or inferred by this screen.",
    "- Launch selects bora and the locked alias; start `bora coding` elsewhere first.",
    "- pi, npm, file, backup, and confirmation behavior starts after this closes.",
)
# The rows follow the order a machine needs them: install, connect, use, then take both back.
CHOICES: tuple[Choice, ...] = (
    Choice(
        "install pi",
        lambda flags: compose_pi(is_installed=True),
        description="Show the npm command, ask once, then connect this machine to pi.",
    ),
    Choice(
        "connect pi to bora",
        lambda flags: compose_pi(_PRINT in flags),
        (Flag("p", _PRINT),),
        "Review or write the provider entry with the context this machine serves.",
    ),
    Choice(
        "launch pi with bora",
        lambda flags: compose_pi_launch(),
        description="Open pi in this terminal with the bora provider and locked alias.",
    ),
    Choice(
        "disconnect pi from bora",
        lambda flags: compose_pi_remove(),
        description="Delete only bora's entry while preserving pi and other providers.",
    ),
    Choice(
        "uninstall pi",
        lambda flags: compose_pi_uninstall(),
        description="Ask npm to remove pi, then separately offer provider removal.",
    ),
)


def _installation_lines(snapshot: WorkbenchSnapshot) -> tuple[str, ...]:
    """Name every documented installation route only while pi is actually missing.

    A reader who cannot find pi needs the exact commands, not a flag to discover (D-097).
    """
    if snapshot.pi_installation.is_installed:
        return ()
    return (
        "",
        "Installing pi",
        f"Ubuntu        {UBUNTU_INSTALLER}",
        f"Windows       {WINDOWS_INSTALLER}",
        f"either        {' '.join(install_command())}",
        f"removal       {' '.join(uninstall_command())}",
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
    installing = _installation_lines(snapshot)
    return "\n".join(("Connection", *lines, *installing, "", "Boundaries", *_NOTE))


class PiView(Section):
    """Show the one supported pi integration without adding another agent or provider."""

    def __init__(self, palette: Palette) -> None:
        """Create the hidden-until-opened pi section marked on installing the agent."""
        super().__init__("Pi agent", ChoiceList(CHOICES), palette)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with installation and context-source details."""
        self.show_body(render_pi(snapshot))
