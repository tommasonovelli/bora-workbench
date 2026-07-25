"""Read out-of-memory evidence from engine logs and name the exhausted memory resource.

An exhausted GPU allocation cannot be observed by the VRAM monitor: the driver rejects the
allocation, so free VRAM never falls below the monitored reserve and the engine simply exits during
model load. The process log is therefore the only evidence available for the VRAM side, while the
RAM side stays class-based through ``RamReserveError`` (spec 5.6, D-059).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

# "oom" must match as a whole word: a bare substring test would classify unrelated log text
# such as "zoom" as an out-of-memory failure.
OOM_PATTERN = re.compile(r"\boom\b|out of memory")

# The engine names the refusing device on the failing line itself, so the marker is searched per
# line: a CUDA banner elsewhere in the log must not turn a host allocation failure into a GPU one.
_DEVICE_PATTERN = re.compile(r"cuda|cublas|vram|gpu|device")

MemoryResource = Literal["ram", "vram"]


def read_logs(paths: tuple[Path, ...]) -> str:
    """Concatenate the readable process logs, skipping the ones this run cannot open."""
    parts: list[str] = []
    for path in paths:
        try:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(parts)


def oom_resource(text: str) -> MemoryResource | None:
    """Return the memory resource named by out-of-memory evidence, or None when there is none."""
    failing = [line for line in text.casefold().splitlines() if OOM_PATTERN.search(line)]
    if not failing:
        return None
    return "vram" if any(_DEVICE_PATTERN.search(line) for line in failing) else "ram"
