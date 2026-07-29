"""Compose exact CLI commands and compare snapshots without executing either operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bora_workbench.snapshot import WorkbenchSnapshot

CommandDisposition = Literal["returning", "terminal"]


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Keep exact display tokens, parser arguments, and post-command disposition together."""

    display_tokens: tuple[str, ...]
    cli_arguments: tuple[str, ...]
    disposition: CommandDisposition

    def __post_init__(self) -> None:
        """Require display and parser tokens to describe the same current bora command."""
        if not self.cli_arguments or any(not token for token in self.cli_arguments):
            raise ValueError("a composed command requires non-empty CLI arguments")
        if self.display_tokens != ("bora", *self.cli_arguments):
            raise ValueError("display tokens must be 'bora' followed by the exact CLI arguments")

    @property
    def display(self) -> str:
        """Render fixed command tokens exactly as the TUI shows them before dispatch."""
        return " ".join(self.display_tokens)


@dataclass(frozen=True, slots=True)
class TuiResult:
    """Return a selected command and its before-snapshot after Textual has stopped."""

    command: CommandSpec | None
    snapshot: WorkbenchSnapshot | None


def _command(*arguments: str) -> CommandSpec:
    """Build one returning command whose display has the canonical bora executable name."""
    return CommandSpec(("bora", *arguments), arguments, "returning")


def compose_doctor() -> CommandSpec:
    """Compose the existing non-mutating doctor command."""
    return _command("doctor")


def compose_validate() -> CommandSpec:
    """Compose the existing packaged-content validation command."""
    return _command("validate")


def compose_status() -> CommandSpec:
    """Compose the existing managed-service status command."""
    return _command("status")


def compose_engine_status() -> CommandSpec:
    """Compose the existing nested managed-engine status command."""
    return _command("engine", "status")


def overview_commands() -> tuple[CommandSpec, ...]:
    """Return the four E4 diagnostic actions in their stable presentation order."""
    return (compose_doctor(), compose_validate(), compose_status(), compose_engine_status())


def _model_state(snapshot: WorkbenchSnapshot) -> str:
    """Reduce receipt-aware model state to a concise comparison label."""
    model = snapshot.model
    if model is None:
        return "unavailable"
    if model.is_verified:
        return "receipt verified"
    return "user managed" if not model.is_managed else "not verified"


def _record_state(snapshot: WorkbenchSnapshot) -> tuple[tuple[str, str, str], ...]:
    """Reduce active and candidate record states while retaining packaged mode order."""
    return tuple(
        (item.mode_id, item.evaluation.status, item.evaluation.candidate_status)
        for item in snapshot.doctor.records
    )


def _comparison_values(snapshot: WorkbenchSnapshot) -> tuple[tuple[str, object], ...]:
    """Select concise local facts that a returning command could have changed."""
    context = snapshot.pi_context
    context_value = None if context is None else (context.tokens, context.source)
    engine = snapshot.doctor.engine
    return (
        ("running services", len(snapshot.services)),
        ("engine active", engine.is_active),
        ("engine compatible", engine.is_compatible),
        ("model", _model_state(snapshot)),
        ("packaged-content errors", len(snapshot.doctor.validation.errors)),
        ("calibration records", _record_state(snapshot)),
        ("pi available", snapshot.pi_installation.is_installed),
        ("pi context", context_value),
    )


def snapshot_changes(before: WorkbenchSnapshot, after: WorkbenchSnapshot) -> tuple[str, ...]:
    """Describe concise before/after differences without inferring uncollected facts."""
    previous = dict(_comparison_values(before))
    current = dict(_comparison_values(after))
    changes = tuple(
        f"{label}: {previous[label]} -> {value}"
        for label, value in current.items()
        if previous[label] != value
    )
    return changes or ("No local snapshot changes detected.",)
