"""CLI tests for presentation, read-only behavior, and exit-code mapping."""

from types import SimpleNamespace

from typer.testing import CliRunner

import qwen_launcher._calibration_record as record_module
import qwen_launcher._cli_control as control_cli
import qwen_launcher._cli_doctor as doctor_cli
import qwen_launcher._cli_services as service_cli
import qwen_launcher._cli_validation as validation_cli
import qwen_launcher.config as config_module
import qwen_launcher.engine as engine_module
import qwen_launcher.paths as paths_module
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
        monkeypatch.setattr(paths_module, name, lambda path=path: path)
    # The record module binds data_dir at import time, so its lookup is patched directly.
    monkeypatch.setattr(record_module, "data_dir", lambda: directories["data_dir"])
    absent_engine = SimpleNamespace(
        is_active=False,
        release=None,
        backend=None,
        executable=None,
        is_compatible=False,
        differences=("not installed",),
    )
    monkeypatch.setattr(engine_module, "engine_status", lambda: absent_engine)
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
    assert result.stdout.strip() == "0.1.5"


def test_validate_passes_with_complete_engine_assets() -> None:
    """Return zero for packaged content with the complete engine lock."""
    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0
    assert "Validation passed with 0 warning(s)" in result.stdout


def test_validate_maps_errors_to_exit_1(monkeypatch) -> None:
    """Print validation errors to stderr and return the contractual failure code."""
    invalid = ValidationResult((ValidationIssue("error", "mode.json", "$.id", "bad id"),))
    monkeypatch.setattr(validation_cli, "validate_resources", lambda: invalid)

    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 1
    assert "mode.json:$.id: bad id" in result.stderr


def test_doctor_is_read_only_and_reports_hardware(tmp_path, monkeypatch) -> None:
    """Describe hardware and empty profiles without creating directories."""
    patch_directories(tmp_path, monkeypatch)
    monkeypatch.setattr(doctor_cli, "detect_hardware", fake_hardware)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "qwen-launcher diagnostics" in result.stdout
    assert "Test CPU" in result.stdout
    assert "32.00 GiB" in result.stdout
    assert "no active record" in result.stdout
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
    monkeypatch.setattr(doctor_cli, "detect_hardware", lambda: (_ for _ in ()).throw(failure))

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Hardware error" in result.stderr
    assert "logical CPU cores" in result.stderr


def test_coding_maps_invalid_configuration_to_exit_2(monkeypatch) -> None:
    """Keep coding configuration failures in the contractual CLI-input category."""
    error = config_module.ConfigError("invalid test configuration")
    monkeypatch.setattr(service_cli, "load_config", lambda: (_ for _ in ()).throw(error))

    result = runner.invoke(app, ["coding"])

    assert result.exit_code == 2
    assert "Configuration error" in result.stderr


def test_coding_ctrl_c_maps_to_exit_130(monkeypatch) -> None:
    """Map foreground interruption after lifecycle cleanup to exit code 130."""
    mode = SimpleNamespace(id="coding")
    plan = SimpleNamespace(mode=mode, backend="cpu", profile_id=None, warnings=())
    state = SimpleNamespace(log_path="server.log")
    running = SimpleNamespace(state=state, warnings=())
    session = SimpleNamespace(
        running=running,
        plan=plan,
        api_url="http://127.0.0.1:8080/v1",
        ui_url=None,
        is_browser_enabled=False,
    )
    monkeypatch.setattr(service_cli, "_prepare_mode", lambda mode_id, force, stderr: session)
    interruption = KeyboardInterrupt()
    monkeypatch.setattr(
        service_cli, "wait_foreground", lambda running: (_ for _ in ()).throw(interruption)
    )

    result = runner.invoke(app, ["coding", "--force"])

    assert result.exit_code == 130
    assert "Stopped after Ctrl-C" in result.stdout


def test_status_and_stop_commands_are_idempotent(monkeypatch) -> None:
    """Expose successful empty-state status and stop behavior through the CLI."""
    empty = SimpleNamespace(services=(), warnings=(), stopped=())
    monkeypatch.setattr(control_cli, "status_services", lambda: empty)
    monkeypatch.setattr(control_cli, "stop_services", lambda: empty)

    status_result = runner.invoke(app, ["status"])
    stop_result = runner.invoke(app, ["stop"])

    assert status_result.exit_code == 0
    assert stop_result.exit_code == 0
    assert "No managed services" in status_result.stdout
    assert "No managed services" in stop_result.stdout
