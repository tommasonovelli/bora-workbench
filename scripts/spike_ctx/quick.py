"""Measure quick-bench fields directly from llama.cpp JSON responses."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx

from qwen_launcher.benchmark import BenchmarkError, BenchmarkHttpError, BenchmarkRetryableError
from scripts.spike_ctx.models import QuickResult, RequestMetric

_SHORT_PROMPT = "Rispondi con una breve frase deterministica sulla calibrazione locale."
_LONG_PROMPT = " ".join(f"dato{i % 97}" for i in range(8192))
_TIMEOUT_SECONDS = 15 * 60.0
JsonObject = dict[str, object]


@dataclass(frozen=True, slots=True)
class QuickRequest:
    """Group endpoint and raw-response destination for one process measurement."""

    base_url: str
    response_root: Path


def _payload(prompt: str, max_tokens: int) -> JsonObject:
    """Build a deterministic uncached request so repeated calls remain independent."""
    return {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "cache_prompt": False,
        "ignore_eos": True,
        "seed": 424242,
    }


def _post(client: httpx.Client, url: str, payload: JsonObject) -> tuple[JsonObject, float]:
    """Submit one bounded request and retain end-to-end milliseconds."""
    started = time.perf_counter()
    try:
        response = client.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
    except httpx.HTTPError as error:
        raise BenchmarkRetryableError(f"spike request failed: {error}") from error
    elapsed_ms = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        raise BenchmarkHttpError(response.status_code)
    try:
        value = response.json()
    except ValueError as error:
        raise BenchmarkError("spike response is not valid JSON") from error
    if not isinstance(value, dict):
        raise BenchmarkError("spike response must be a JSON object")
    return cast(JsonObject, value), elapsed_ms


def _metric(value: JsonObject, elapsed_ms: float, workload: str) -> RequestMetric:
    """Validate every required timing field without parsing server logs."""
    try:
        timings = cast(JsonObject, value["timings"])
        choices = cast(list[JsonObject], value["choices"])
        usage = cast(JsonObject, value["usage"])
        predicted_n = int(cast(int, timings["predicted_n"]))
        completion_n = int(cast(int, usage["completion_tokens"]))
        finish_reason = choices[0]["finish_reason"]
        metric = RequestMetric(
            cast(str, workload),
            elapsed_ms,
            float(cast(float, timings["prompt_per_second"])),
            float(cast(float, timings["predicted_per_second"])),
            float(cast(float, timings["prompt_ms"])),
            int(cast(int, timings["prompt_n"])),
            int(cast(int, timings["cache_n"])),
            _optional_int(timings, "draft_n"),
            _optional_int(timings, "draft_n_accepted"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise BenchmarkError("spike response is missing valid timings") from error
    expected_n = 64 if workload == "long" else 128
    if finish_reason != "length" or completion_n != expected_n or predicted_n != expected_n:
        raise BenchmarkError("spike response did not finish at the requested token count")
    if metric.prompt_n < 0 or metric.cache_n < 0 or metric.e2e_ms <= 0:
        raise BenchmarkError("spike response contains invalid timing counts")
    if metric.draft_n is not None and (metric.draft_n_accepted or 0) > metric.draft_n:
        raise BenchmarkError("spike response accepted more draft tokens than it produced")
    return metric


def _optional_int(value: JsonObject, name: str) -> int | None:
    """Read one optional MTP counter while rejecting booleans and malformed values."""
    item = value.get(name)
    if item is None:
        return None
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise BenchmarkError(f"spike timing {name} must be a non-negative integer")
    return item


def _measure(
    client: httpx.Client, request: QuickRequest, item: tuple[str, str, int, int]
) -> RequestMetric:
    """Measure and persist one indexed workload response."""
    name, prompt, max_tokens, index = item
    value, elapsed_ms = _post(
        client, f"{request.base_url}/v1/chat/completions", _payload(prompt, max_tokens)
    )
    request.response_root.mkdir(parents=True, exist_ok=True)
    path = request.response_root / f"response-{index}-{name}.json"
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return _metric(value, elapsed_ms, name)


def run_quick(request: QuickRequest) -> QuickResult:
    """Run one warm-up, three uncached short requests, and one long request."""
    items = [("short", _SHORT_PROMPT, 128, index) for index in range(1, 5)]
    items.append(("long", _LONG_PROMPT, 64, 5))
    with httpx.Client() as client:
        metrics = tuple(_measure(client, request, item) for item in items)
    return QuickResult(
        metrics[0],
        cast(tuple[RequestMetric, RequestMetric, RequestMetric], metrics[1:4]),
        metrics[4],
    )


def run_reasoning(request: QuickRequest) -> tuple[RequestMetric, RequestMetric, RequestMetric]:
    """Run three reasoning-off requests and reject visible thinking blocks."""
    metrics = []
    with httpx.Client() as client:
        for index in range(1, 4):
            payload = _payload(_SHORT_PROMPT, 128)
            value, elapsed = _post(client, f"{request.base_url}/v1/chat/completions", payload)
            request.response_root.mkdir(parents=True, exist_ok=True)
            path = request.response_root / f"reasoning-response-{index}.json"
            path.write_text(
                json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            content = json.dumps(value, ensure_ascii=False).casefold()
            if "<think>" in content:
                raise BenchmarkError("reasoning-off response contains a <think> block")
            metrics.append(_metric(value, elapsed, "reasoning"))
    return cast(tuple[RequestMetric, RequestMetric, RequestMetric], tuple(metrics))
