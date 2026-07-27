"""Offline tests for the calibration quick-bench workload and metric extraction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import httpx
import pytest

from bora_workbench.benchmark import BenchmarkError
from bora_workbench.benchmark_quick import (
    LONG_REQUEST_SHA256,
    SHORT_REQUEST_SHA256,
    ShortBench,
    run_confirm_bench,
    run_quick_bench,
    verify_protocol_resources,
)
from bora_workbench.resources import resource
from tests.sample_fixtures import short_bench


def quick_response(
    max_tokens: int,
    *,
    prompt_pps: float = 500.0,
    predicted_pps: float = 50.0,
    finish: str = "length",
    completion: int | None = None,
    draft_n: int = 10,
    draft_accepted: int = 7,
) -> dict[str, object]:
    """Build one deterministic llama.cpp timing response for a quick-bench request."""
    return {
        "choices": [{"finish_reason": finish, "message": {"content": "Risposta"}}],
        "usage": {"completion_tokens": max_tokens if completion is None else completion},
        "timings": {
            "prompt_n": 8,
            "cache_n": 0,
            "prompt_ms": 10.0,
            "prompt_per_second": prompt_pps,
            "predicted_n": max_tokens,
            "predicted_ms": 20.0,
            "predicted_per_second": predicted_pps,
            "draft_n": draft_n,
            "draft_n_accepted": draft_accepted,
        },
    }


def test_packaged_quick_bench_resources_match_pinned_digests() -> None:
    """Ship byte-identical quick-bench request resources instead of reconstructed content."""
    verify_protocol_resources()
    short = hashlib.sha256(resource("benchmark-quick/short-request.json").read_bytes()).hexdigest()
    long = hashlib.sha256(resource("benchmark-quick/long-request.json").read_bytes()).hexdigest()
    assert short == SHORT_REQUEST_SHA256
    assert long == LONG_REQUEST_SHA256


def test_warmup_excluded_and_three_short_plus_long_summarized() -> None:
    """Discard the first short run and summarize exactly three short plus one long request."""
    short_decode = iter([99.0, 40.0, 60.0, 50.0])
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Return controlled decode rates for short runs and a fixed long prefill rate."""
        body = json.loads(request.content)
        seen.append(body)
        if body["max_tokens"] == 64:
            return httpx.Response(200, json=quick_response(64, prompt_pps=333.0))
        return httpx.Response(200, json=quick_response(128, predicted_pps=next(short_decode)))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run_quick_bench("http://127.0.0.1:8080", client)

    assert len(result.short.metrics) == 3
    assert result.decode_tps_median == 50.0
    assert result.prefill_8k_tps == 333.0
    assert result.short_e2e_median_ms > 0
    assert result.long.draft_n == 10
    assert result.long.draft_n_accepted == 7
    assert len(seen) == 5
    assert all(body["cache_prompt"] is False and body["seed"] == 424242 for body in seen)


def test_confirmation_runs_the_warm_up_and_short_series_without_the_long_request() -> None:
    """Start no 23180-token prefill for a comparison that cannot read it (D-074)."""
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Record each request and answer every short run identically."""
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json=quick_response(128, predicted_pps=50.0))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run_confirm_bench("http://127.0.0.1:8080", client)

    assert len(seen) == 4
    assert all(body["max_tokens"] == 128 for body in seen)
    assert len(result.metrics) == 3
    assert result.decode_tps_median == 50.0


def test_dispersion_normalizes_the_short_spread_around_its_median() -> None:
    """Report the spread the third-round rule inspects, and zero when the median is unusable."""
    spread = short_bench(0.0)
    metrics = (
        replace(spread.metrics[0], e2e_ms=90.0),
        replace(spread.metrics[1], e2e_ms=100.0),
        replace(spread.metrics[2], e2e_ms=110.0),
    )

    assert ShortBench(metrics).dispersion == pytest.approx(0.2)
    assert spread.dispersion == 0.0


@pytest.mark.parametrize(
    "response_kwargs",
    [
        {"finish": "stop"},
        {"completion": 127},
        {"draft_n": 2, "draft_accepted": 5},
    ],
)
def test_invalid_quick_bench_evidence_is_rejected(response_kwargs: dict[str, object]) -> None:
    """Reject early finish, a wrong completion count, or impossible acceptance counts."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=quick_response(128, **response_kwargs))
    )
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(BenchmarkError),
    ):
        run_quick_bench("http://127.0.0.1:8080", client)
