"""Redact private bundle text and detect absolute paths or host identity leaks."""

from __future__ import annotations

import getpass
import re
import socket
from collections.abc import Mapping, Sequence
from pathlib import Path

_GENERIC_PRIVATE_PATTERNS = (
    re.compile(r"(?<![\w:])/(?:home|Users)/[^/\s\"']+"),
    re.compile(r"(?<![\w:])/(?:root|tmp|var|opt|mnt|media|srv|run|etc)(?:/[^\s\"']+)+"),
    re.compile(r"(?i)(?<![a-z0-9])[a-z]:[\\/][^\s\"']+"),
    re.compile(r"\\\\[^\\/\s]+[\\/][^\\/\s]+"),
)


def has_private_path_pattern(text: str) -> bool:
    """Return whether text contains a generic POSIX, Windows, or UNC private path."""
    return any(pattern.search(text) for pattern in _GENERIC_PRIVATE_PATTERNS)


def redact_text(text: str, private_values: tuple[str, ...]) -> str:
    """Replace every known private value and slash-normalized variant in text."""
    for value in private_values:
        text = text.replace(value, "<redacted>")
    return text


def relative_log_reason(
    reason: str | None, sources: tuple[Path, ...], evidence: tuple[tuple[str, str], ...]
) -> str | None:
    """Replace private runtime log paths with their copied bundle-relative counterparts."""
    if reason is None:
        return None
    for source, (relative, _digest) in zip(sources, evidence, strict=False):
        reason = reason.replace(str(source), relative)
        reason = reason.replace(source.as_posix(), relative)
    return reason


def redact_document(value: object, private_values: tuple[str, ...]) -> object:
    """Recursively redact every string in one generated shareable JSON document."""
    if isinstance(value, str):
        return redact_text(value, private_values)
    if isinstance(value, Mapping):
        return {key: redact_document(item, private_values) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_document(item, private_values) for item in value]
    return value


def _local_markers(root: Path) -> tuple[str, ...]:
    """Return local identity and path values that must not occur in a shared bundle."""
    values = {
        getpass.getuser(),
        socket.gethostname(),
        str(Path.home()),
        str(root.resolve()),
    }
    expanded = values | {value.replace("\\", "/") for value in values}
    return tuple(sorted((value for value in expanded if value), key=len, reverse=True))


def privacy_findings(root: Path) -> tuple[tuple[str, str], ...]:
    """Find local identity values and generic absolute paths in every shareable file."""
    markers = _local_markers(root)
    findings: list[tuple[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        if any(marker in text for marker in markers):
            findings.append((relative, "contains local username, hostname, or absolute path"))
            continue
        if has_private_path_pattern(text):
            findings.append((relative, "contains a private absolute path pattern"))
    return tuple(findings)
