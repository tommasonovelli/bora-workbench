"""Install, describe, and launch the managed Open WebUI interface.

Open WebUI is an upstream program this launcher starts; it is not part of the distribution and it
is never modified. Everything bora configures travels through the child process environment, and
bora holds no credential into it and never calls its API: the model picker already names the model
because `engine.lock` makes `/v1/models` report the alias of D-080, so nothing has to be written
into another program's database (D-095).

The environment below was read at upstream tag `v0.11.0`. Two of its defaults are wrong here and
are overridden by argument rather than by configuration: `serve` binds `0.0.0.0`, which
specification section 5.12 forbids, and it listens on `8080`, which is `llama_port`.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from bora_workbench.paths import state_dir, venv_executable, webui_dir
from bora_workbench.process import ReadinessContract

OPEN_WEBUI_VERSION = "0.11.0"
OPEN_WEBUI_REQUIREMENT = f"open-webui=={OPEN_WEBUI_VERSION}"

# `serve --host` is the only place the bind address is decided, and it is a constant here so no
# configuration key can ever widen it (specification section 5.12, D-015).
LOOPBACK_HOST = "127.0.0.1"

# `GET /health` answers 200 unconditionally, before startup finishes; `GET /ready` answers 200 only
# once startup completed and the database responded, and 503 until then. Polling the first would
# report an interface as ready while it is still migrating its database (D-095).
READY_PATH = "/ready"
_READY_BODY: dict[str, object] = {"status": True}
_STARTUP_TIMEOUT_SECONDS = 10 * 60.0

_PYTHON_VERSION = "3.12"
_MARKER_NAME = "installed.json"
_SECRET_KEY_NAME = "open-webui.secret"


class WebuiError(RuntimeError):
    """Report an actionable failure to install, inspect, or configure the managed interface."""


@dataclass(frozen=True, slots=True)
class WebuiStatus:
    """Describe the managed interface installation without starting or repairing anything."""

    root: Path
    version: str | None
    executable: Path | None

    @property
    def is_installed(self) -> bool:
        """Report whether the pinned version is present and its console script is executable."""
        return self.version == OPEN_WEBUI_VERSION and self.executable is not None


@dataclass(frozen=True, slots=True)
class WebuiLaunch:
    """Group everything one managed interface process needs, resolved and validated."""

    executable: Path
    port: int
    llama_port: int
    data_dir: Path
    secret_key: str


def environment_dir(root: Path) -> Path:
    """Return the managed virtual environment holding the pinned Open WebUI."""
    return root / "venv"


def interface_data_dir(root: Path) -> Path:
    """Return the directory Open WebUI owns: its database, uploads, and vector store."""
    return root / "data"


def _marker_path(root: Path) -> Path:
    """Return the file recording which version the managed environment actually holds."""
    return environment_dir(root) / _MARKER_NAME


def _installed_version(root: Path) -> str | None:
    """Read the recorded version, treating an absent or unreadable marker as not installed.

    The marker is written last, so an interrupted installation leaves no version behind and the
    next `bora webui install` rebuilds the environment instead of trusting a partial one.
    """
    try:
        recorded = json.loads(_marker_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = recorded.get("version") if isinstance(recorded, dict) else None
    return version if isinstance(version, str) else None


def inspect_webui(root: Path | None = None) -> WebuiStatus:
    """Describe the managed installation without creating directories or starting a process."""
    selected = webui_dir() if root is None else root
    executable = venv_executable(environment_dir(selected), "open-webui")
    present = executable if executable.is_file() else None
    return WebuiStatus(selected, _installed_version(selected), present)


def _require_uv() -> str:
    """Locate the installer this project already defers to for every managed environment."""
    located = shutil.which("uv")
    if located is None:
        raise WebuiError(
            "uv is required to install Open WebUI; install it from https://docs.astral.sh/uv/ "
            "and run `bora webui install` again"
        )
    return located


def _run(command: list[str], description: str) -> None:
    """Run one installer step without a shell, leaving its own progress visible to the user.

    The output is not captured, because an installation this large is worth watching: uv prints
    which wheel it is resolving and downloading, and a captured stream would show nothing until
    the whole step finished.
    """
    try:
        result = subprocess.run(command, check=False)
    except OSError as error:
        raise WebuiError(f"cannot {description}: {error}") from error
    if result.returncode != 0:
        raise WebuiError(f"could not {description}: uv exited with code {result.returncode}")


def _write_marker(root: Path) -> None:
    """Record the installed version only once the console script is present and executable."""
    payload = {"version": OPEN_WEBUI_VERSION, "python": _PYTHON_VERSION}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    try:
        _marker_path(root).write_text(text, encoding="utf-8")
    except OSError as error:
        raise WebuiError(f"cannot record the Open WebUI installation: {error}") from error


def install_webui(root: Path | None = None, *, force: bool = False) -> WebuiStatus:
    """Create the managed environment and install exactly the pinned Open WebUI release.

    The version is pinned here rather than resolved, so two machines running the same bora install
    the same interface; `latest` is forbidden by specification section 2.
    """
    selected = webui_dir() if root is None else root
    current = inspect_webui(selected)
    if current.is_installed and not force:
        return current
    uv = _require_uv()
    environment = environment_dir(selected)
    _marker_path(selected).unlink(missing_ok=True)
    selected.mkdir(parents=True, exist_ok=True)
    _run(
        [uv, "venv", "--python", _PYTHON_VERSION, str(environment)],
        "create the Open WebUI environment",
    )
    python = venv_executable(environment, "python")
    _run(
        [uv, "pip", "install", "--python", str(python), OPEN_WEBUI_REQUIREMENT],
        f"install {OPEN_WEBUI_REQUIREMENT}",
    )
    if not venv_executable(environment, "open-webui").is_file():
        raise WebuiError("the Open WebUI installation produced no `open-webui` console script")
    _write_marker(selected)
    return inspect_webui(selected)


def directory_size(path: Path) -> int:
    """Sum the bytes of one managed directory, so a removal can report what it frees.

    Entries that vanish or cannot be read while walking are skipped rather than failing the
    report: the number exists to inform a decision, not to be an audit.
    """
    if not path.is_dir():
        return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _remove_confined(path: Path, root: Path) -> bool:
    """Delete one directory proven to sit inside the managed root, and report whether it existed.

    A symlink is refused rather than followed, so removal can never escape the managed tree
    (specification sections 5.10 and 5.12).
    """
    absolute, managed = path.absolute(), root.absolute()
    if absolute.parent != managed:
        raise WebuiError(f"refusing to remove a path outside the managed root: {absolute}")
    if path.is_symlink():
        raise WebuiError(f"refusing to remove a symlinked managed path: {absolute}")
    if not path.exists():
        return False
    try:
        shutil.rmtree(path)
    except OSError as error:
        raise WebuiError(f"cannot remove {absolute}: {error}") from error
    return True


def remove_environment(root: Path | None = None) -> bool:
    """Delete the managed Open WebUI environment, leaving the interface's own data untouched.

    The two are separated because they are different kinds of thing: the environment is bytes bora
    installed and can reinstall, while the data directory is the user's chats and uploads.
    """
    selected = webui_dir() if root is None else root
    return _remove_confined(environment_dir(selected), selected)


def remove_interface_data(root: Path | None = None) -> bool:
    """Delete the interface's database, uploads, and vector store, which are user content."""
    selected = webui_dir() if root is None else root
    return _remove_confined(interface_data_dir(selected), selected)


