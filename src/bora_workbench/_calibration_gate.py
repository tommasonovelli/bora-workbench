"""Final per-envelope gate workloads for one calibration envelope (spec 3.5).

The gate runs once per selected envelope inside a fresh monitored process. It fails only on invalid
responses; reserve and release violations are caught by the trial monitors that wrap it. Per-turn
``prompt_n``/``cache_n`` are diagnostic, never pass/fail, because a hybrid model may legitimately
reprocess context.
"""

from __future__ import annotations

from typing import cast

import httpx

from bora_workbench._calibration_types import GateResult
from bora_workbench.benchmark import BenchmarkError, BenchmarkRetryableError, run_vision_probe
from bora_workbench.profiles import Mode

_SMOKE_TOKENS = 48
_TURN_TOKENS = 32
_MULTI_TURN_COUNT = 4
_TIMEOUT_SECONDS = 15 * 60.0
_RATIO_SAMPLE_WORDS = 256
_SMOKE_CONTEXT_FRACTION = 0.8
JsonObject = dict[str, object]


def _words(count: int) -> str:
    """Build one deterministic word sequence of the requested length."""
    return " ".join(f"ctx{index % 101}" for index in range(count))


def _tokens_per_word(client: httpx.Client, base_url: str) -> float:
    """Measure this model's tokens per generated word before sizing the smoke prompt.

    A word is not a token: on this vocabulary each ``ctxNN`` word costs roughly three tokens, so
    treating the 80% target as a word count overshoots the window and the server rejects the
    request outright. The ratio is measured once, from the same deterministic vocabulary, and the
    chat template overhead it also counts only makes the final prompt slightly smaller (spec 3.5).
    """
    payload = _payload([{"role": "user", "content": _words(_RATIO_SAMPLE_WORDS)}], 1)
    usage = cast(JsonObject, _post(client, base_url, payload)["usage"])
    try:
        prompt_tokens = int(cast(int, usage["prompt_tokens"]))
    except (KeyError, TypeError, ValueError) as error:
        raise BenchmarkError("gate response omitted the prompt token count") from error
    return max(1.0, prompt_tokens / _RATIO_SAMPLE_WORDS)


def _smoke_prompt(client: httpx.Client, base_url: str, ctx: int) -> str:
    """Build a deterministic prompt near 80% of the context window, measured in tokens."""
    words = int(ctx * _SMOKE_CONTEXT_FRACTION / _tokens_per_word(client, base_url))
    return _words(max(1, words))


def _post(client: httpx.Client, base_url: str, payload: JsonObject) -> JsonObject:
    """Submit one bounded gate request and require a JSON object response."""
    try:
        response = client.post(
            f"{base_url}/v1/chat/completions", json=payload, timeout=_TIMEOUT_SECONDS
        )
    except httpx.HTTPError as error:
        raise BenchmarkRetryableError(f"gate request failed: {error}") from error
    if response.status_code != 200:
        raise BenchmarkRetryableError(f"gate request returned HTTP {response.status_code}")
    value = response.json()
    if not isinstance(value, dict):
        raise BenchmarkError("gate response must be a JSON object")
    return cast(JsonObject, value)


def _is_valid(value: JsonObject, expected_n: int) -> bool:
    """Return whether one response finished at exactly the requested completion length."""
    try:
        choices = cast(list[JsonObject], value["choices"])
        finish_reason = choices[0]["finish_reason"]
        completion_n = int(cast(int, cast(JsonObject, value["usage"])["completion_tokens"]))
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    return finish_reason == "length" and completion_n == expected_n


def _payload(messages: list[JsonObject], max_tokens: int) -> JsonObject:
    """Build one deterministic uncached gate request."""
    return {
        "messages": messages,
        "max_tokens": max_tokens,
        "cache_prompt": False,
        "ignore_eos": True,
        "seed": 424242,
    }


def _smoke(client: httpx.Client, base_url: str, ctx: int) -> bool:
    """Run one near-full-context smoke request and require a valid bounded completion."""
    messages = [{"role": "user", "content": _smoke_prompt(client, base_url, ctx)}]
    return _is_valid(_post(client, base_url, _payload(messages, _SMOKE_TOKENS)), _SMOKE_TOKENS)


def _multi_turn(client: httpx.Client, base_url: str) -> bool:
    """Run four append-only turns and require every turn to finish validly (spec 3.5)."""
    messages: list[JsonObject] = []
    for index in range(_MULTI_TURN_COUNT):
        messages.append({"role": "user", "content": f"Turn {index}: continua la conversazione."})
        value = _post(client, base_url, _payload(messages, _TURN_TOKENS))
        if not _is_valid(value, _TURN_TOKENS):
            return False
        content = cast(JsonObject, cast(list[JsonObject], value["choices"])[0]["message"])
        messages.append({"role": "assistant", "content": str(content["content"])})
    return True


def _vision(client: httpx.Client, base_url: str) -> bool:
    """Run the pinned red-image request and require its verified answer for vstudio."""
    try:
        run_vision_probe(base_url, client)
    except BenchmarkError:
        return False
    return True


def _client(selected: httpx.Client | None) -> tuple[httpx.Client, bool]:
    """Return the injected client or one owned synchronous client."""
    return (selected, False) if selected is not None else (httpx.Client(), True)


def run_gate(base_url: str, mode: Mode, ctx: int, client: httpx.Client | None = None) -> GateResult:
    """Run smoke, multi-turn, and (for vision) the pinned image gate for one envelope."""
    selected, is_owned = _client(client)
    try:
        smoke = _smoke(selected, base_url, ctx)
        multi_turn = _multi_turn(selected, base_url)
        vision = _vision(selected, base_url) if mode.services.vision else None
    finally:
        if is_owned:
            selected.close()
    return GateResult(smoke, multi_turn, vision)
