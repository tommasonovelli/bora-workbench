"""Test shared terminal helpers preserve dynamic text literally."""

from io import StringIO

from rich.console import Console

from bora_workbench._cli_theme import (
    STYLE_ACCENT,
    STYLE_BODY,
    STYLE_HEADING,
    STYLE_SUCCESS,
    print_error,
    print_heading,
    print_note,
    print_success,
    print_warning,
)


def test_shared_cli_identity_uses_blue_labels_and_white_explanations() -> None:
    """Keep ordinary command output aligned with the workbench without recolouring errors."""
    assert all("blue" in style for style in (STYLE_ACCENT, STYLE_HEADING, STYLE_SUCCESS))
    assert STYLE_BODY == "white"


def test_status_helpers_do_not_interpret_dynamic_rich_markup() -> None:
    """Keep brackets and mismatched closing tags literal instead of raising MarkupError."""
    stream = StringIO()
    console = Console(file=stream, color_system=None)

    print_heading(console, "Section [draft]")
    print_success(console, "Ready [local]", "path [/red]")
    print_warning(console, "warning detail [yellow]")
    print_error(console, "Launch error", "model [/red]")
    print_note(console, "Path", "records/[draft]")

    rendered = stream.getvalue()
    for literal in (
        "Section [draft]",
        "Ready [local] path [/red]",
        "warning: warning detail [yellow]",
        "Launch error: model [/red]",
        "Path: records/[draft]",
    ):
        assert literal in rendered
