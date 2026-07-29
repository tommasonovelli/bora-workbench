"""Tests for the pi integration: what it writes, what it preserves, and what it refuses."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console
from typer.testing import CliRunner

import bora_workbench._cli_pi as pi_cli
import bora_workbench.cli as cli_module
from bora_workbench import pi_link
from bora_workbench._calibration_reuse import RecordEvaluation
from bora_workbench._cli_pi import _context_window
from bora_workbench.cli import app
from bora_workbench.config import Config, load_config
from bora_workbench.engine import EngineError, load_engine_lock
from bora_workbench.pi_link import ContextWindow, ContextWindowQuery, resolve_context_window
from bora_workbench.process import ServiceReport, ServiceState
from bora_workbench.profiles import FALLBACK_CTX

runner = CliRunner()


def _fixed_window(monkeypatch, tokens: int = 8192) -> None:
    """Pin the window so a connection test exercises the write, not the resolution."""
    monkeypatch.setattr(
        pi_cli, "_context_window", lambda config, lock: ContextWindow(tokens, "test source")
    )


def _service(port: int, ctx: int, mode: str = "coding") -> ServiceState:
    """Build one managed service record with the two fields the pi resolution reads."""
    return ServiceState(
        label="llama-server",
        pid=4321,
        create_time=1.0,
        executable="llama-server",
        port=port,
        started_at="2026-07-28T10:00:00Z",
        log_path="server.log",
        mode=mode,
        model="qwen",
        engine_release="b10011",
        profile_id="local-calibration-record",
        ctx=ctx,
        n_cpu_moe=33,
        backend="cuda",
        gpu_index=0,
    )


def _services(monkeypatch, *services: ServiceState) -> None:
    """Replace the managed-service sweep, which would otherwise read this machine's state."""
    monkeypatch.setattr(pi_cli, "across_service_roots", lambda operation: ServiceReport(services))


def _evaluation(monkeypatch, evaluation: RecordEvaluation) -> None:
    """Replace record evaluation and hardware detection so the resolution stays offline."""
    monkeypatch.setattr(pi_cli, "detect_hardware", lambda: None)
    monkeypatch.setattr(pi_cli, "evaluate_record", lambda query: evaluation)


def _npm_calls(monkeypatch) -> list[tuple[str, ...]]:
    """Record every npm invocation instead of running one, and report success."""
    calls: list[tuple[str, ...]] = []

    def fake_run(command, check, shell):
        """Capture the command and assert the two arguments security requires."""
        assert (check, shell) == (False, False)
        calls.append(tuple(command))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(pi_cli.subprocess, "run", fake_run)
    return calls


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


def test_dropping_the_provider_leaves_every_other_one_in_place() -> None:
    """Removal is the exact inverse of the write: one key, and nothing else (D-082)."""
    document = {"providers": {"ollama": {"a": 1}, "bora": {"b": 2}}, "somethingElse": 1}

    without = pi_link.document_without_provider(document)

    assert without == {"providers": {"ollama": {"a": 1}}, "somethingElse": 1}
    assert document["providers"]["bora"] == {"b": 2}
    assert pi_link.document_without_provider({}) == {}


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


def test_shared_context_selection_covers_all_three_d082_sources() -> None:
    """Keep live, record, and baseline selection in one pure shared service."""
    valid = RecordEvaluation("valid", 49152, 33, ())
    missing = RecordEvaluation("missing", None, None, ("no active coding record",))
    cases = (
        (ContextWindowQuery(8080, (_service(8080, 65536),), None), 65536, "running"),
        (ContextWindowQuery(8080, (), valid), 49152, "local coding"),
        (ContextWindowQuery(8080, (), missing), FALLBACK_CTX, "baseline"),
    )

    for query, tokens, source in cases:
        result = resolve_context_window(query)
        assert result.tokens == tokens
        assert source in result.source
    assert resolve_context_window(cases[-1][0]).diagnostics == ("no active coding record",)


def test_cli_context_resolution_returns_the_shared_result(monkeypatch) -> None:
    """Delegate presentation collection to pi_link without copying its source order."""
    query = ContextWindowQuery(8080, (), RecordEvaluation("missing", None, None, ()))
    expected = ContextWindow(FALLBACK_CTX, "shared test result")
    monkeypatch.setattr(pi_cli, "_context_query", lambda config, lock: query)
    monkeypatch.setattr(pi_cli, "resolve_context_window", lambda selected: expected)

    result = _context_window(Config(), load_engine_lock())

    assert result is expected


