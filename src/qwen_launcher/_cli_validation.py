"""Present installed-resource or local calibration-bundle validation results."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from qwen_launcher.validation import ValidationIssue, ValidationResult, validate_resources


def _print_issue(item: ValidationIssue, stdout: Console, stderr: Console) -> None:
    """Print one validation issue to the stream appropriate for its severity."""
    label = f"{item.file}:{item.field_path}: {item.message}"
    if item.severity == "error":
        stderr.print(f"[red]ERROR[/red] {label}")
    else:
        stdout.print(f"[yellow]WARNING[/yellow] {label}")


def show_validation(result: ValidationResult, stdout: Console, stderr: Console) -> None:
    """Print deterministic validation details and a concise summary."""
    for item in result.issues:
        _print_issue(item, stdout, stderr)
    if result.errors:
        stderr.print(f"[red]Validation failed:[/red] {len(result.errors)} error(s)")
    else:
        stdout.print(f"[green]Validation passed[/green] with {len(result.warnings)} warning(s)")


def run_validate(source: Path | None, stdout: Console, stderr: Console) -> None:
    """Validate installed content by default or one explicit local Step 5A bundle."""
    if source is None:
        result = validate_resources()
    else:
        from qwen_launcher._calibration_validation import validate_bundle

        result = validate_bundle(source)
    show_validation(result, stdout, stderr)
    if result.errors:
        raise typer.Exit(code=1)
