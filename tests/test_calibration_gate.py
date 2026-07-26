"""Offline tests for the final envelope gate workloads."""

from __future__ import annotations

import json

import httpx

from bora_workbench._calibration_trial import run_gate
from bora_workbench.profiles import load_catalog


def _mode(mode_id: str):
    """Return one packaged mode for the gate under test."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    return mode


def _response(
    content: str, finish: str, completion: int, prompt_tokens: int = 745
) -> dict[str, object]:
    """Build one deterministic gate response, including the prompt size the sizing probe reads."""
    return {
        "choices": [{"finish_reason": finish, "message": {"content": content}}],
        "usage": {"completion_tokens": completion, "prompt_tokens": prompt_tokens},
    }


def _client(handler) -> httpx.Client:
    """Return an httpx client backed by a deterministic mock transport."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def valid_handler(request: httpx.Request) -> httpx.Response:
    """Return a valid completion whose length matches each requested max_tokens."""
    body = json.loads(request.content)
    max_tokens = int(body.get("max_tokens", 0))
    return httpx.Response(200, json=_response("Rosso", "length", max_tokens))


def test_gate_passes_for_text_and_vision_modes() -> None:
    """Pass smoke and multi-turn for text modes and add the image gate for vision."""
    with _client(valid_handler) as client:
        text = run_gate("http://127.0.0.1:8080", _mode("coding"), 65536, client)
        vision = run_gate("http://127.0.0.1:8080", _mode("vstudio"), 65536, client)
    assert text.smoke and text.multi_turn and text.vision is None and text.passed
    assert vision.smoke and vision.multi_turn and vision.vision is True and vision.passed


def test_gate_fails_when_smoke_completion_is_invalid() -> None:
    """Fail the gate when the near-full-context smoke request stops early."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        max_tokens = int(body.get("max_tokens", 0))
        finish = "stop" if max_tokens == 48 else "length"
        return httpx.Response(200, json=_response("Rosso", finish, max_tokens))

    with _client(handler) as client:
        result = run_gate("http://127.0.0.1:8080", _mode("coding"), 65536, client)
    assert not result.smoke
    assert not result.passed


def test_gate_fails_when_vision_answer_is_wrong() -> None:
    """Fail the vision gate when the pinned red image is not identified."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json=_response("Blu", "length", int(body.get("max_tokens", 0))))

    with _client(handler) as client:
        result = run_gate("http://127.0.0.1:8080", _mode("vstudio"), 65536, client)
    assert result.smoke and result.multi_turn
    assert result.vision is False
    assert not result.passed


def test_smoke_prompt_is_sized_in_tokens_not_words() -> None:
    """Keep the smoke prompt inside the window: a word costs several tokens on this vocabulary."""
    ctx = 65536
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        content = body["messages"][-1]["content"]
        prompts.append(content)
        words = len(content.split())
        return httpx.Response(
            200,
            json=_response("Rosso", "length", int(body["max_tokens"]), prompt_tokens=words * 3),
        )

    with _client(handler) as client:
        assert run_gate("http://127.0.0.1:8080", _mode("coding"), ctx, client).smoke

    smoke_words = len(prompts[1].split())
    assert smoke_words * 3 <= ctx
    assert smoke_words * 3 >= ctx * 0.5
