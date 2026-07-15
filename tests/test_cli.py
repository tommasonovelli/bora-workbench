"""CLI tests for presentation, read-only behavior, and exit-code mapping."""

from typer.testing import CliRunner

import qwen_launcher.cli as cli_module
import qwen_launcher.config as config_module
from qwen_launcher.cli import app
from qwen_launcher.hardware import HardwareError, HardwareInfo
from qwen_launcher.validation import ValidationIssue, ValidationResult

runner = CliRunner()


def patch_directories(tmp_path, monkeypatch):
    """Redirect all public directories to one isolated test root."""
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


def fake_hardware() -> HardwareInfo:
    """Return deterministic CPU hardware for doctor presentation tests."""
    return HardwareInfo(
        "linux",
        "test-version",
        "Test CPU",
        12,
        32,
        24,
        "cpu",
        0,
        None,
        None,
        None,
        None,
        ("nvidia-smi was not found; using the CPU backend.",),
    )


def test_version() -> None:
    """Expose the package version through the eager global option."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0.dev0"


def test_validate_passes_with_expected_engine_warning() -> None:
    """Return zero for valid packaged content containing only warnings."""
    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0
    assert "engine.lock:$.assets_complete" in result.stdout
    assert "Validation passed" in result.stdout


def test_validate_maps_errors_to_exit_1(monkeypatch) -> None:
    """Print validation errors to stderr and return the contractual failure code."""
    invalid = ValidationResult((ValidationIssue("error", "mode.json", "$.id", "bad id"),))
    monkeypatch.setattr(cli_module, "validate_resources", lambda: invalid)

    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 1
    assert "mode.json:$.id: bad id" in result.stderr


def test_doctor_is_read_only_and_reports_hardware(tmp_path, monkeypatch) -> None:
    """Describe Step 2B hardware and empty profiles without creating directories."""
    patch_directories(tmp_path, monkeypatch)
    monkeypatch.setattr(cli_module, "detect_hardware", fake_hardware)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Step 2B diagnostics" in result.stdout
    assert "Test CPU" in result.stdout
    assert "32.00 GiB" in result.stdout
    assert "No calibrated profile" in result.stdout
    assert not any(tmp_path.iterdir())


def test_doctor_maps_invalid_configuration_to_exit_2(tmp_path, monkeypatch) -> None:
    """Keep malformed user configuration in the CLI-input error category."""
    directories = patch_directories(tmp_path, monkeypatch)
    directories["config_dir"].mkdir(parents=True)
    (directories["config_dir"] / "config.toml").write_text("llama_port = 0\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 2
    assert "Configuration error" in result.stderr
    assert "llama_port" in result.stderr


def test_doctor_maps_hardware_failure_to_exit_1(tmp_path, monkeypatch) -> None:
    """Map missing required hardware facts to an actionable operational error."""
    patch_directories(tmp_path, monkeypatch)
    failure = HardwareError("cannot determine logical CPU cores")
    monkeypatch.setattr(cli_module, "detect_hardware", lambda: (_ for _ in ()).throw(failure))

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Hardware error" in result.stderr
    assert "logical CPU cores" in result.stderr
