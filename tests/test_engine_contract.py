"""Tests for the lock-only command expansion and its pinned mode/v2 argv contract."""

from __future__ import annotations

from dataclasses import replace

import pytest

import bora_workbench.engine as engine
from bora_workbench._calibration_record import command_contract_sha256
from bora_workbench.profiles import PlanError
from tests.test_engine import plan


def _text_prefix(executable: object, model_path: object, temp: str, top_p: str) -> tuple[str, ...]:
    """Return the shared mode/v2 argv head up to the reasoning flag."""
    return (
        str(executable),
        "-m",
        str(model_path),
        "-c",
        "8192",
        "--temp",
        temp,
        "--top-p",
        top_p,
        "--top-k",
        "20",
    )


def _extended_and_server(presence: str, reasoning: str) -> tuple[str, ...]:
    """Return the extended sampling, reasoning, network, metrics, and fixed argv middle."""
    return (
        "--min-p",
        "0.0",
        "--presence-penalty",
        presence,
        "--repeat-penalty",
        "1.0",
        "--reasoning",
        reasoning,
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
    )


def _backend_tail() -> tuple[str, ...]:
    """Return the fixed CUDA offload and KV-cache argv tail."""
    return ("-ngl", "99", "-ncmoe", "48", "--cache-type-k", "q8_0", "--cache-type-v", "q8_0")


@pytest.mark.parametrize(
    ("mode_id", "temp", "top_p", "presence", "reasoning", "ui"),
    [
        ("coding", "0.6", "0.95", "0.0", "on", "--no-webui"),
        ("studio", "0.7", "0.8", "1.5", "off", "--webui"),
    ],
)
def test_text_mode_argv_matches_mode_v2_contract(
    tmp_path, mode_id, temp, top_p, presence, reasoning, ui
) -> None:
    """Pin the complete coding and studio argv after the mode/v2 migration (spec section 5.3)."""
    selected = plan(tmp_path, "cuda", mode_id)
    executable = tmp_path / "llama-server"
    expected = (
        *_text_prefix(executable, selected.model_path, temp, top_p),
        *_extended_and_server(presence, reasoning),
        "--spec-type",
        "draft-mtp",
        "--spec-draft-n-max",
        "2",
        "--cors-origins",
        "localhost",
        "--log-timestamps",
        ui,
        "--no-mmproj",
        *_backend_tail(),
    )
    assert engine.build_command(executable, selected, engine.load_engine_lock()) == expected


def test_vision_mode_argv_matches_mode_v2_contract(tmp_path) -> None:
    """Pin the vstudio argv: reasoning off, vision projector, and no speculative flags (D-060)."""
    selected = plan(tmp_path, "cuda", "vstudio")
    executable = tmp_path / "llama-server"
    expected = (
        *_text_prefix(executable, selected.model_path, "0.7", "0.8"),
        *_extended_and_server("1.5", "off"),
        "--cors-origins",
        "localhost",
        "--log-timestamps",
        "--webui",
        "--mmproj",
        str(selected.mmproj_path),
        *_backend_tail(),
    )
    assert engine.build_command(executable, selected, engine.load_engine_lock()) == expected


def test_mode_v2_values_emit_every_extended_flag(tmp_path) -> None:
    """Emit every extended sampling and reasoning flag from the mode/v2 sampling contract."""
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


@pytest.mark.parametrize("backend", ["cpu", "cuda"])
@pytest.mark.parametrize(
    ("mode_id", "has_ui", "has_vision", "sampling"),
    [
        ("coding", False, False, ("0.6", "0.95")),
        ("studio", True, False, ("0.7", "0.8")),
        ("vstudio", True, True, ("0.7", "0.8")),
    ],
)
def test_builder_emits_verified_three_mode_matrix(
    tmp_path, backend, mode_id, has_ui, has_vision, sampling
) -> None:
    """Emit exact UI, vision, sampling, and backend switches for all three modes."""
    lock = engine.load_engine_lock()
    selected_plan = plan(tmp_path, backend, mode_id)
    command = engine.build_command(tmp_path / "llama-server", selected_plan, lock)
    flags = {token for token in command[1:] if token.startswith("-")}

    assert flags <= set(lock["verified_flags"])
    assert ("--webui" in command) is has_ui
    assert ("--no-webui" in command) is not has_ui
    assert ("--mmproj" in command) is has_vision
    assert ("--no-mmproj" in command) is not has_vision
    assert sampling[0] == command[command.index("--temp") + 1]
    assert sampling[1] == command[command.index("--top-p") + 1]
    assert command[command.index("--top-k") + 1] == "20"
    assert str(selected_plan.model_path) in command
    assert (str(selected_plan.mmproj_path) in command) is has_vision
    assert ("-ncmoe" in command) is (backend == "cuda")
    assert ("-ngl" in command) is (backend == "cuda")
    assert ("--cache-type-k" in command) is (backend == "cuda")
    assert ("--cache-type-v" in command) is (backend == "cuda")
    if backend == "cuda":
        assert command[command.index("--cache-type-k") + 1] == "q8_0"
        assert command[command.index("--cache-type-v") + 1] == "q8_0"
    assert "--no-mmap" not in command
    assert "--mmap" in command
    assert ("--spec-type" in command) is not has_vision
    assert ("--spec-draft-n-max" in command) is not has_vision


def test_builder_defensively_rejects_unverified_lock_option(tmp_path) -> None:
    """Fail even if malformed lock data reaches the builder without prior validation."""
    lock = engine.load_engine_lock()
    contract = lock["command_contract"]
    assert isinstance(contract, dict)
    fixed = contract["fixed_args"]
    assert isinstance(fixed, list)
    fixed.append("--invented")

    with pytest.raises(engine.EngineError, match=r"outside engine\.lock"):
        engine.build_command(tmp_path / "llama-server", plan(tmp_path), lock)


def test_vision_plan_rejects_speculative_decoding(tmp_path) -> None:
    """Enforce the conservative D-060 vision and MTP incompatibility invariant."""
    with pytest.raises(PlanError, match="vision"):
        replace(plan(tmp_path, mode_id="vstudio"), speculative="mtp2")


def test_contract_change_invalidates_historical_identity() -> None:
    """Keep historical v3 evidence readable without treating its digest as current."""
    historical = "965d8bbc01812bc7df08da6451cb598ed8a552bd512b0e141817343b6566333d"
    assert command_contract_sha256(engine.load_engine_lock()) != historical
