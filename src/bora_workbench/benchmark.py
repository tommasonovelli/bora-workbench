"""Run the immutable benchmark/v1 request and validate every measured response.

benchmark/v1 is the only protocol this module implements (specification section 4.1); the
calibration selection workload lives in `benchmark_quick.py` because it measures different
evidence against different pinned payloads.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from statistics import median
from typing import cast

import httpx

from bora_workbench.profiles import TokenRate
from bora_workbench.resources import resource

_PROMPT_PATH = "benchmark-v1/prompt.txt"
_REQUEST_PATH = "benchmark-v1/request.json"
_VISION_REQUEST_PATH = "calibration-v1/vision-request.json"
PROMPT_SHA256 = "1c7182235411da2d4fe6fca130e3effb0b0d965569c52abd8fd45327103ddb2e"
REQUEST_SHA256 = "025dc91aeb61a790d5fd36c27f127e04761ae7f1c3d6b542d0cfd9d37bc5c19f"
VISION_REQUEST_SHA256 = "2641e7a3d3e23b6779fb3a73eefae4ed5a27dec19280384c33df170aeaad483c"
_COMPLETION_TOKENS = 256
_REQUEST_TIMEOUT_SECONDS = 15 * 60.0
JsonObject = dict[str, object]


class BenchmarkError(RuntimeError):
    """Report an invalid request resource, API response, or benchmark measurement."""


class BenchmarkRetryableError(BenchmarkError):
    """Report a transient transport or HTTP response failure."""


class BenchmarkHttpError(BenchmarkError):
    """Retain a non-success HTTP status for class-based trial classification."""

    def __init__(self, status_code: int) -> None:
        """Attach the returned status without parsing an exception message."""
        super().__init__(f"benchmark request returned HTTP {status_code}")
        self.status_code = status_code


class BenchmarkHttpRetryableError(BenchmarkHttpError, BenchmarkRetryableError):
    """Report a non-success status whose cause a repeated request can plausibly clear."""


# A 4xx answer is the server's verdict on the request that was sent, so repeating that exact
# request cannot change it; only server-side failures and the wait-and-retry statuses earn a
# retry. `process.py` applies the same rule to health responses (spec section 5.6, D-059).
_RETRYABLE_STATUSES = frozenset({408, 425, 429})


def http_status_error(status_code: int) -> BenchmarkHttpError:
    """Build the error class one non-success status maps to, keeping D-059 class-based."""
    if status_code >= 500 or status_code in _RETRYABLE_STATUSES:
        return BenchmarkHttpRetryableError(status_code)
    return BenchmarkHttpError(status_code)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Hold the excluded warm-up and exactly five benchmark/v1 measurements."""

    warmup_tok_s: float
    measured_tok_s: tuple[float, float, float, float, float]
    tok_s: TokenRate


