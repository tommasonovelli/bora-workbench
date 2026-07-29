"""Render resolved configuration, provenance, path, and environment names read-only."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from bora_workbench.snapshot import WorkbenchSnapshot


def _value(value: object) -> str:
    """Render optional and boolean configuration values without terminal markup."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _setting(label: str, value: object, source: str) -> str:
    """Render one resolved field beside its exact environment override and source."""
    return f"{label}: {_value(value)} (source: {source})"


def render_settings(snapshot: WorkbenchSnapshot) -> str:
    """Render current precedence results without proposing or writing TOML."""
    resolution = snapshot.doctor.configuration
    config = resolution.config
    sources = resolution.sources
    lines = (
        f"Configuration file: {resolution.path}",
        "Precedence: environment > config.toml > defaults",
        "This screen is read-only.",
        "",
        _setting("model [BORA_MODEL]", config.model, sources.model),
        _setting("model_path [BORA_MODEL_PATH]", config.model_path, sources.model_path),
        _setting("llama_port [BORA_LLAMA_PORT]", config.llama_port, sources.llama_port),
        _setting("engine_path [BORA_ENGINE_PATH]", config.engine_path, sources.engine_path),
        _setting("open_browser [BORA_OPEN_BROWSER]", config.open_browser, sources.open_browser),
    )
    return "\n".join(lines)


class SettingsView(Vertical):
    """Show effective settings and provenance without becoming a configuration editor."""

    def __init__(self) -> None:
        """Create the hidden-until-selected settings region."""
        super().__init__(classes="section-view")

    def compose(self) -> ComposeResult:
        """Yield the static title and literal detail body."""
        yield Static("Settings", classes="section-title", markup=False)
        yield Static("Waiting for the local snapshot...", classes="section-body", markup=False)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with resolved values and their shared provenance."""
        self.query_one(".section-body", Static).update(render_settings(snapshot))
