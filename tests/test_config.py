from pathlib import Path

import pytest

from bora_workbench.config import DEFAULT_MODEL, ConfigError, load_config


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_absent_file_uses_defaults(tmp_path):
    config = load_config(tmp_path / "missing.toml", environ={})

    assert config.model == DEFAULT_MODEL
    assert config.model_path is None
    assert config.llama_port == 8080
    assert config.engine_path is None
    assert config.open_browser is True


def test_environment_overrides_valid_file(tmp_path):
    path = write_config(
        tmp_path,
        (
            'model = "file/model"\nmodel_path = "~/file.gguf"\nllama_port = 9000\n'
            'engine_path = "~/engine"\nopen_browser = false\n'
        ),
    )

    config = load_config(
        path,
        environ={
            "BORA_MODEL": "env/model",
            "BORA_MODEL_PATH": "~/env.gguf",
            "BORA_LLAMA_PORT": "1234",
            "BORA_ENGINE_PATH": "",
            "BORA_OPEN_BROWSER": "ON",
        },
    )

    assert config.model == "env/model"
    assert config.model_path == Path("~/env.gguf").expanduser()
    assert config.llama_port == 1234
    assert config.engine_path is None
    assert config.open_browser is True


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "On"])
def test_environment_true_values(tmp_path, value):
    config = load_config(tmp_path / "missing.toml", environ={"BORA_OPEN_BROWSER": value})
    assert config.open_browser is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "Off"])
def test_environment_false_values(tmp_path, value):
    config = load_config(tmp_path / "missing.toml", environ={"BORA_OPEN_BROWSER": value})
    assert config.open_browser is False


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("unknown = 1\n", "unknown configuration key"),
        ('model = ""\n', "non-empty string"),
        ("llama_port = true\n", "integer between 1 and 65535"),
        ("llama_port = 0\n", "integer between 1 and 65535"),
        ("llama_port = 65536\n", "integer between 1 and 65535"),
        ('model_path = ""\n', "model_path.*must not be empty"),
        ("model_path = 1\n", "model_path.*must be a string"),
        ('engine_path = ""\n', "must not be empty"),
        ('open_browser = "yes"\n', "must be a boolean"),
        ("[nested]\nvalue = 1\n", "unknown configuration key"),
    ],
)
def test_invalid_file_values_are_rejected(tmp_path, content, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, content), environ={})


def test_empty_environment_model_path_unsets_file_value(tmp_path) -> None:
    """Treat an empty optional path override as explicitly unset."""
    path = write_config(tmp_path, 'model_path = "~/file.gguf"\n')

    config = load_config(path, environ={"BORA_MODEL_PATH": ""})

    assert config.model_path is None


def test_invalid_file_is_rejected_even_when_environment_would_override_it(tmp_path):
    path = write_config(tmp_path, "llama_port = 0\n")
    with pytest.raises(ConfigError, match="llama_port"):
        load_config(path, environ={"BORA_LLAMA_PORT": "8080"})


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"BORA_MODEL": ""}, "model"),
        ({"BORA_LLAMA_PORT": ""}, "integer"),
        ({"BORA_LLAMA_PORT": "12.5"}, "integer"),
        ({"BORA_LLAMA_PORT": "65536"}, "integer"),
        ({"BORA_OPEN_BROWSER": ""}, "must be one of"),
        ({"BORA_OPEN_BROWSER": "maybe"}, "must be one of"),
    ],
)
def test_invalid_environment_values_are_rejected(tmp_path, environment, message):
    with pytest.raises(ConfigError, match=message):
        load_config(tmp_path / "missing.toml", environ=environment)


def test_malformed_toml_has_actionable_error(tmp_path):
    with pytest.raises(ConfigError, match="cannot read configuration file"):
        load_config(write_config(tmp_path, 'model = "unterminated\n'), environ={})
