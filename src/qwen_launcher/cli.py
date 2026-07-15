"""Command-line interface for the initial qwen-launcher scaffold."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer
from rich.console import Console
from rich.table import Table

from qwen_launcher.config import ConfigError, load_config
from qwen_launcher.paths import cache_dir, config_dir, data_dir, state_dir

app = typer.Typer(
    name="qwen-launcher",
    help="Launch and manage the calibrated local Qwen distribution.",
    no_args_is_help=True,
)
_stdout = Console()
_stderr = Console(stderr=True)


def package_version() -> str:
    """Read the installed distribution version."""
    try:
        return version("qwen-launcher")
    except PackageNotFoundError:
        return "0.1.0.dev0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(package_version())
        raise typer.Exit()


@app.callback()
def main(
    version_requested: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed package version and exit.",
    ),
) -> None:
    """qwen-launcher command group."""
    del version_requested


@app.command()
def doctor() -> None:
    """Check the configuration and show paths without modifying the machine."""
    try:
        config = load_config()
    except ConfigError as error:
        _stderr.print(f"[red]Configuration error:[/red] {error}")
        raise typer.Exit(code=2) from error

    table = Table(title="qwen-launcher — initial diagnostics")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Configuration", "valid")
    table.add_row("Model", config.model)
    table.add_row("llama.cpp port", str(config.llama_port))
    table.add_row("Config directory", str(config_dir()))
    table.add_row("Data directory", str(data_dir()))
    table.add_row("Cache directory", str(cache_dir()))
    table.add_row("State directory", str(state_dir()))
    _stdout.print(table)
    _stdout.print("[yellow]Hardware and engine diagnostics are not implemented in Step 1.[/yellow]")


if __name__ == "__main__":
    app()
