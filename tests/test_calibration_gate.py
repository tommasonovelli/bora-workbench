"""Offline tests for the final envelope gate workloads."""

from __future__ import annotations

import json

import httpx
import pytest

import bora_workbench._calibration_trial as trial_module
from bora_workbench._calibration_trial import run_gate
from bora_workbench.benchmark import BenchmarkError, BenchmarkRetryableError
from bora_workbench.profiles import load_catalog

_REAL_CLIENT = httpx.Client


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
    return _REAL_CLIENT(transport=httpx.MockTransport(handler))


def _run(monkeypatch, handler, mode_id: str, ctx: int = 65536):
    """Run one Gate through its production-owned client and verify deterministic closure."""
    client = _client(handler)
    monkeypatch.setattr(trial_module.httpx, "Client", lambda: client)

    result = run_gate("http://127.0.0.1:8080", _mode(mode_id), ctx)

    assert client.is_closed
    return result


def valid_handler(request: httpx.Request) -> httpx.Response:
    """Return a valid completion whose length matches each requested max_tokens."""
    body = json.loads(request.content)
    max_tokens = int(body.get("max_tokens", 0))
    return httpx.Response(200, json=_response("Rosso", "length", max_tokens))


def test_gate_passes_for_text_and_vision_modes(monkeypatch) -> None:
    """Pass smoke and multi-turn for text modes and add the image gate for vision."""
    text = _run(monkeypatch, valid_handler, "coding")
    vision = _run(monkeypatch, valid_handler, "vstudio")
    assert text.smoke and text.multi_turn and text.vision is None and text.passed
    assert vision.smoke and vision.multi_turn and vision.vision is True and vision.passed


def test_multi_turn_preserves_the_measured_input(monkeypatch) -> None:
    """Pin the non-English multi-turn payload because changing it invalidates real evidence."""
    turns: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture each newest multi-turn message while returning valid completions."""
        body = json.loads(request.content)
        max_tokens = int(body.get("max_tokens", 0))
        if max_tokens == 32:
            turns.append(body["messages"][-1]["content"])
        return httpx.Response(200, json=_response("Rosso", "length", max_tokens))

    assert _run(monkeypatch, handler, "coding").passed
    assert turns == [f"Turn {index}: continua la conversazione." for index in range(4)]


def test_gate_fails_when_smoke_completion_is_invalid(monkeypatch) -> None:
    """Fail the gate when the near-full-context smoke request stops early."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a short smoke completion and valid later completions."""
        body = json.loads(request.content)
        max_tokens = int(body.get("max_tokens", 0))
        finish = "stop" if max_tokens == 48 else "length"
        return httpx.Response(200, json=_response("Rosso", finish, max_tokens))

    result = _run(monkeypatch, handler, "coding")
    assert not result.smoke
    assert not result.passed


def test_gate_fails_when_vision_answer_is_wrong(monkeypatch) -> None:
    """Fail the vision gate when the pinned red image is not identified."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return the wrong image colour while preserving valid counters."""
        body = json.loads(request.content)
        return httpx.Response(200, json=_response("Blu", "length", int(body.get("max_tokens", 0))))

    result = _run(monkeypatch, handler, "vstudio")
    assert result.smoke and result.multi_turn
    assert result.vision is False
    assert not result.passed


def test_smoke_prompt_is_sized_in_tokens_not_words(monkeypatch) -> None:
    """Keep the smoke prompt inside the window: a word costs several tokens on this vocabulary."""
    ctx = 65536
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Measure the generated prompt with the regression's token ratio."""
        body = json.loads(request.content)
        content = body["messages"][-1]["content"]
        prompts.append(content)
        words = len(content.split())
        return httpx.Response(
            200,
            json=_response("Rosso", "length", int(body["max_tokens"]), prompt_tokens=words * 3),
        )

    assert _run(monkeypatch, handler, "coding", ctx).smoke

    smoke_words = len(prompts[1].split())
    assert smoke_words * 3 <= ctx
    assert smoke_words * 3 >= ctx * 0.5


def test_malformed_gate_json_is_protocol_invalid(monkeypatch) -> None:
    """Map a non-JSON success response into the benchmark protocol taxonomy."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return malformed JSON behind a successful HTTP status."""
        del request
        return httpx.Response(200, content=b"{broken")

    with pytest.raises(BenchmarkError, match="valid JSON"):
        _run(monkeypatch, handler, "coding")


def test_missing_multi_turn_message_is_protocol_invalid(monkeypatch) -> None:
    """Reject a response that has valid counters but no assistant message to append."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Remove the assistant message from the first multi-turn response."""
        body = json.loads(request.content)
        response = _response("unused", "length", int(body["max_tokens"]))
        if len(body["messages"]) == 1 and body["max_tokens"] == 32:
            response["choices"][0].pop("message")
        return httpx.Response(200, json=response)

    with pytest.raises(BenchmarkError, match="assistant message"):
        _run(monkeypatch, handler, "coding")


def test_vision_transport_failure_remains_retryable(monkeypatch) -> None:
    """Do not turn a retryable image request into an ordinary failed vision Gate."""
    monkeypatch.setattr(
        trial_module,
        "run_vision_probe",
        lambda base_url, client: (_ for _ in ()).throw(BenchmarkRetryableError("reset")),
    )

    with pytest.raises(BenchmarkRetryableError, match="reset"):
        _run(monkeypatch, valid_handler, "vstudio")


def test_client_close_failure_cannot_mask_keyboard_interrupt(monkeypatch) -> None:
    """Preserve control-flow precedence when the owned HTTP client also fails to close."""

    class _Client:
        """Fail cleanup after the workload has already been interrupted."""

        def close(self) -> None:
            """Raise an operational cleanup failure."""
            raise RuntimeError("close failed")

    monkeypatch.setattr(trial_module.httpx, "Client", _Client)
    monkeypatch.setattr(
        trial_module,
        "_smoke",
        lambda client, base_url, ctx: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        run_gate("http://127.0.0.1:8080", _mode("coding"), 65536)
