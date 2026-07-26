"""Validate the machine lock before runtime code installs assets or expands command templates.

The module owns one area of competence: everything `engine.lock` declares. It checks the engine
identity and the pinned default-model artifacts (section 5.8), requires the complete asset matrix
that safe managed installation depends on (section 5.10), and rejects any option token outside
`verified_flags` or any placeholder the command builder cannot expand (section 5.7). Digests, the
pinned source commit, and the asset roles bind downloaded bytes, so the checks compare exact values
instead of shapes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import PurePosixPath, PureWindowsPath
from typing import cast
from urllib.parse import urlparse

from bora_workbench.validation import JsonObject, ValidationIssue

_ALLOWED_PLACEHOLDERS = {
    "ctx",
    "mmproj",
    "min_p",
    "model_path",
    "n_cpu_moe",
    "port",
    "presence_penalty",
    "repeat_penalty",
    "temp",
    "top_k",
    "top_p",
}
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DEVICE = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.I)
_ASSET_ROLES = {"server", "cuda-runtime", "source"}
_REQUIRED_ROLES = {
    ("ubuntu", "cpu"): {"server"},
    ("ubuntu", "cuda"): {"source"},
    ("windows", "cpu"): {"server"},
    ("windows", "cuda"): {"server", "cuda-runtime"},
}
_ASSET_FIELDS = {"os", "backend", "role", "filename", "url", "sha256", "archive", "executable"}


def _error(path: str, message: str) -> ValidationIssue:
    """Create one engine.lock validation error."""
    return ValidationIssue("error", "engine.lock", path, message)


def _is_safe_relative(value: str) -> bool:
    """Recognize a relative path under both supported platform syntaxes."""
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    return bool(posix.parts) and not (
        "\\" in value
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
        or _has_unsafe_windows_component(posix.parts)
    )


def _has_unsafe_windows_component(parts: tuple[str, ...]) -> bool:
    """Reject paths Windows aliases, redirects, or normalizes."""
    forbidden = '<>:"|?*'
    return any(
        not part
        or part.endswith((" ", "."))
        or any(character in forbidden or ord(character) < 32 for character in part)
        or _WINDOWS_DEVICE.fullmatch(part) is not None
        for part in parts
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


def _asset_path_issues(item: JsonObject, path: str) -> list[ValidationIssue]:
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


def _asset_value_issues(item: JsonObject, path: str) -> list[ValidationIssue]:
    """Validate one asset's exact fields, target values, URL, format, and digest."""
    issues: list[ValidationIssue] = []
    if set(item) != _ASSET_FIELDS:
        issues.append(_error(path, f"must contain exactly {sorted(_ASSET_FIELDS)}"))
    if item.get("os") not in {"ubuntu", "windows"}:
        issues.append(_error(f"{path}.os", "must be 'ubuntu' or 'windows'"))
    if item.get("backend") not in {"cpu", "cuda"}:
        issues.append(_error(f"{path}.backend", "must be 'cpu' or 'cuda'"))
    if item.get("role") not in _ASSET_ROLES:
        issues.append(_error(f"{path}.role", f"must be one of {sorted(_ASSET_ROLES)}"))
    url = item.get("url")
    parsed = urlparse(url) if isinstance(url, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        issues.append(_error(f"{path}.url", "must be an absolute HTTPS URL"))
    digest = item.get("sha256")
    if not isinstance(digest, str) or _HEX_64.fullmatch(digest) is None:
        issues.append(_error(f"{path}.sha256", "must be 64 lowercase hexadecimal characters"))
    if item.get("archive") not in {"zip", "tar.gz"}:
        issues.append(_error(f"{path}.archive", "must be 'zip' or 'tar.gz'"))
    issues.extend(_asset_path_issues(item, path))
    return issues


def _matrix_issues(assets: list[JsonObject]) -> list[ValidationIssue]:
    """Require one exact role set for every supported OS/backend pair."""
    issues: list[ValidationIssue] = []
    for pair, expected in _REQUIRED_ROLES.items():
        selected = [item for item in assets if (item.get("os"), item.get("backend")) == pair]
        roles = {item.get("role") for item in selected}
        if roles != expected or len(selected) != len(expected):
            label = f"{pair[0]}/{pair[1]}"
            issues.append(_error("$.assets", f"{label} must contain roles {sorted(expected)}"))
    return issues


def _asset_issues(lock: JsonObject) -> list[ValidationIssue]:
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
        issues.extend(_asset_value_issues(item, path))
    issues.extend(_matrix_issues(assets))
    source = next((item for item in assets if item.get("role") == "source"), None)
    if source is not None and str(lock.get("source_commit")) not in str(source.get("url")):
        issues.append(_error("$.assets", "source URL must contain the pinned source_commit"))
    return issues


def _file_issues(value: object, path: str) -> list[ValidationIssue]:
    """Validate one pinned GGUF filename, size, and digest object."""
    if not isinstance(value, dict):
        return [_error(path, "must be an object")]
    item = cast(JsonObject, value)
    issues: list[ValidationIssue] = []
    expected = {"filename", "size_bytes", "sha256"}
    if set(item) != expected:
        issues.append(_error(path, f"must contain exactly {sorted(expected)}"))
    filename = item.get("filename")
    if not isinstance(filename, str) or not filename.endswith(".gguf"):
        issues.append(_error(f"{path}.filename", "must be a GGUF filename"))
    elif "/" in filename or "\\" in filename:
        issues.append(_error(f"{path}.filename", "must not contain directory components"))
    size = item.get("size_bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        issues.append(_error(f"{path}.size_bytes", "must be a positive integer"))
    digest = item.get("sha256")
    if not isinstance(digest, str) or _HEX_64.fullmatch(digest) is None:
        issues.append(_error(f"{path}.sha256", "must be 64 lowercase hexadecimal characters"))
    return issues


def _artifact_issues(lock: JsonObject) -> list[ValidationIssue]:
    """Validate the exact default-model artifacts copied from Spike 0 evidence."""
    value = lock.get("default_model_artifact")
    if not isinstance(value, dict):
        return [_error("$.default_model_artifact", "must be an object")]
    artifact = cast(JsonObject, value)
    expected = {"repository", "revision", "filename", "size_bytes", "sha256", "mmproj"}
    issues: list[ValidationIssue] = []
    if set(artifact) != expected:
        issues.append(
            _error("$.default_model_artifact", f"must contain exactly {sorted(expected)}")
        )
    repository = artifact.get("repository")
    default_model = lock.get("default_model")
    expected_repository = default_model.split(":", 1)[0] if isinstance(default_model, str) else None
    if not isinstance(repository, str) or repository != expected_repository:
        message = "must equal the repository portion of $.default_model"
        issues.append(_error("$.default_model_artifact.repository", message))
    revision = artifact.get("revision")
    if not isinstance(revision, str) or _HEX_40.fullmatch(revision) is None:
        issues.append(_error("$.default_model_artifact.revision", "must be a 40-character commit"))
    model_file = {name: artifact.get(name) for name in ("filename", "size_bytes", "sha256")}
    issues.extend(_file_issues(model_file, "$.default_model_artifact"))
    issues.extend(_file_issues(artifact.get("mmproj"), "$.default_model_artifact.mmproj"))
    return issues


def _argument_tokens(value: object) -> Iterable[str]:
    """Yield scalar tokens from nested lock argument templates."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item
            else:
                yield from _argument_tokens(item)
    elif isinstance(value, dict):
        for item in cast(JsonObject, value).values():
            yield from _argument_tokens(item)


def _template_type_issues(value: object, path: str) -> list[ValidationIssue]:
    """Require every command-template array to contain only string tokens."""
    issues: list[ValidationIssue] = []
    if isinstance(value, list) and not all(isinstance(item, str) for item in value):
        issues.append(_error(path, "argument arrays must contain only strings"))
    if isinstance(value, dict):
        for key, item in cast(JsonObject, value).items():
            if isinstance(item, (dict, list)):
                issues.extend(_template_type_issues(item, f"{path}.{key}"))
    return issues


def _token_issues(token: str, verified: set[str]) -> list[ValidationIssue]:
    """Validate one option or placeholder token from the machine contract."""
    issues: list[ValidationIssue] = []
    if token.startswith("-") and token not in verified:
        issues.append(_error("$.verified_flags", f"does not cover emitted flag {token!r}"))
    if "{" not in token and "}" not in token:
        return issues
    match = re.fullmatch(r"\{([^{}]+)\}", token)
    if match is None:
        issues.append(_error("$.command_contract", f"malformed placeholder token {token!r}"))
    elif match.group(1) not in _ALLOWED_PLACEHOLDERS:
        issues.append(_error("$.command_contract", f"unknown placeholder {match.group(1)!r}"))
    return issues


def _probe_issues(lock: JsonObject) -> list[ValidationIssue]:
    """Require version and help probes to expose string argument arrays."""
    issues: list[ValidationIssue] = []
    for name in ("version_contract", "help_contract"):
        value = lock.get(name)
        if not isinstance(value, dict):
            issues.append(_error(f"$.{name}", "must be an object"))
            continue
        args = cast(JsonObject, value).get("args")
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            issues.append(_error(f"$.{name}.args", "must be an array of strings"))
    return issues


def _command_issues(lock: JsonObject) -> list[ValidationIssue]:
    """Reject unknown placeholders and option tokens outside verified_flags."""
    verified_value = lock.get("verified_flags")
    if not isinstance(verified_value, list) or not all(
        isinstance(item, str) for item in verified_value
    ):
        return [_error("$.verified_flags", "must be an array of strings")]
    verified = set(cast(list[str], verified_value))
    issues: list[ValidationIssue] = []
    if len(verified) != len(verified_value):
        issues.append(_error("$.verified_flags", "must not contain duplicates"))
    command = lock.get("command_contract")
    if not isinstance(command, dict):
        issues.append(_error("$.command_contract", "must be an object"))
        return issues
    issues.extend(_template_type_issues(command, "$.command_contract"))
    model_args = cast(JsonObject, command).get("model_args")
    if not isinstance(model_args, list) or "{model_path}" not in model_args:
        issues.append(_error("$.command_contract.model_args", "must contain {model_path}"))
    contracts = [lock.get("version_contract"), lock.get("help_contract"), command]
    for token in _argument_tokens(contracts):
        issues.extend(_token_issues(token, verified))
    return issues


def validate_engine_lock(lock: JsonObject) -> list[ValidationIssue]:
    """Validate engine identity, pinned artifacts, assets, and command vocabulary."""
    issues = _asset_issues(lock)
    if lock.get("schema") != "engine-lock/v1":
        issues.append(_error("$.schema", "must equal 'engine-lock/v1'"))
    for field in ("release", "default_model"):
        if not isinstance(lock.get(field), str) or not cast(str, lock[field]):
            issues.append(_error(f"$.{field}", "must be a non-empty string"))
    issues.extend(_artifact_issues(lock))
    issues.extend(_probe_issues(lock))
    issues.extend(_command_issues(lock))
    return issues