def secret_key_path(state_root: Path | None = None) -> Path:
    """Return the file holding the session-signing key, without creating it."""
    return (state_dir() if state_root is None else state_root) / _SECRET_KEY_NAME


def _create_secret_key(path: Path) -> str:
    """Create the key exclusively, readable only by its owner, and return it."""
    key = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, (key + "\n").encode("ascii"))
    finally:
        os.close(descriptor)
    return key


def resolve_secret_key(state_root: Path | None = None) -> str:
    """Return the stable session key, generating it once on first use.

    Upstream would otherwise generate this itself into `.webui_secret_key` in the current working
    directory, which for a launcher is wherever the user's shell happened to be. It also signs the
    session cookie, so a key that moves between runs logs the browser out on every launch. It is
    the first secret this project keeps: owner-only permissions, and printed nowhere.
    """
    path = secret_key_path(state_root)
    try:
        return _read_secret_key(path)
    except FileNotFoundError:
        pass
    try:
        return _create_secret_key(path)
    except FileExistsError:
        return _read_secret_key(path)
    except OSError as error:
        raise WebuiError(f"cannot create the Open WebUI session key {path}: {error}") from error


def _read_secret_key(path: Path) -> str:
    """Read an existing key, refusing an empty file rather than starting without a session key."""
    try:
        existing = path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as error:
        raise WebuiError(f"cannot read the Open WebUI session key {path}: {error}") from error
    if not existing:
        raise WebuiError(f"the Open WebUI session key {path} is empty; delete it and launch again")
    return existing


