from typer.testing import CliRunner

from qwen_launcher.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0.dev0"


def test_doctor_is_read_only_and_reports_pending_spike(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "initial diagnostics" in result.stdout
    assert "pending completion of Spike 0" in result.stdout
    assert not any(tmp_path.iterdir())


def test_doctor_maps_invalid_configuration_to_exit_2(tmp_path, monkeypatch):
    config_dir = tmp_path / "config" / "qwen-launcher"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("llama_port = 0\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 2
    assert "Configuration error" in result.stderr
    assert "llama_port" in result.stderr
