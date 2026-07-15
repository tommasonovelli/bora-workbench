from typer.testing import CliRunner

import qwen_launcher.cli as cli_module
import qwen_launcher.config as config_module
from qwen_launcher.cli import app

runner = CliRunner()


def patch_directories(tmp_path, monkeypatch):
    directories = {
        "config_dir": tmp_path / "config" / "qwen-launcher",
        "data_dir": tmp_path / "data" / "qwen-launcher",
        "cache_dir": tmp_path / "cache" / "qwen-launcher",
        "state_dir": tmp_path / "state" / "qwen-launcher",
    }
    monkeypatch.setattr(config_module, "config_dir", lambda: directories["config_dir"])
    for name, path in directories.items():
        monkeypatch.setattr(cli_module, name, lambda path=path: path)
    return directories


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0.dev0"


def test_doctor_is_read_only_and_reports_step_1_scope(tmp_path, monkeypatch):
    patch_directories(tmp_path, monkeypatch)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "initial diagnostics" in result.stdout
    assert "not implemented in Step 1" in result.stdout
    assert not any(tmp_path.iterdir())


def test_doctor_maps_invalid_configuration_to_exit_2(tmp_path, monkeypatch):
    directories = patch_directories(tmp_path, monkeypatch)
    directories["config_dir"].mkdir(parents=True)
    (directories["config_dir"] / "config.toml").write_text("llama_port = 0\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 2
    assert "Configuration error" in result.stderr
    assert "llama_port" in result.stderr
