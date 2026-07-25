"""Run the calibration quick-bench selection workload (IMPLEMENTATION_SPEC.md 1.3).

Every metric is read from the response ``timings`` and the wall clock, so no server log parsing or
SSE is needed. ``benchmark.py`` (benchmark/v1) stays intact for the feasibility probe.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from statistics import median
from typing import cast

import httpx

from qwen_launcher.benchmark import BenchmarkError, BenchmarkHttpError, BenchmarkRetryableError
from qwen_launcher.resources import resource

_SHORT_REQUEST_PATH = "benchmark-quick/short-request.json"
_LONG_REQUEST_PATH = "benchmark-quick/long-request.json"
SHORT_REQUEST_SHA256 = "c85566582ec1f7dbdefa2bdd4c44133729461047418a6a7dfc3cc9953733ee9e"
LONG_REQUEST_SHA256 = "03492ca4051c2565bb75bf80e9e079ba7b0c7dbd8c78530a6b04c39bbcaaa0ee"
_SHORT_TOKENS = 128
_LONG_TOKENS = 64
_SHORT_RUNS = 3
_REQUEST_TIMEOUT_SECONDS = 15 * 60.0
JsonObject = dict[str, object]


@dataclass(frozen=True, slots=True)
class QuickMetric:
    """Hold one quick-bench request's wall-clock and llama.cpp timing evidence."""

    workload: str
    e2e_ms: float
    prompt_per_second: float
    predicted_per_second: float
    prompt_ms: float
    prompt_n: int
    cache_n: int
    draft_n: int | None
    draft_n_accepted: int | None


@dataclass(frozen=True, slots=True)
class QuickBenchResult:
    """Group the three measured short requests and the one long ~8K-prefill request."""

    short: tuple[QuickMetric, QuickMetric, QuickMetric]
    long: QuickMetric

    @property
    def short_e2e_median_ms(self) -> float:
        """Return the median short end-to-end latency fast and balanced selection uses."""
        return median(metric.e2e_ms for metric in self.short)

    @property
    def decode_tps_median(self) -> float:
        """Return the median short decode throughput used as the ordering tie-break."""
        return median(metric.predicted_per_second for metric in self.short)

    @property
    def prefill_8k_tps(self) -> float:
        """Return the ~8K prefill throughput used as the deadband prefill tie-break."""
        return self.long.prompt_per_second


@dataclass(frozen=True, slots=True)
class _Workload:
    """Group one quick-bench request template with its verification target."""

    path: str
    name: str
    expected_n: int


def _load_request(path: str) -> JsonObject:
    """Load one immutable quick-bench request template as a fresh JSON object."""
    try:
        value = json.loads(resource(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BenchmarkError(f"cannot read quick-bench resource {path}: {error}") from error
    if not isinstance(value, dict):
        raise BenchmarkError(f"quick-bench resource {path} must contain an object")
    return cast(JsonObject, value)


def verify_protocol_resources() -> None:
    """Require byte-identical quick-bench resources before measuring (section 5.6)."""
    expected = (
        (_SHORT_REQUEST_PATH, SHORT_REQUEST_SHA256),
        (_LONG_REQUEST_PATH, LONG_REQUEST_SHA256),
    )
    for path, digest in expected:
        if hashlib.sha256(resource(path).read_bytes()).hexdigest() != digest:
            raise BenchmarkError(f"quick-bench resource digest mismatch: {path}")


def _post(client: httpx.Client, url: str, request: JsonObject) -> tuple[JsonObject, float]:
    """Submit one bounded loopback request and retain measured end-to-end milliseconds."""
    started = time.perf_counter()
    try:
        response = client.post(url, json=request, timeout=_REQUEST_TIMEOUT_SECONDS)
    except httpx.HTTPError as error:
        raise BenchmarkRetryableError(f"quick-bench request failed: {error}") from error
    elapsed_ms = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        raise BenchmarkHttpError(response.status_code)
    try:
        value = response.json()
    except ValueError as error:
        raise BenchmarkError("quick-bench response is not valid JSON") from error
    if not isinstance(value, dict):
        raise BenchmarkError("quick-bench response must be a JSON object")
    return cast(JsonObject, value), elapsed_ms


def _optional_int(timings: JsonObject, name: str) -> int | None:
    """Read one optional MTP counter while rejecting booleans and malformed values."""
    item = timings.get(name)
    if item is None:
        return None
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise BenchmarkError(f"quick-bench timing {name} must be a non-negative integer")
    return item


def _metric(value: JsonObject, elapsed_ms: float, workload: _Workload) -> QuickMetric:
    """Validate finish, token counts, and timing fields directly from one response."""
    try:
        timings = cast(JsonObject, value["timings"])
        choices = cast(list[JsonObject], value["choices"])
        finish_reason = choices[0]["finish_reason"]
        completion_n = int(cast(int, cast(JsonObject, value["usage"])["completion_tokens"]))
        predicted_n = int(cast(int, timings["predicted_n"]))
        metric = QuickMetric(
            workload.name,
            elapsed_ms,
            float(cast(float, timings["prompt_per_second"])),
            float(cast(float, timings["predicted_per_second"])),
            float(cast(float, timings["prompt_ms"])),
            int(cast(int, timings["prompt_n"])),
            int(cast(int, timings["cache_n"])),
            _optional_int(timings, "draft_n"),
            _optional_int(timings, "draft_n_accepted"),
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise BenchmarkError("quick-bench response is missing valid timings") from error
    if finish_reason != "length" or completion_n != workload.expected_n:
        raise BenchmarkError("quick-bench response did not finish at the requested token count")
    if predicted_n != workload.expected_n or metric.e2e_ms <= 0:
        raise BenchmarkError("quick-bench response contains invalid completion evidence")
    if metric.draft_n is not None and (metric.draft_n_accepted or 0) > metric.draft_n:
        raise BenchmarkError("quick-bench accepted more draft tokens than it produced")
    return metric


def _client(selected: httpx.Client | None) -> tuple[httpx.Client, bool]:
    """Return the injected client or one owned synchronous client."""
    return (selected, False) if selected is not None else (httpx.Client(), True)


def _measure(client: httpx.Client, url: str, workload: _Workload) -> QuickMetric:
    """Post one workload template and validate its measured response."""
    value, elapsed_ms = _post(client, url, _load_request(workload.path))
    return _metric(value, elapsed_ms, workload)


def run_quick_bench(base_url: str, client: httpx.Client | None = None) -> QuickBenchResult:
    """Run one excluded warm-up, three short requests, and one ~8K prefill request (spec 1.3)."""
    verify_protocol_resources()
    short = _Workload(_SHORT_REQUEST_PATH, "short", _SHORT_TOKENS)
    long_workload = _Workload(_LONG_REQUEST_PATH, "long", _LONG_TOKENS)
    selected, is_owned = _client(client)
    try:
        url = f"{base_url}/v1/chat/completions"
        _measure(selected, url, short)
        short_metrics = tuple(_measure(selected, url, short) for _ in range(_SHORT_RUNS))
        long_metric = _measure(selected, url, long_workload)
    finally:
        if is_owned:
            selected.close()
    triple = cast(tuple[QuickMetric, QuickMetric, QuickMetric], short_metrics)
    return QuickBenchResult(triple, long_metric)
