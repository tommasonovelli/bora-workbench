# Operations and diagnostics

## Starting point

When something does not work, run in this order:

```bash
bora --version
bora validate
bora doctor
bora status
bora engine status
```

These commands quickly separate four categories: tool installation, content, machine, and
engine/process. Keep the full output and the log path reported by the CLI. Before sharing a log,
remove paths, usernames, and other private data.

Expected errors show no traceback. In general:

- exit 1: an operational problem or a failed validation;
- exit 2: an invalid command or configuration;
- exit 130: keyboard interrupt.

## Tool installation

### The installer asks for a source

That is intentional: there is no implicit default. For the local `0.2.0` candidate use the newly
built wheel and its digest as described in [Installation](installation.md). The PyPI source becomes
valid only after `bora-workbench==0.2.0` is published.

Historical `0.1.6` artifacts install `qwen-launcher`; they are not `bora-workbench` wheels despite
the repository's renamed URL.

### `uv` is not on the `PATH`

The scripts look for `uv` on the `PATH` first, then in:

- Ubuntu: `${UV_INSTALL_DIR:-$HOME/.local/bin}`;
- Windows: `%UV_INSTALL_DIR%` or `%USERPROFILE%\.local\bin`.

Open a new terminal or add that directory to the `PATH`. For the reproducible flow:

```bash
uv --version
```

must report `0.11.28`.

### PowerShell blocks the script

