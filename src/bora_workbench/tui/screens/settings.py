"""Render resolved configuration, provenance, path, and environment names read-only."""

from __future__ import annotations

from bora_workbench.snapshot import WorkbenchSnapshot
from bora_workbench.tui.choices import ChoiceList
from bora_workbench.tui.palette import Palette
from bora_workbench.tui.section import Section


def _value(value: object) -> str:
    """Render optional and boolean configuration values without terminal markup."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _setting(label: str, value: object, source: str) -> str:
    """Render one resolved field beside its exact environment override and source.

    The source column precedes the value because a resolved model identity is long enough
    to break any column that follows it.
    """
    return f"{label.ljust(34)}{source.ljust(14)}{_value(value)}"


def render_settings(snapshot: WorkbenchSnapshot) -> str:
    """Render current precedence results without proposing or writing TOML."""
    resolution = snapshot.doctor.configuration
    config = resolution.config
    sources = resolution.sources
    lines = (
        f"{'setting [environment]'.ljust(34)}{'source'.ljust(14)}value",
        "",
        _setting("model [BORA_MODEL]", config.model, sources.model),
        _setting("model_path [BORA_MODEL_PATH]", config.model_path, sources.model_path),
        _setting("llama_port [BORA_LLAMA_PORT]", config.llama_port, sources.llama_port),
        _setting("engine_path [BORA_ENGINE_PATH]", config.engine_path, sources.engine_path),
        _setting("open_browser [BORA_OPEN_BROWSER]", config.open_browser, sources.open_browser),
        "",
        f"file          {resolution.path}",
        "precedence    environment > config.toml > defaults; this screen never writes.",
    )
    return "\n".join(lines)


class SettingsView(Section):
    """Show effective settings and provenance without becoming a configuration editor."""

    def __init__(self, palette: Palette) -> None:
        """Create the one section that offers no action because settings stay read-only."""
        super().__init__("Settings", ChoiceList(()), palette)

    def show_snapshot(self, snapshot: WorkbenchSnapshot) -> None:
        """Replace the body with resolved values and their shared provenance."""
        self.show_body(render_settings(snapshot))
