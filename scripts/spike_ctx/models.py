"""Define compact JSON-ready values for the cross-context spike."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RequestMetric:
    """Retain wall-clock and server timing fields from one measured response."""

    workload: Literal["short", "long", "reasoning"]
    e2e_ms: float
    prompt_per_second: float
    predicted_per_second: float
    prompt_ms: float
    prompt_n: int
    cache_n: int
    draft_n: int | None
    draft_n_accepted: int | None


@dataclass(frozen=True, slots=True)
class QuickResult:
    """Hold one excluded warm-up, three short requests, and one long request."""

    warmup: RequestMetric
    short: tuple[RequestMetric, RequestMetric, RequestMetric]
    long: RequestMetric


@dataclass(frozen=True, slots=True)
class TrialResult:
    """Describe one completed process without serializing private host paths."""

    ctx: int
    n_cpu_moe: int
    speculative: Literal["mtp2", "disabled"]
    quick: QuickResult
    minimum_ram_available_gib: float
    minimum_vram_free_gib: float


@dataclass(frozen=True, slots=True)
class SearchStep:
    """Record one bounded feasibility probe and its class-based outcome."""

    n_cpu_moe: int
    outcome: str
    resource: Literal["ram", "vram"] | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Retain the discovered boundary, prudent point, and complete probe order."""

    boundary: int | None
    prudent: int
    steps: tuple[SearchStep, ...]


def to_json(value: object) -> object:
    """Convert nested spike dataclasses into strict JSON-compatible values."""
    return asdict(value) if hasattr(value, "__dataclass_fields__") else value
