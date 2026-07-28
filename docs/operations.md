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

That is intentional: there is no implicit default. For `0.3.2`, use the wheel from the GitHub
Release and its manifest digest as described in [Installation](installation.md). A full commit hash
is also accepted for testing an exact repository revision.

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

### `bora update` refuses to run

Three refusals are deliberate and each names its fix. A live managed service must be stopped with
`bora stop` first, because the running launcher holds the environment uv has to replace. An
installation that `uv tool` does not own — a development checkout, or a wheel installed by hand —
is left alone; use the installer commands in [Installation](installation.md). A checksum mismatch
between the downloaded wheel and the release `SHA256SUMS` aborts before anything is installed;
retry, and if it persists, report it rather than installing that wheel manually.

### `bora update` reported success but the version did not change

Exit code 0 means the installation was *scheduled*. Windows cannot replace the environment of the
process that is still running, so uv is invoked by a helper once the command exits, and it prints
its own outcome on the same terminal a moment later. If that output shows a uv failure, run the
command it names yourself; the previous installation is still in place until uv succeeds. Check
with `bora --version` in a new shell.

### Windows blocks `bora.exe` after an install or an update

```text
'...\.local\bin\bora.exe' was blocked by your organization's Device Guard policy.
```

**This is Windows refusing the launcher shim, not a problem with the tool.** The Python environment
is installed correctly, the managed engine runs, and every command works — through a longer form.

#### Confirming the diagnosis

```powershell
# 1. Is Smart App Control enforced? 1 = yes, 2 = evaluation, 0 = off
Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy" |
  Select-Object VerifiedAndReputablePolicyState

# 2. What exactly was refused, and when?
Get-WinEvent -LogName "Microsoft-Windows-CodeIntegrity/Operational" |
  Where-Object { $_.Message -match "bora" } |
  Select-Object TimeCreated, Id, Message -First 5
```

Events `3033` and `3077` name the refused file. The message says *"did not meet the Enterprise
signing level requirements"*, which reads like a corporate policy but is the wording Smart App
Control uses on a personal machine too.

#### What it is not

It is tempting to blame the missing signature, and wrong. The shim is unsigned, but so are
`uv.exe`, the managed `python.exe`, and `llama-server.exe` — none of which is ever refused, which is
why the managed engine keeps working. `Get-AuthenticodeSignature` on any of them reports
`NotSigned`.

It is not the version either. Authenticode is applied at build time or not at all: it does not
expire when a newer release appears, and no version of this tool is signed.

Nor is it that the file is new to the world. Every uv shim is unique: uv builds it by appending the
target interpreter path to a trampoline, so two installations at different paths produce different
bytes — the path is readable inside the executable. Unknown-to-everyone files of exactly this shape
are nevertheless admitted routinely.

#### What it is

A per-file verdict from Microsoft's cloud reputation service, which the machine records but does not
explain. Nothing observable locally predicts it, and it is **not stable over time**. What was
measured on the machine where this was diagnosed:

- the shim ran normally for days;
- an ordinary reinstall rewrote it, and the first refusal was logged **seven seconds later**;
- refusals continued for about an hour, covering both the shim on the `PATH` and the one inside the
  tool environment;
- no local policy changed that day — the newest `.cip` under
  `C:\Windows\System32\CodeIntegrity\CiPolicies\Active` was two weeks old;
- a shim built **after** that hour ran without complaint, including from the very directory where
  the refused one had lived;
- the predecessor `qwen-launcher.exe` had been refused the same way on two earlier, isolated dates.

So a refusal does not mean the installation is broken, and it does not mean the next one will be
refused too. Reinstalling is a reasonable thing to try, and so is simply trying again later.

Note that the log records refusals only. An absence of events for a period is evidence the file was
**not** being blocked then, not evidence it never ran.

#### What to do

While it lasts, use the module entry point. It is the same program — the wheel declares
`bora = bora_workbench.cli:app`, and `python -m bora_workbench.cli` calls that same `app()`:

```powershell
& "$env:APPDATA\uv\tools\bora-workbench\Scripts\python.exe" -m bora_workbench.cli doctor
```

Define a shorthand for the session if you use it often:

```powershell
function bora { & "$env:APPDATA\uv\tools\bora-workbench\Scripts\python.exe" -m bora_workbench.cli @args }
```

