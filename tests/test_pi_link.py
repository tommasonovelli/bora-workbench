"""Tests for the pi integration: what it writes, what it preserves, and what it refuses."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import bora_workbench._cli_pi as pi_cli
from bora_workbench import pi_link
from bora_workbench.cli import app
from bora_workbench.engine import EngineError, load_engine_lock

runner = CliRunner()


def test_provider_entry_points_at_the_loopback_service_with_the_model_alias() -> None:
    """The entry names the local endpoint and the exact id `/v1/models` reports (D-080)."""
    entry = pi_link.provider_entry(load_engine_lock(), 8080, 32768)

    assert entry["baseUrl"] == "http://127.0.0.1:8080/v1"
    assert entry["api"] == "openai-completions"
    assert entry["models"] == [
        {
            "id": "Qwen 3.6",
            "name": "Qwen 3.6",
            "input": ["text"],
            "contextWindow": 32768,
            "maxTokens": 32768,
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        }
    ]


def test_merging_replaces_only_the_bora_provider() -> None:
    """Somebody else's providers, and every unrelated key, survive the write untouched."""
    document = {
        "providers": {"ollama": {"baseUrl": "http://localhost:11434/v1"}, "bora": {"old": True}},
        "somethingElse": 1,
    }

    merged = pi_link.merged_document(document, {"new": True})

    assert merged["providers"] == {
        "ollama": {"baseUrl": "http://localhost:11434/v1"},
        "bora": {"new": True},
    }
    assert merged["somethingElse"] == 1
    assert document["providers"]["bora"] == {"old": True}


def test_reading_an_absent_file_is_an_empty_document(tmp_path) -> None:
    """A machine where pi has never written a model store still gets a provider."""
    assert pi_link.read_document(tmp_path / "models.json") == {}


def test_unparsable_configuration_is_refused_rather_than_overwritten(tmp_path) -> None:
    """Replacing a file this tool cannot read would destroy the user's own configuration."""
    path = tmp_path / "models.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(EngineError, match="not valid JSON"):
        pi_link.read_document(path)


def test_writing_keeps_the_previous_content_beside_the_new_one(tmp_path) -> None:
    """The write is atomic and leaves a backup, because it edits somebody else's file."""
    path = tmp_path / "models.json"
    path.write_text('{"providers": {}}', encoding="utf-8")

    pi_link.write_document(path, {"providers": {"bora": {"api": "openai-completions"}}})

    assert json.loads(path.read_text(encoding="utf-8"))["providers"]["bora"]["api"]
    assert path.with_suffix(".json.bak").read_text(encoding="utf-8") == '{"providers": {}}'
    assert [item.name for item in tmp_path.iterdir() if item.suffix == ".tmp"] == []


def test_print_writes_nothing_and_needs_no_installed_pi(tmp_path, monkeypatch) -> None:
    """`--print` is the escape hatch when pi is absent or its format has moved on."""
    monkeypatch.setattr(pi_cli, "_context_window", lambda config, lock: 8192)
    monkeypatch.setattr(
        pi_link, "inspect_pi", lambda: pi_link.PiInstallation(None, tmp_path / "models.json")
    )

    result = runner.invoke(app, ["pi", "--print"])

    assert result.exit_code == 0
    assert '"baseUrl"' in result.stdout
    assert not (tmp_path / "models.json").exists()


def test_absent_pi_is_reported_with_both_platform_instructions(tmp_path, monkeypatch) -> None:
    """Without `--install` an absent pi is an actionable message, never an implicit install."""
    monkeypatch.setattr(pi_cli, "_context_window", lambda config, lock: 8192)
    monkeypatch.setattr(
        pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(None, tmp_path / "models.json")
    )

    result = runner.invoke(app, ["pi"])

    assert result.exit_code == 1
    assert "npm install -g --ignore-scripts" in result.stdout
    assert "install.ps1" in result.stdout
    assert result.stdout.isascii()


def test_declining_the_confirmation_leaves_the_configuration_alone(tmp_path, monkeypatch) -> None:
    """The provider is shown first and written only after an explicit yes."""
    path = tmp_path / "models.json"
    path.write_text('{"providers": {"ollama": {}}}', encoding="utf-8")
    monkeypatch.setattr(pi_cli, "_context_window", lambda config, lock: 8192)
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", path))

    result = runner.invoke(app, ["pi"], input="n\n")

    assert result.exit_code == 0
    assert path.read_text(encoding="utf-8") == '{"providers": {"ollama": {}}}'
    assert "not changed" in result.stdout


def test_confirmed_connection_writes_the_provider(tmp_path, monkeypatch) -> None:
    """A confirmed run leaves pi able to select the local model by provider and id."""
    path = tmp_path / "models.json"
    monkeypatch.setattr(pi_cli, "_context_window", lambda config, lock: 8192)
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", path))

    result = runner.invoke(app, ["pi"], input="y\n")

    assert result.exit_code == 0
    stored = json.loads(path.read_text(encoding="utf-8"))["providers"]["bora"]
    assert stored["baseUrl"].startswith("http://127.0.0.1:")
    assert stored["models"][0]["id"] == "Qwen 3.6"
    assert "pi --provider bora" in result.stdout
