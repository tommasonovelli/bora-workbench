"""Validate the machine lock before runtime code expands its command templates."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import cast

from bora_workbench.validation import ValidationIssue

JsonObject = dict[str, object]
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


def _error(path: str, message: str) -> ValidationIssue:
    """Create one engine.lock validation error."""
    return ValidationIssue("error", "engine.lock", path, message)


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
    from bora_workbench._validation_assets import validate_assets

    issues: list[ValidationIssue] = validate_assets(lock)
    if lock.get("schema") != "engine-lock/v1":
        issues.append(_error("$.schema", "must equal 'engine-lock/v1'"))
    for field in ("release", "default_model"):
        if not isinstance(lock.get(field), str) or not cast(str, lock[field]):
            issues.append(_error(f"$.{field}", "must be a non-empty string"))
    issues.extend(_artifact_issues(lock))
    issues.extend(_probe_issues(lock))
    issues.extend(_command_issues(lock))
    return issues
