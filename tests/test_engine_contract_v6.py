"""Tests for the one-time command-contract preparation for calibration/v6-lite."""

from __future__ import annotations

from dataclasses import replace

import pytest

import qwen_launcher.engine as engine
from qwen_launcher._calibration_record import command_contract_sha256
from qwen_launcher.profiles import PlanError
from tests.test_engine_runtime import plan


@pytest.mark.parametrize(
    ("mode_id", "temp", "top_p", "ui"),
    [("coding", "0.6", "0.95", "--no-webui"), ("studio", "0.7", "0.8", "--webui")],
)
def test_text_mode_argv_remains_byte_identical(tmp_path, mode_id, temp, top_p, ui) -> None:
    """Preserve the pre-D-060 command token order for coding and studio."""
    selected = plan(tmp_path, "cuda", mode_id)
    executable = tmp_path / "llama-server"
    common = (
        str(executable),
        "-m",
        str(selected.model_path),
        "-c",
        "8192",
        "--temp",
        temp,
        "--top-p",
        top_p,
        "--top-k",
        "20",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
        "--metrics",
        "--fit",
        "off",
        "-fa",
        "on",
        "--mmap",
        "-np",
        "1",
        "--jinja",
        "--spec-type",
        "draft-mtp",
        "--spec-draft-n-max",
        "2",
        "--cors-origins",
        "localhost",
        "--log-timestamps",
        ui,
        "--no-mmproj",
        "-ngl",
        "99",
        "-ncmoe",
        "48",
        "--cache-type-k",
        "q8_0",
        "--cache-type-v",
        "q8_0",
    )
    assert engine.build_command(executable, selected, engine.load_engine_lock()) == common


def test_prepared_mode_v2_values_emit_only_when_present(tmp_path) -> None:
    """Keep mode/v1 commands unchanged while preparing verified mode/v2 arrays."""
    selected = plan(tmp_path)
    sampling = replace(
        selected.mode.sampling,
        min_p=0.0,
        presence_penalty=1.5,
        repeat_penalty=1.0,
        reasoning="off",
    )
    selected = replace(selected, mode=replace(selected.mode, sampling=sampling))
    command = engine.build_command(tmp_path / "llama-server", selected, engine.load_engine_lock())

    assert command[command.index("--min-p") + 1] == "0.0"
    assert command[command.index("--presence-penalty") + 1] == "1.5"
    assert command[command.index("--repeat-penalty") + 1] == "1.0"
    assert command[command.index("--reasoning") + 1] == "off"


def test_vision_plan_rejects_speculative_decoding(tmp_path) -> None:
    """Enforce the conservative D-060 vision and MTP incompatibility invariant."""
    with pytest.raises(PlanError, match="vision"):
        replace(plan(tmp_path, mode_id="vstudio"), speculative="mtp2")


def test_contract_change_invalidates_historical_identity() -> None:
    """Keep historical v3 evidence readable without treating its digest as current."""
    historical = "965d8bbc01812bc7df08da6451cb598ed8a552bd512b0e141817343b6566333d"
    assert command_contract_sha256(engine.load_engine_lock()) != historical