Run the local file downloaded from the release in a separate process:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 <options>
```

Do not change the system policy and do not execute remote text with `Invoke-Expression`.

## Configuration

### Invalid TOML or unknown key

The whole file is validated before the environment overrides. Fix the file printed by `doctor`; the
only keys are:

```text
model, model_path, llama_port, engine_path, open_browser
```

Strings such as `open_browser = "false"` are not TOML booleans. Use `open_browser = false`.

### An environment variable seems to override the file, but the command still fails

That is the intended behavior: an invalid TOML is not hidden by an override. Fix the file first,
then check the resolved value with `doctor`.

## Model

### The default model is not found

The launcher does not download it. Check that the snapshot of the pinned revision exists in the
selected Hugging Face cache and that the filename is exact. `vstudio` also requires
`mmproj-BF16.gguf`.

### Wrong size or digest

The file is incomplete or different from the pinned one. Do not rename it to bypass the check and do
not modify `engine.lock`. Restore the correct bytes from the source you chose.

### A custom model is rejected

Set both a different `model` identity and `model_path`. The default model does not accept a
substitute path. The calibrated data and the gate of the default model are not attributed to a
different GGUF.

## Memory

### Insufficient RAM at preflight

The default model requires 28 GiB total and 22 GiB available. Close workloads or use a suitable
machine. `--force` on the modes accepts only the risk of this gate; it bypasses no other check.

Calibration additionally applies a dynamic 2 GiB reserve during every trial and offers no `--force`.

### The record had enough RAM but is now ignored

Reuse requires the highest measured requirement plus 2 GiB available. Free memory and try again. On
the current branch a total-RAM variation of up to 1 MiB is tolerated; larger differences indicate a
different machine or capacity and invalidate the record.

## CUDA

### The backend is CPU despite an NVIDIA GPU

`doctor` shows why. Check:

```bash
nvidia-smi
```

The launcher falls back to CPU when the command is missing, exceeds 5 seconds, exits with an error,
or returns unparseable CSV. Fix the driver and the `PATH`; do not set `CUDA_VISIBLE_DEVICES`
globally as a workaround.

### Multiple GPUs are present

The launcher identifies one GPU deterministically but blocks CUDA startup. The multi-GPU case is not
supported by the current series; use a single-GPU host, or make the other devices invisible before
starting the launcher, taking on the external management of the environment yourself.

### Calibration is invalidated by a GPU process

Close compute workloads and graphics-intensive applications. On WDDM the initial desktop contexts
are allowed within the captured population; a new executable, an unreadable identity, or more
instances than expected still invalidate the run.

## Engine

### The engine is missing

```bash
bora engine install
bora engine status
```

The managed installation selects the detected backend. If you want to use an external executable,
`engine_path` must point at the `llama-server` of the exact release, with all verified flags.

### The engine is incompatible

An explicit executable, or one found on the `PATH`, takes precedence over the managed one. If it is
incompatible, the launcher stops instead of ignoring it. Fix or remove `engine_path` or the
candidate on the `PATH`, then re-run `engine status`.

### Ubuntu CUDA reports missing prerequisites

The pinned release has no verified Linux CUDA prebuilt, so the launcher builds from source. Install
the tools listed in the message manually and repeat the command. The launcher uses neither `sudo`
nor a package manager.

### Download or checksum failed

Check HTTPS connectivity, disk space, and proxies. Do not disable TLS or checksums. `.part` files
and staging are not activated; the previous `current.json` stays valid.

## Startup and process

### The port is busy

For `coding`, `studio`, and `vstudio`, change `llama_port` or stop the owner. If it is a managed
service:

```bash
bora status
bora stop
```

Do not delete `services.json` to free the port. Since `v0.1.1` only calibration trials can pick a
temporary port automatically; ordinary launches stay strict about the configured port.

### A second startup is refused

Only one managed service is allowed. A `start.lock` with a live owner blocks the second command; a
lock that is definitely stale is removed and acquired exactly once. Use `status` and `stop`.

### Loading times out

The total timeout is 15 minutes. Check the log for OOM, the wrong model, missing libraries, or
extreme slowness. Do not widen the timeout or change the endpoint without changing and verifying the
contract.

### Incompatible health check

READY requires exactly HTTP 200 with `{"status":"ok"}`. A different body indicates an incompatible
engine or service on the port. Check `engine_path`, the `PATH`, `engine status`, and the process
that is listening.

### The browser does not open

The UI may already be ready. Copy the URL printed by the CLI. Check `open_browser=true`; a browser
failure does not terminate the server.

### Corrupt state

`status` automatically moves the file to `services.corrupt-<timestamp>.json` and rebuilds an empty
state. Before starting a new server, verify by hand that no old `llama-server` — no longer
manageable through the corrupt file — is still running.

## Records and calibration

### The record is missing or ignored

`doctor` distinguishes candidate, absent, invalid, stale, superseded schema, and insufficient
headroom. Only an active `<mode>.json` is reusable. The normal remedy is to free memory or re-run:

```bash
bora calibrate --mode <mode>
```

Do not fix the JSON by hand and do not copy a record from another machine.

### A valid candidate exists

Promote it without new trials:

```bash
bora calibrate --mode <mode> --activate
```

Check `doctor` first. Activation atomically replaces the active record and keeps a single
`previous`.

### Every probe fails

Read the summary and the private evidence of the last run. Common causes are insufficient RAM/VRAM,
OOM, concurrent workloads, a changed driver, an incompatible API response, or memory release outside
the threshold. A run without a valid envelope must not be completed or promoted by hand.

### Calibration was interrupted

The processes are stopped; the available logs are preserved as the last private evidence. A
candidate record is written only after the mode's whole result has been built and validated.

## Uninstalling

Stop the services first. If a managed root is a symlink, a file instead of a directory, or does not
match the current preview, the command stops without removing anything. Fix the structure by hand
only after verifying the path.

The Hugging Face cache and uv are never included. With the supported `uv tool` installation, the
same confirmation also removes the command as soon as the current process exits. If the summary
reports that the Python installation is not managed by uv, use the manager it was installed with:
the launcher neither guesses nor modifies external environments.

## Reporting a problem

Include:

- the version and commit, if you use a checkout;
- the OS and backend shown by `doctor`;
- the exact command and exit code;
- the relevant output of `validate`, `doctor`, and `engine status`;
- a minimal log excerpt, reviewed for private data;
- the expected and observed behavior.

Do not attach the config, local records, full logs, tokens, hostnames, usernames, or private paths
without redaction.

**Next:** [Development and contributions](development.md)
