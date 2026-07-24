"""Expand only command templates and placeholders declared by the verified engine lock."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from qwen_launcher.engine import EngineError, JsonObject
from qwen_launcher.profiles import LaunchPlan


def _expand(tokens: object, values: dict[str, str]) -> list[str]:
    """Expand complete placeholder tokens without interpreting engine option semantics."""
    expanded: list[str] = []
    for token in cast(list[str], tokens):
        if token.startswith("{") and token.endswith("}"):
            name = token[1:-1]
            if name not in values:
                raise EngineError(f"engine command requires unavailable placeholder {name!r}")
            expanded.append(values[name])
        else:
            expanded.append(token)
    return expanded


def _values(plan: LaunchPlan) -> dict[str, str]:
    """Serialize plan values for exact lock placeholder substitution."""
    values = {
        "model_path": str(plan.model_path),
        "ctx": str(plan.ctx),
        "temp": str(plan.mode.sampling.temp),
        "top_p": str(plan.mode.sampling.top_p),
        "top_k": str(plan.mode.sampling.top_k),
        "port": str(plan.port),
    }
    optional = ("min_p", "presence_penalty", "repeat_penalty")
    for name in optional:
        value = getattr(plan.mode.sampling, name)
        if value is not None:
            values[name] = str(value)
    if plan.mmproj_path is not None:
        values["mmproj"] = str(plan.mmproj_path)
    if plan.n_cpu_moe is not None:
        values["n_cpu_moe"] = str(plan.n_cpu_moe)
    return values


def _optional_mode_arrays(plan: LaunchPlan, command: JsonObject) -> list[object]:
    """Emit prepared mode/v2 arrays only when validated mode values are present."""
    extended = cast(JsonObject, command["extended_sampling_args"])
    arrays = [
        extended[name]
        for name in ("min_p", "presence_penalty", "repeat_penalty")
        if getattr(plan.mode.sampling, name) is not None
    ]
    reasoning = plan.mode.sampling.reasoning
    if reasoning is not None:
        arrays.append(cast(JsonObject, command["reasoning_args"])[reasoning])
    return arrays


def _contract_arrays(plan: LaunchPlan, command: JsonObject) -> tuple[object, ...]:
    """Select explicit behavior, speculative, vision, and backend arrays."""
    sampling = cast(JsonObject, command["sampling_args"])
    ui = cast(JsonObject, command["ui_args"])
    vision = cast(JsonObject, command["vision_args"])
    backends = cast(JsonObject, command["backend_args"])
    arrays = [command["model_args"], command["context_args"]]
    arrays.extend(sampling[name] for name in ("temp", "top_p", "top_k"))
    arrays.extend(_optional_mode_arrays(plan, command))
    arrays.extend((command["network_args"], command["metrics_args"], command["fixed_args"]))
    arrays.append(cast(JsonObject, command["speculative_args"])[plan.speculative])
    arrays.extend(
        (command["post_speculative_args"], ui["enabled" if plan.mode.services.ui else "disabled"])
    )
    arrays.append(vision["enabled" if plan.mode.services.vision else "disabled"])
    arrays.append(backends[plan.backend])
    return tuple(arrays)


def build_engine_command(executable: Path, plan: LaunchPlan, lock: JsonObject) -> tuple[str, ...]:
    """Build a complete shell-free command and enforce verified_flags defensively."""
    command = cast(JsonObject, lock["command_contract"])
    values = _values(plan)
    arguments: list[str] = [str(executable)]
    for tokens in _contract_arrays(plan, command):
        arguments.extend(_expand(tokens, values))
    verified = set(cast(list[str], lock["verified_flags"]))
    emitted = {token for token in arguments[1:] if token.startswith("-")}
    unknown = sorted(emitted - verified)
    if unknown:
        raise EngineError(f"engine command emitted flags outside engine.lock: {unknown}")
    return tuple(arguments)