def test_a_running_service_reports_the_window_it_is_actually_serving(monkeypatch) -> None:
    """A live service outranks the record, whose headroom that same service is holding (D-082)."""
    config = load_config()
    _services(monkeypatch, _service(config.llama_port, 65536))
    _evaluation(monkeypatch, RecordEvaluation("insufficient-headroom", 65536, 33, ("no VRAM",)))

    window = _context_window(config, load_engine_lock())

    assert window.tokens == 65536
    assert "running coding service" in window.source
    assert window.diagnostics == ()


def test_a_service_on_another_port_does_not_supply_the_window(monkeypatch) -> None:
    """The provider names one port, so only a service serving that port answers for it."""
    config = load_config()
    _services(monkeypatch, _service(config.llama_port + 1, 65536))
    _evaluation(monkeypatch, RecordEvaluation("valid", 49152, 33, ()))

    assert _context_window(config, load_engine_lock()).tokens == 49152


def test_an_active_record_supplies_its_calibrated_window(monkeypatch) -> None:
    """What `bora calibrate` measured is what pi is told, without a service running."""
    config = load_config()
    _services(monkeypatch)
    _evaluation(monkeypatch, RecordEvaluation("valid", 131072, 0, ()))

    window = _context_window(config, load_engine_lock())

    assert window.tokens == 131072
    assert window.source == "local coding calibration record"


def test_the_baseline_window_carries_the_reason_it_was_used(monkeypatch) -> None:
    """A window smaller than the calibrated one has to say why, not just be small."""
    config = load_config()
    _services(monkeypatch)
    diagnostic = "no local calibration record; run `bora calibrate` to optimize locally"
    _evaluation(monkeypatch, RecordEvaluation("missing", None, None, (diagnostic,)))

    window = _context_window(config, load_engine_lock())

    assert window.tokens == FALLBACK_CTX
    assert window.diagnostics == (diagnostic,)


@pytest.mark.parametrize(
    "arguments",
    (
        ["pi", "--print", "--install"],
        ["pi", "--install", "remove"],
        ["pi", "--print", "uninstall"],
    ),
)
def test_contradictory_pi_options_exit_before_any_action(arguments, monkeypatch) -> None:
    """Reject every option combination that the selected pi action would discard."""
    calls: list[str] = []
    monkeypatch.setattr(cli_module, "run_pi", lambda *args: calls.append("connect"))
    monkeypatch.setattr(cli_module, "run_pi_removal", lambda *args: calls.append("remove"))
    monkeypatch.setattr(cli_module, "run_pi_uninstall", lambda *args: calls.append("uninstall"))

    result = runner.invoke(app, arguments)

    assert result.exit_code == 2
    assert "cannot be used" in result.stderr or "mutually exclusive" in result.stderr
    assert calls == []


def test_print_writes_nothing_and_needs_no_installed_pi(tmp_path, monkeypatch) -> None:
    """`--print` is the escape hatch when pi is absent or its format has moved on."""
    _fixed_window(monkeypatch)
    monkeypatch.setattr(
        pi_link, "inspect_pi", lambda: pi_link.PiInstallation(None, tmp_path / "models.json")
    )

    result = runner.invoke(app, ["pi", "--print"])

    assert result.exit_code == 0
    assert '"baseUrl"' in result.stdout
    assert not (tmp_path / "models.json").exists()


def test_absent_pi_is_reported_with_both_platform_instructions(tmp_path, monkeypatch) -> None:
    """Without `--install` an absent pi is an actionable message, never an implicit install."""
    _fixed_window(monkeypatch)
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
    _fixed_window(monkeypatch)
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", path))

    result = runner.invoke(app, ["pi"], input="n\n")

    assert result.exit_code == 0
    assert path.read_text(encoding="utf-8") == '{"providers": {"ollama": {}}}'
    assert "not changed" in result.stdout


def test_confirmed_connection_writes_the_provider(tmp_path, monkeypatch) -> None:
    """A confirmed run leaves pi able to select the local model by provider and id."""
    path = tmp_path / "models.json"
    _fixed_window(monkeypatch, 65536)
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", path))

    result = runner.invoke(app, ["pi"], input="y\n")

    assert result.exit_code == 0
    stored = json.loads(path.read_text(encoding="utf-8"))["providers"]["bora"]
    assert stored["baseUrl"].startswith("http://127.0.0.1:")
    assert stored["models"][0]["id"] == "Qwen 3.6"
    assert stored["models"][0]["contextWindow"] == 65536
    assert "65536 tokens, from the test source" in result.stdout
    assert "pi --provider bora" in result.stdout


def test_removing_without_an_entry_changes_nothing(tmp_path, monkeypatch) -> None:
    """Removal is idempotent: an absent entry is a report, not an error."""
    path = tmp_path / "models.json"
    path.write_text('{"providers": {"ollama": {}}}', encoding="utf-8")
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(None, path))

    result = runner.invoke(app, ["pi", "remove"])

    assert result.exit_code == 0
    assert "nothing to remove" in result.stdout
    assert path.read_text(encoding="utf-8") == '{"providers": {"ollama": {}}}'


