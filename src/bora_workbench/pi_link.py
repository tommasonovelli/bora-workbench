"""Connect the pi coding agent to the local bora service (D-081).

pi is bring-your-own-key and speaks the OpenAI completions API, so nothing about it has to be
patched: one provider entry in its user model store names the loopback endpoint, the placeholder
key the managed server ignores, and the alias the server reports as its model. That entry is the
whole integration.

Two rules shape this module. Writing into somebody else's configuration is done the way this
project writes its own state — read, merge, atomic replace, with a backup kept — and never
silently: the caller shows the change and asks first. Installing pi is delegated to npm with
`--ignore-scripts`, which is the vendor's own instruction; this project pins no digest for it and
must not pretend otherwise.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import uuid4

from bora_workbench.engine import EngineError, JsonObject
from bora_workbench.models import display_name

PROVIDER_NAME = "bora"
PACKAGE_NAME = "@earendil-works/pi-coding-agent"

# pi reaches a provider through the OpenAI completions API, which is exactly what the managed
# llama-server exposes at /v1 (docs/commands.md). The key is a placeholder: the managed server
# requires none, but pi only offers a provider whose authentication is configured.
_API_KIND = "openai-completions"
_PLACEHOLDER_KEY = "bora-local"
_MODELS_FILE = "models.json"


@dataclass(frozen=True, slots=True)
class PiInstallation:
    """Report whether pi is reachable on PATH and where its user model store lives."""

    executable: Path | None
    models_file: Path

    @property
    def is_installed(self) -> bool:
        """Return whether a pi executable was found on PATH."""
        return self.executable is not None


def agent_dir() -> Path:
    """Return pi's per-user agent directory, which it keeps under the home directory."""
    return Path.home() / ".pi" / "agent"


def inspect_pi() -> PiInstallation:
    """Locate pi without running it, so inspection stays free of side effects."""
    found = shutil.which("pi")
    executable = None if found is None else Path(found).resolve()
    return PiInstallation(executable, agent_dir() / _MODELS_FILE)


def install_command() -> tuple[str, ...]:
    """Return the vendor's installation command, with install scripts disabled."""
    return ("npm", "install", "-g", "--ignore-scripts", PACKAGE_NAME)


def provider_entry(lock: JsonObject, port: int, context_window: int) -> JsonObject:
    """Build the single provider entry that points pi at this machine's bora service.

    The model id is the alias the engine is launched with, so what pi sends is exactly what
    `/v1/models` reports (D-080).
    """
    alias = display_name(lock)
    model = {
        "id": alias,
        "name": alias,
        "input": ["text"],
        "contextWindow": context_window,
        "maxTokens": context_window,
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
    }
    return {
        "baseUrl": f"http://127.0.0.1:{port}/v1",
        "api": _API_KIND,
        "apiKey": _PLACEHOLDER_KEY,
        "models": [model],
    }


def read_document(path: Path) -> JsonObject:
    """Read pi's model store, treating an absent file as an empty one.

    Anything present but unreadable is an error rather than something to overwrite: replacing a
    file this tool cannot parse would destroy configuration that belongs to the user.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise EngineError(f"cannot read {path}: {error}") from error
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as error:
        raise EngineError(f"{path} is not valid JSON; fix or move it first: {error}") from error
    if not isinstance(decoded, dict):
        raise EngineError(f"{path} does not contain a JSON object; fix or move it first")
    return cast(JsonObject, decoded)


def merged_document(document: JsonObject, entry: JsonObject) -> JsonObject:
    """Return the document with only the bora provider replaced, leaving every other one intact."""
    providers = document.get("providers")
    merged = dict(providers) if isinstance(providers, dict) else {}
    merged[PROVIDER_NAME] = entry
    updated = dict(document)
    updated["providers"] = merged
    return updated


def current_entry(document: JsonObject) -> JsonObject | None:
    """Return the bora provider already configured, if any, so a caller can show the change."""
    providers = document.get("providers")
    if not isinstance(providers, dict):
        return None
    existing = providers.get(PROVIDER_NAME)
    return cast(JsonObject, existing) if isinstance(existing, dict) else None


def render(document: JsonObject) -> str:
    """Serialize one document the way it is written to disk, for printing and for writing."""
    return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def write_document(path: Path, document: JsonObject) -> None:
    """Replace pi's model store atomically, keeping the previous content beside it as a backup."""
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        with temporary.open("x", encoding="utf-8", newline="\n") as output:
            output.write(render(document))
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise EngineError(f"cannot write {path}: {error}") from error