def _load_request(path: str) -> JsonObject:
    """Load one immutable request template as a fresh JSON object."""
    try:
        value = json.loads(resource(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BenchmarkError(f"cannot read request resource {path}: {error}") from error
    if not isinstance(value, dict):
        raise BenchmarkError(f"request resource {path} must contain an object")
    return cast(JsonObject, value)


def verify_protocol_resources() -> None:
    """Require byte-identical benchmark resources from measured evidence (section 5.6).

    The vision request digest is the one measured for the Ubuntu Spike 0 evidence copies in
    ``evidence/engine/spike-0/SHA256SUMS``, which the resource matches byte for byte.
    """
    expected = (
        (_PROMPT_PATH, PROMPT_SHA256),
        (_REQUEST_PATH, REQUEST_SHA256),
        (_VISION_REQUEST_PATH, VISION_REQUEST_SHA256),
    )
    for path, digest in expected:
        actual = hashlib.sha256(resource(path).read_bytes()).hexdigest()
        if actual != digest:
            raise BenchmarkError(f"protocol resource digest mismatch: {path}")


@contextmanager
def _session(client: httpx.Client | None) -> Iterator[httpx.Client]:
    """Yield the caller's client, or one this module owns and closes on exit.

    A caller that runs several workloads passes its own client so the connection pool is reused;
    when none is supplied the run must not leak the pool it created.
    """
    if client is not None:
        yield client
        return
    with httpx.Client() as owned:
        yield owned


def _post(client: httpx.Client, url: str, request: JsonObject) -> JsonObject:
    """Submit one bounded loopback request and require a JSON object response."""
    try:
        response = client.post(url, json=request, timeout=_REQUEST_TIMEOUT_SECONDS)
    except httpx.HTTPError as error:
        raise BenchmarkRetryableError(f"benchmark request failed: {error}") from error
    if response.status_code != 200:
        raise http_status_error(response.status_code)
    try:
        value = response.json()
    except ValueError as error:
        raise BenchmarkError("benchmark response is not valid JSON") from error
    if not isinstance(value, dict):
        raise BenchmarkError("benchmark response must be a JSON object")
    return cast(JsonObject, value)


def _measurement(value: JsonObject) -> float:
    """Validate exact-token completion evidence and return cross-checked token throughput."""
    try:
        choices = cast(list[JsonObject], value["choices"])
        usage = cast(JsonObject, value["usage"])
        timings = cast(JsonObject, value["timings"])
        finish_reason = choices[0]["finish_reason"]
        completion_tokens = usage["completion_tokens"]
        predicted_n = timings["predicted_n"]
        predicted_ms = float(cast(float, timings["predicted_ms"]))
        measured = float(cast(float, timings["predicted_per_second"]))
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise BenchmarkError("benchmark response is missing timing or token evidence") from error
    if finish_reason != "length" or completion_tokens != _COMPLETION_TOKENS:
        raise BenchmarkError("benchmark response did not finish at exactly 256 completion tokens")
    if predicted_n != _COMPLETION_TOKENS or predicted_ms <= 0 or measured < 0:
        raise BenchmarkError("benchmark response contains invalid prediction timing evidence")
    cross_checked = _COMPLETION_TOKENS / (predicted_ms / 1000)
    if not math.isclose(measured, cross_checked, rel_tol=1e-9, abs_tol=1e-9):
        raise BenchmarkError("predicted_per_second does not match predicted_n / predicted_ms")
    return measured


def run_probe(base_url: str, client: httpx.Client | None = None) -> float:
    """Run one verified textual workload without treating it as a benchmark measurement set."""
    verify_protocol_resources()
    with _session(client) as session:
        response = _post(session, f"{base_url}/v1/chat/completions", _load_request(_REQUEST_PATH))
        return _measurement(response)


def run_vision_probe(base_url: str, client: httpx.Client | None = None) -> None:
    """Run the red-image request verified by Spike 0 and require its observed answer."""
    verify_protocol_resources()
    with _session(client) as session:
        try:
            response = _post(
                session,
                f"{base_url}/v1/chat/completions",
                _load_request(_VISION_REQUEST_PATH),
            )
            choices = cast(list[JsonObject], response.get("choices"))
            message = cast(JsonObject, choices[0]["message"])
            if "rosso" not in str(message["content"]).casefold():
                raise BenchmarkError("vision workload did not identify the verified red image")
        except (KeyError, IndexError, TypeError) as error:
            raise BenchmarkError("vision response is missing assistant content") from error


def run_benchmark(base_url: str, client: httpx.Client | None = None) -> BenchmarkResult:
    """Execute one excluded warm-up and exactly five valid benchmark/v1 measurements."""
    verify_protocol_resources()
    with _session(client) as session:
        url = f"{base_url}/v1/chat/completions"
        warmup = _measurement(_post(session, url, _load_request(_REQUEST_PATH)))
        values = tuple(
            _measurement(_post(session, url, _load_request(_REQUEST_PATH))) for _ in range(5)
        )
    measured = cast(tuple[float, float, float, float, float], values)
    summary = TokenRate(min(measured), median(measured), max(measured))
    return BenchmarkResult(warmup, measured, summary)