def test_declining_the_removal_leaves_the_entry_in_place(tmp_path, monkeypatch) -> None:
    """The entry is shown first and deleted only after an explicit yes."""
    path = tmp_path / "models.json"
    path.write_text('{"providers": {"bora": {"api": "openai-completions"}}}', encoding="utf-8")
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(None, path))

    result = runner.invoke(app, ["pi", "remove"], input="n\n")

    assert result.exit_code == 0
    assert json.loads(path.read_text(encoding="utf-8"))["providers"]["bora"]
    assert "not changed" in result.stdout


def test_confirmed_removal_deletes_only_this_projects_provider(tmp_path, monkeypatch) -> None:
    """What `bora pi` added is taken back; what the user configured stays (D-082)."""
    path = tmp_path / "models.json"
    original = '{"providers": {"ollama": {"a": 1}, "bora": {"b": 2}}}'
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(None, path))

    result = runner.invoke(app, ["pi", "remove"], input="y\n")

    assert result.exit_code == 0
    assert json.loads(path.read_text(encoding="utf-8"))["providers"] == {"ollama": {"a": 1}}
    assert path.with_suffix(".json.bak").read_text(encoding="utf-8") == original


def test_uninstalling_an_absent_pi_still_offers_the_entry(tmp_path, monkeypatch) -> None:
    """An entry written earlier outlives the package, so removing it stays possible."""
    path = tmp_path / "models.json"
    path.write_text('{"providers": {"bora": {"b": 2}}}', encoding="utf-8")
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(None, path))
    calls = _npm_calls(monkeypatch)

    result = runner.invoke(app, ["pi", "uninstall"], input="y\n")

    assert result.exit_code == 0
    assert calls == []
    assert "no npm package was removed" in result.stdout
    assert json.loads(path.read_text(encoding="utf-8"))["providers"] == {}


def test_uninstall_runs_the_vendor_removal_and_asks_about_the_entry(tmp_path, monkeypatch) -> None:
    """The package and the entry are two consents, and neither implies the other (D-079/D-082)."""
    path = tmp_path / "models.json"
    path.write_text('{"providers": {"bora": {"b": 2}}}', encoding="utf-8")
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", path))
    calls = _npm_calls(monkeypatch)

    result = runner.invoke(app, ["pi", "uninstall"], input="y\nn\n")

    assert result.exit_code == 0
    assert calls == [("npm", "uninstall", "-g", "@earendil-works/pi-coding-agent")]
    assert "still on PATH" in result.stdout
    assert json.loads(path.read_text(encoding="utf-8"))["providers"]["bora"] == {"b": 2}


def test_declining_the_vendor_removal_runs_no_command(tmp_path, monkeypatch) -> None:
    """Refusing the npm step is a skip, not a failure, and the entry is still offered."""
    path = tmp_path / "models.json"
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", path))
    calls = _npm_calls(monkeypatch)

    result = runner.invoke(app, ["pi", "uninstall"], input="n\n")

    assert result.exit_code == 0
    assert calls == []
    assert "pi is still installed" in result.stdout


def test_a_failing_npm_removal_is_reported_operationally(tmp_path, monkeypatch) -> None:
    """npm's own failure is an operational error, without a traceback (section 5.11)."""
    path = tmp_path / "models.json"
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", path))
    monkeypatch.setattr(
        pi_cli.subprocess, "run", lambda command, check, shell: SimpleNamespace(returncode=1)
    )

    result = runner.invoke(app, ["pi", "uninstall"], input="y\n")

    assert result.exit_code == 1
    assert "npm exited with code 1" in result.stderr


def test_the_calibration_hint_offers_to_install_an_absent_pi(monkeypatch) -> None:
    """A machine without pi is told how to get it, because that is what the window is for."""
    models_file = Path("models.json")
    monkeypatch.setattr(pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(None, models_file))
    console = Console(record=True, width=200)

    pi_cli.print_pi_hint(65536, console)

    assert "--install" in console.export_text()


def test_the_calibration_hint_points_an_installed_pi_at_bora_pi(tmp_path, monkeypatch) -> None:
    """With pi present the hint is the one command that rewrites the stored window."""
    monkeypatch.setattr(
        pi_cli, "inspect_pi", lambda: pi_link.PiInstallation(tmp_path / "pi", tmp_path / "m.json")
    )
    console = Console(record=True, width=200)

    pi_cli.print_pi_hint(65536, console)

    text = console.export_text()
    assert "bora pi" in text and "65536" in text
