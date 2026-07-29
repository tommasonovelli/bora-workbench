"""Render pi installation and shared context-window selection without reading its provider file."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.snapshot import WorkbenchSnapshot


def render_pi(snapshot: WorkbenchSnapshot) -> str:
    """Render only pi facts already carried by the shared non-mutating snapshot."""
    installation = snapshot.pi_installation
    executable = installation.executable or "not found on PATH"
    lines = [
        f"Available: {'yes' if installation.is_installed else 'no'}",
        f"Executable: {executable}",
        f"Provider file: {installation.models_file}",
        "Provider-file contents are not changed or inferred by this screen.",
    ]
    context = snapshot.pi_context
    if context is None:
        lines.extend(("", "Context window: unavailable", "Source: unavailable"))
    else:
        lines.extend(("", f"Context window: {context.tokens} tokens", f"Source: {context.source}"))
        lines.extend(f"Diagnostic: {item}" for item in context.diagnostics)
    return "\n".join(lines)


class PiView(Vertical):
    """Show the one supported pi integration without adding another agent or provider."""

    def __init__(self) -> None:
        """Create the hidden-until-selected pi region."""
        super().__init__(classes="section-view")

    def compose(self) -> ComposeResult:
        """Yield the static title and literal detail body."""
        yield Static("Pi", classes="section-title", markup=False)
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with installation and context-source details."""
        self.query_one(".section-body", Static).update(render_pi(snapshot))
