"""Compose exact CLI commands and compare snapshots without executing either operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bora_workbench._calibration_types import MEASURABLE_CONTEXT_SCALE, PREFERENCES, Preference
from bora_workbench.snapshot import WorkbenchSnapshot

CommandDisposition = Literal["returning", "terminal"]
ModeId = Literal["coding", "studio", "vstudio"]
CalibrationMode = Literal["coding", "studio", "vstudio", "all"]


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


@dataclass(frozen=True, slots=True)
class CalibrationSelection:
    """Hold one valid measurement route chosen by the calibration wizard."""

    mode: CalibrationMode
    preference: Preference
    is_candidate_only: bool = False
    target_ctx: int | None = None

    def __post_init__(self) -> None:
        """Reject values outside current CLI domains before composing parser tokens."""
        if self.mode not in ("coding", "studio", "vstudio", "all"):
            raise ValueError(f"unsupported calibration mode: {self.mode}")
        if self.preference not in PREFERENCES:
            raise ValueError(f"unsupported calibration preference: {self.preference}")
        if self.target_ctx is not None and self.target_ctx not in MEASURABLE_CONTEXT_SCALE:
            raise ValueError(f"unmeasurable calibration target: {self.target_ctx}")


def _command(*arguments: str) -> CommandSpec:
    """Build one returning command whose display has the canonical bora executable name."""
    return CommandSpec(("bora", *arguments), arguments, "returning")


def _terminal_command(*arguments: str) -> CommandSpec:
    """Build one foreground command that ends the TUI invocation after dispatch."""
    return CommandSpec(("bora", *arguments), arguments, "terminal")


def compose_mode(mode: ModeId, is_force: bool = False) -> CommandSpec:
    """Compose one current foreground mode and its exact memory-gate override."""
    if mode not in ("coding", "studio", "vstudio"):
        raise ValueError(f"unsupported launch mode: {mode}")
    arguments = [mode]
    if is_force:
        arguments.append("--force")
    return _terminal_command(*arguments)


def compose_calibration(selection: CalibrationSelection) -> CommandSpec:
    """Compose a measurement route that cannot contain candidate activation."""
    preference = selection.preference.replace("_", "-")
    arguments = ["calibrate", "--mode", selection.mode, "--preference", preference]
    if selection.is_candidate_only:
        arguments.append("--no-activate")
    if selection.target_ctx is not None:
        arguments.extend(("--target-ctx", str(selection.target_ctx)))
    return _terminal_command(*arguments)


def compose_calibration_activation(mode: ModeId) -> CommandSpec:
    """Compose candidate activation without preference, target, or no-activate flags."""
    if mode not in ("coding", "studio", "vstudio"):
        raise ValueError(f"unsupported candidate mode: {mode}")
    return _terminal_command("calibrate", "--mode", mode, "--activate")


def mode_commands() -> tuple[CommandSpec, ...]:
    """Return every current foreground mode with and without its memory override."""
    return tuple(
        compose_mode(mode, is_force)
        for mode in ("coding", "studio", "vstudio")
        for is_force in (False, True)
    )


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


def compose_engine_install(is_force: bool = False, is_model_skipped: bool = False) -> CommandSpec:
    """Compose engine installation with only its two current optional flags."""
    arguments = ["engine", "install"]
    if is_force:
        arguments.append("--force")
    if is_model_skipped:
        arguments.append("--no-model")
    return _command(*arguments)


def _locked_model(model: Literal["qwen"] | None) -> tuple[str, ...]:
    """Return the optional sole pinned handle without admitting arbitrary model names."""
    if model not in (None, "qwen"):
        raise ValueError("this distribution composes only the pinned 'qwen' model")
    return () if model is None else (model,)


def compose_pull(model: Literal["qwen"] | None = None) -> CommandSpec:
    """Compose pinned-model acquisition with its optional explicit handle."""
    return _command("pull", *_locked_model(model))


def compose_remove_model(
    model: Literal["qwen"] | None = None,
    is_cache_kept: bool = False,
    is_dry_run: bool = False,
) -> CommandSpec:
    """Compose pinned-model removal while retaining every real CLI prompt."""
    arguments = ["rm", *_locked_model(model)]
    if is_cache_kept:
        arguments.append("--keep-hf")
    if is_dry_run:
        arguments.append("--dry-run")
    return _command(*arguments)


def compose_stop() -> CommandSpec:
    """Compose the existing verified managed-service stop command."""
    return _command("stop")


def compose_pi(is_printed: bool = False, is_installed: bool = False) -> CommandSpec:
    """Compose one valid bare pi action and reject the contradictory pair by construction."""
    if is_printed and is_installed:
        raise ValueError("pi print-only and installation cannot be selected together")
    arguments = ["pi"]
    if is_printed:
        arguments.append("--print")
    if is_installed:
        arguments.append("--install")
    return _command(*arguments)


def compose_pi_remove() -> CommandSpec:
    """Compose removal of only bora's pi provider entry."""
    return _command("pi", "remove")


def compose_pi_uninstall() -> CommandSpec:
    """Compose npm removal of pi with the existing separate provider prompt."""
    return _command("pi", "uninstall")


def compose_update_check() -> CommandSpec:
    """Compose the explicit returning network check for a published release."""
    return _command("update", "--check")


def compose_update() -> CommandSpec:
    """Compose self-update as terminal because its helper must observe this process exit."""
    return _terminal_command("update")


def compose_uninstall() -> CommandSpec:
    """Compose self-removal as terminal while retaining every real CLI confirmation."""
    return _terminal_command("uninstall")


def installation_commands() -> tuple[CommandSpec, ...]:
    """Return explicit update check, terminal replacement, then terminal removal."""
    return (compose_update_check(), compose_update(), compose_uninstall())


def overview_commands() -> tuple[CommandSpec, ...]:
    """Return the four E4 diagnostic actions in their stable presentation order."""
    return (compose_doctor(), compose_validate(), compose_status(), compose_engine_status())


def setup_commands() -> tuple[CommandSpec, ...]:
    """Enumerate every reachable setup flag state without an arbitrary argument editor."""
    engine = tuple(
        compose_engine_install(is_force, is_model_skipped)
        for is_force in (False, True)
        for is_model_skipped in (False, True)
    )
    pull = (compose_pull(), compose_pull("qwen"))
    removal = tuple(
        compose_remove_model(model, is_cache_kept, is_dry_run)
        for model in (None, "qwen")
        for is_cache_kept in (False, True)
        for is_dry_run in (False, True)
    )
    return (compose_engine_status(), *engine, *pull, *removal)


def pi_commands() -> tuple[CommandSpec, ...]:
    """Return every valid current pi action and no contradictory option combination."""
    return (
        compose_pi(),
        compose_pi(is_printed=True),
        compose_pi(is_installed=True),
        compose_pi_remove(),
        compose_pi_uninstall(),
    )


def render_command_menu(
    commands: tuple[CommandSpec, ...], selected_index: int, heading: str
) -> str:
    """Render exact commands with a text marker before Enter can select one."""
    lines = [heading]
    lines.extend(
        f"{'>' if index == selected_index else ' '} {command.display}"
        for index, command in enumerate(commands)
    )
    return "\n".join(lines)


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
