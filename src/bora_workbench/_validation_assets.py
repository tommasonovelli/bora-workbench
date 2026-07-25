"""Validate the complete engine asset matrix and its safe installation metadata."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import cast
from urllib.parse import urlparse

from bora_workbench.validation import ValidationIssue

JsonObject = dict[str, object]
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ROLES = {"server", "cuda-runtime", "source"}
_REQUIRED = {
    ("ubuntu", "cpu"): {"server"},
    ("ubuntu", "cuda"): {"source"},
    ("windows", "cpu"): {"server"},
    ("windows", "cuda"): {"server", "cuda-runtime"},
}
_FIELDS = {"os", "backend", "role", "filename", "url", "sha256", "archive", "executable"}


def _error(path: str, message: str) -> ValidationIssue:
    """Create one engine asset validation error."""
    return ValidationIssue("error", "engine.lock", path, message)


def _is_safe_relative(value: str) -> bool:
    """Recognize a relative path under both supported platform syntaxes."""
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    return bool(posix.parts) and not (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    )


def _identity_issues(lock: JsonObject) -> list[ValidationIssue]:
    """Validate source identity needed for the pinned Ubuntu CUDA build."""
    issues: list[ValidationIssue] = []
    if lock.get("project") != "ggml-org/llama.cpp":
        issues.append(_error("$.project", "must equal 'ggml-org/llama.cpp'"))
    commit = lock.get("source_commit")
    if not isinstance(commit, str) or _HEX_40.fullmatch(commit) is None:
        issues.append(_error("$.source_commit", "must be a 40-character lowercase commit"))
    if not isinstance(lock.get("assets_complete"), bool):
        issues.append(_error("$.assets_complete", "must be a boolean"))
    return issues


def _path_issues(item: JsonObject, path: str) -> list[ValidationIssue]:
    """Validate archive and executable paths before extraction can consume them."""
    issues: list[ValidationIssue] = []
    filename = item.get("filename")
    if not isinstance(filename, str) or not _is_safe_relative(filename):
        issues.append(_error(f"{path}.filename", "must be a safe relative filename"))
    elif "/" in filename or "\\" in filename:
        issues.append(_error(f"{path}.filename", "must not contain directory components"))
    executable = item.get("executable")
    role = item.get("role")
    if role in {"server", "source"}:
        if not isinstance(executable, str) or not _is_safe_relative(executable):
            issues.append(_error(f"{path}.executable", "must be a safe relative path"))
    elif executable is not None:
        issues.append(_error(f"{path}.executable", "must be null for non-server runtime assets"))
    return issues


def _value_issues(item: JsonObject, path: str) -> list[ValidationIssue]:
    """Validate one asset's exact fields, target values, URL, format, and digest."""
    issues: list[ValidationIssue] = []
    if set(item) != _FIELDS:
        issues.append(_error(path, f"must contain exactly {sorted(_FIELDS)}"))
    if item.get("os") not in {"ubuntu", "windows"}:
        issues.append(_error(f"{path}.os", "must be 'ubuntu' or 'windows'"))
    if item.get("backend") not in {"cpu", "cuda"}:
        issues.append(_error(f"{path}.backend", "must be 'cpu' or 'cuda'"))
    if item.get("role") not in _ROLES:
        issues.append(_error(f"{path}.role", f"must be one of {sorted(_ROLES)}"))
    url = item.get("url")
    if not isinstance(url, str) or urlparse(url).scheme != "https" or not urlparse(url).netloc:
        issues.append(_error(f"{path}.url", "must be an absolute HTTPS URL"))
    digest = item.get("sha256")
    if not isinstance(digest, str) or _HEX_64.fullmatch(digest) is None:
        issues.append(_error(f"{path}.sha256", "must be 64 lowercase hexadecimal characters"))
    if item.get("archive") not in {"zip", "tar.gz"}:
        issues.append(_error(f"{path}.archive", "must be 'zip' or 'tar.gz'"))
    issues.extend(_path_issues(item, path))
    return issues


def _matrix_issues(assets: list[JsonObject]) -> list[ValidationIssue]:
    """Require one exact role set for every supported OS/backend pair."""
    issues: list[ValidationIssue] = []
    for pair, expected in _REQUIRED.items():
        selected = [item for item in assets if (item.get("os"), item.get("backend")) == pair]
        roles = {item.get("role") for item in selected}
        if roles != expected or len(selected) != len(expected):
            label = f"{pair[0]}/{pair[1]}"
            issues.append(_error("$.assets", f"{label} must contain roles {sorted(expected)}"))
    return issues


def validate_assets(lock: JsonObject) -> list[ValidationIssue]:
    """Validate the complete matrix and bind Ubuntu CUDA source to the pinned commit."""
    issues = _identity_issues(lock)
    values = lock.get("assets")
    if not isinstance(values, list):
        return [*issues, _error("$.assets", "must be an array")]
    assets: list[JsonObject] = []
    for index, value in enumerate(values):
        path = f"$.assets[{index}]"
        if not isinstance(value, dict):
            issues.append(_error(path, "must be an object"))
            continue
        item = cast(JsonObject, value)
        assets.append(item)
        issues.extend(_value_issues(item, path))
    issues.extend(_matrix_issues(assets))
    source = next((item for item in assets if item.get("role") == "source"), None)
    if source is not None and str(lock.get("source_commit")) not in str(source.get("url")):
        issues.append(_error("$.assets", "source URL must contain the pinned source_commit"))
    return issues