A PowerShell function is not a file, so Smart App Control has nothing to judge, and PowerShell
resolves functions before executables on the `PATH`: typing `bora` never reaches the refused file.
Put it in your profile to keep it. A `bora.cmd` beside the shim would **not** work, because `.EXE`
precedes `.CMD` in `PATHEXT`.

Turning Smart App Control off does restore the short command, but it is **not reversible without
reinstalling Windows**. Given that the refusal has been observed to clear on its own, that is a
disproportionate response: it is a security decision about the whole machine, not a workaround for
one tool, and this project neither changes nor recommends it.

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

Run `bora pull`. Resolution looks in the managed store at `<data root>/models` first and then in
the pinned snapshot of the selected Hugging Face cache, so this means neither holds a file with the
exact locked name. `vstudio` also requires `mmproj-BF16.gguf`.

### `pull` says the model is already present, but the disk did not fill up

It found a complete, verified copy and did not fetch it again. Run `bora rm --dry-run` to see where
it is: a copy already in the Hugging Face cache — from an earlier version of this tool, or from
another tool entirely — is used where it lies and is never duplicated into the store.

### The same 21.9 GiB appears twice

That is what a `pull` on a machine that already had the weights in its cache produces: the store
copy is downloaded, the cache copy stays where it was, and both are valid. `bora rm --dry-run`
lists them as two groups.

To keep the store copy and free the other, run `bora rm` and answer **no** to the first question and
**yes** to the second. There is no `--keep-store` flag because the two questions already are the
choice. `--keep-hf` does the opposite: it empties the store and never mentions the cache.

### `rm` reported freed space but the disk did not change

The copy it deleted was not the only one. `rm` reports each group separately, and each figure is
what *that* group frees; declining the second question leaves the second figure on the disk. Run
`bora rm --dry-run` to see both groups before deciding.

### Wrong size or digest

The file is incomplete or different from the pinned one. Do not rename it to bypass the check and do
not modify `engine.lock`. Restore the correct bytes with `bora pull`, which replaces a file whose
digest does not match.

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

This can only happen where the card is exclusive — Linux, or a Windows card in TCC mode — and there
any foreign compute context invalidates the run: close compute workloads and graphics-intensive
applications before calibrating.

On WDDM it does not happen. The desktop itself owns compute contexts and recreates them constantly,
so they are counted as evidence and the aggregate reserve and release checks decide feasibility
instead. Closing heavy applications still gives cleaner timings and more usable VRAM.

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

### pi shows a smaller context than the record

`bora pi` prints where the window came from before it writes anything:

```text
Context window: 65536 tokens, from the running coding service on port 8080
Context window: 8192 tokens, from the verified non-optimized baseline
```

A baseline line is followed by a warning that names the reason — no record, a superseded one, a
changed identity, or too little free memory right now. Re-run `bora pi` after calibrating: the entry
in `models.json` is a copy, and nothing rewrites it when a new record is activated.

A number that is right in the launcher but wrong in pi is almost always an entry written before the
record existed. `bora pi` overwrites it, showing the old and the new entry first.

### Every probe fails

Read the summary and the private evidence of the last run. Common causes are insufficient RAM/VRAM,
OOM, concurrent workloads, a changed driver, an incompatible API response, or memory release outside
the threshold. A run without a valid envelope must not be completed or promoted by hand.

### Calibration was interrupted

The processes are stopped; the available logs are preserved as the last private evidence. A
candidate record is written only after the mode's whole result has been built and validated.

If the launcher itself was killed rather than interrupted, its trial server can survive and keep
holding VRAM. `bora status` lists it and `bora stop` ends it; both cover the trial roots of an
unfinished run, so no manual process hunting is needed.

## Uninstalling

Stop the services first. If a managed root is a symlink, a file instead of a directory, or does not
match the current preview, the command stops without removing anything. Fix the structure by hand
only after verifying the path.

uv is never included. The managed roots take the model store with them; weights that also exist in
the Hugging Face cache are a separate question asked afterwards, which defaults to no. With the
supported `uv tool` installation, the same confirmation also removes the command as soon as the
current process exits. If the summary
reports that the Python installation is not managed by uv, use the manager it was installed with:
the launcher neither guesses nor modifies external environments.

The provider entry that `bora pi` writes lives in pi's own `~/.pi/agent/models.json`, which is not a
managed root, so an uninstall leaves it in place. Remove it before or after, as its own step:

```bash
bora pi remove       # the entry only
bora pi uninstall    # pi itself, then the entry as a separate question
```

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