def serve_command(launch: WebuiLaunch) -> tuple[str, ...]:
    """Build the launch command, passing the two arguments whose upstream defaults are wrong."""
    return (
        str(launch.executable),
        "serve",
        "--host",
        LOOPBACK_HOST,
        "--port",
        str(launch.port),
    )


def readiness_contract(port: int) -> ReadinessContract:
    """Describe how the interface reports readiness, and how long a first start may take.

    A first start creates the database, applies every migration, and builds the frontend caches,
    which is slower than any later one; 503 is the endpoint's own "not yet" and is retried.
    """
    return ReadinessContract(
        f"http://{LOOPBACK_HOST}:{port}{READY_PATH}",
        200,
        _READY_BODY,
        (503,),
        _STARTUP_TIMEOUT_SECONDS,
        "Open WebUI",
    )


def _managed_settings(launch: WebuiLaunch) -> dict[str, str]:
    """Return every value bora decides for the interface, with the reason it decides it."""
    return {
        # The database, uploads and vector store stay inside a managed root, so `uninstall` reaches
        # them (specification section 5.10).
        "DATA_DIR": str(launch.data_dir),
        "WEBUI_SECRET_KEY": launch.secret_key,
        "WEBUI_URL": f"http://{LOOPBACK_HOST}:{launch.port}",
        # Upstream creates its own local administrator on the first page load. The inference
        # endpoint beside it has no authentication either, and both are loopback-only.
        "WEBUI_AUTH": "false",
        # The environment seeds the first boot; from the second boot the user owns their settings.
        "ENABLE_PERSISTENT_CONFIG": "true",
        # Nothing serves Ollama here, and the one connection is the managed llama-server.
        "ENABLE_OLLAMA_API": "false",
        "ENABLE_OPENAI_API": "true",
        "OPENAI_API_BASE_URL": f"http://{LOOPBACK_HOST}:{launch.llama_port}/v1",
        # llama-server ignores the key and the field is required, as in D-081.
        "OPENAI_API_KEY": "bora-local",
        # An empty engine with a named model builds a SentenceTransformer at every start and
        # downloads it on the first. A distribution whose weights are an explicit, checksummed
        # command does not fetch a model nobody asked for; retrieval is the user's to configure.
        "RAG_EMBEDDING_ENGINE": "openai",
        "RAG_EMBEDDING_MODEL": "",
        # A local distribution does not phone home.
        "ENABLE_VERSION_UPDATE_CHECK": "false",
        # Upstream otherwise runs `pip install` at every startup for the requirements a stored Tool
        # or Function declares, mutating this environment unpinned, and then runs that third-party
        # Python inside the process bora started. Both switches are set, so neither can happen.
        "ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS": "false",
        "SAFE_MODE": "true",
        # Three extra completions per turn on the one calibrated slot, serialized behind the same
        # stream the user is waiting on.
        "ENABLE_TITLE_GENERATION": "false",
        "ENABLE_TAGS_GENERATION": "false",
        "ENABLE_FOLLOW_UP_GENERATION": "false",
    }


def launch_environment(launch: WebuiLaunch) -> dict[str, str]:
    """Assemble the whole child environment in one place, so `doctor` can show all of it.

    `WEBUI_NAME` is never set, and an inherited one is removed: upstream rewrites any other value
    to `"<name> (Open WebUI)"`, and leaving the interface named `Open WebUI` everywhere means the
    branding clause of its licence is never engaged and no user-count exemption is invoked.
    """
    environment = dict(os.environ)
    environment.pop("WEBUI_NAME", None)
    environment.update(_managed_settings(launch))
    return environment
