"""Verify one llama.cpp executable against the locked probe contracts."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import cast

from bora_workbench._engine_types import EngineError

JsonObject = dict[str, object]
_PROBE_TIMEOUT_SECONDS = 60


def _probe(executable: Path, contract: JsonObject) -> str:
    """Run one bounded version or help probe without a shell."""
    args = [str(executable), *cast(list[str], contract["args"])]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EngineError(f"cannot probe engine {executable}: {error}") from error
    output = result.stdout + result.stderr
    if result.returncode != contract["exit_code"]:
        raise EngineError(f"engine probe failed with exit code {result.returncode}: {executable}")
    return output


def _flag_listed(output: str, flag: str) -> bool:
    """Match one complete option token rather than accepting it inside another flag."""
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(flag)}(?![A-Za-z0-9_-])"
    return re.search(pattern, output) is not None


def verify_engine(executable: Path, lock: JsonObject) -> Path:
    """Require the lock's version fragments and complete verified option vocabulary."""
    version_contract = cast(JsonObject, lock["version_contract"])
    version_output = _probe(executable, version_contract)
    fragments = cast(list[str], version_contract["output_contains"])
    if any(fragment not in version_output for fragment in fragments):
        raise EngineError(
            f"engine version is incompatible with release {lock['release']}: {executable}"
        )
    help_output = _probe(executable, cast(JsonObject, lock["help_contract"]))
    missing = [
        flag
        for flag in cast(list[str], lock["verified_flags"])
        if not _flag_listed(help_output, flag)
    ]
    if missing:
        raise EngineError(f"engine help is missing verified flags {missing}: {executable}")
    return executable.resolve()
