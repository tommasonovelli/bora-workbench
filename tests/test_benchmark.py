"""Offline tests for immutable benchmark/v1 requests and exact response evidence."""

from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from qwen_launcher.benchmark import (
    PROMPT_SHA256,
    REQUEST_SHA256,
    VISION_REQUEST_SHA256,
    BenchmarkError,
    run_benchmark,
    run_vision_probe,
    verify_protocol_resources,
)
from qwen_launcher.resources import resource


def response(rate: float, *, tokens: int = 256, finish_reason: str = "length") -> dict[str, object]:
    """Build one exact-token llama.cpp timing response at a chosen throughput."""
    predicted_ms = 256_000 / rate
    return {
        "choices": [{"finish_reason": finish_reason, "message": {"content": "Rosso"}}],
        "usage": {"completion_tokens": tokens},
        "timings": {
            "predicted_n": 256,
            "predicted_ms": predicted_ms,
            "predicted_per_second": rate,
        },
    }


def test_packaged_protocol_bytes_match_spike_hashes() -> None:
    """Ship byte-identical prompt and request resources instead of reconstructed content."""
    verify_protocol_resources()

    assert (
        hashlib.sha256(resource("benchmark-v1/prompt.txt").read_bytes()).hexdigest()
        == PROMPT_SHA256
    )
    assert (
        hashlib.sha256(resource("benchmark-v1/request.json").read_bytes()).hexdigest()
        == REQUEST_SHA256
    )
    assert (
        hashlib.sha256(resource("calibration-v1/vision-request.json").read_bytes()).hexdigest()
        == VISION_REQUEST_SHA256
    )


def test_warmup_is_excluded_and_five_measurements_are_summarized() -> None:
    """Exclude the first run and compute min/median/max from exactly the next five."""
    rates = iter([99.0, 5.0, 1.0, 4.0, 2.0, 3.0])
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture local request bodies and return deterministic valid timing evidence."""
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response(next(rates)))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run_benchmark("http://127.0.0.1:8080", client)

    assert result.warmup_tok_s == 99
    assert result.measured_tok_s == (5, 1, 4, 2, 3)
    assert (result.tok_s.minimum, result.tok_s.median, result.tok_s.maximum) == (1, 3, 5)
    expected = json.loads(resource("benchmark-v1/request.json").read_text(encoding="utf-8"))
    assert requests == [expected] * 6


@pytest.mark.parametrize(("tokens", "finish_reason"), [(255, "length"), (256, "stop")])
def test_invalid_exact_token_evidence_is_rejected(tokens: int, finish_reason: str) -> None:
    """Reject early finish or a completion count different from benchmark/v1's exact 256."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json=response(10, tokens=tokens, finish_reason=finish_reason)
        )
    )
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(BenchmarkError, match="exactly 256"),
    ):
        run_benchmark("http://127.0.0.1:8080", client)


def test_vision_probe_requires_the_verified_red_image_answer() -> None:
    """Exercise vstudio's real image request and reject an incompatible answer."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "Blu"}}]})
    )
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(BenchmarkError, match="red image"),
    ):
        run_vision_probe("http://127.0.0.1:8080", client)
