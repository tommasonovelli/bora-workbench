# bora-workbench

[![CI](https://github.com/tommasonovelli/bora-workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/tommasonovelli/bora-workbench/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/tommasonovelli/bora-workbench.svg)](https://github.com/tommasonovelli/bora-workbench/releases/tag/v0.3.2)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-31213/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**One Qwen setup, three local experiences.**

| Command | What you get |
|---|---|
| `bora tui` | an optional read-only dashboard and exact composer for the same CLI commands |
| `bora coding` | a local OpenAI-compatible API for editors, scripts, and agents |
| `bora studio` | browser-based local chat in the built-in `llama.cpp` UI |
| `bora vstudio` | the same UI with the pinned vision projector, for multimodal chat |

`bora-workbench` is a ready-to-use local Qwen environment. It installs the verified `llama.cpp`
engine for the hardware it detects, resolves and checks the model, and manages the complete service
lifecycle: start, health check, status, logs, and an identity-safe stop. Services listen on
`127.0.0.1` only.

`bora engine install` acquires both halves of the setup: the engine, and the pinned weights it was
verified against. Everything else — flags, checksums, ports, and process lifetime — is already
decided, pinned, and verified.

## Why it exists

Running a large MoE model locally normally means rebuilding the same decisions by hand every time:
which engine build matches the GPU, which flags the model card actually requires, whether the files
on disk are the ones those flags were tested against, which port is free, and what is still running
an hour later. This launcher turns that into one decision, made once:

- the `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M` model, pinned to one revision and digest;
- `llama.cpp b10011` at its verified commit, installed for the detected backend;
- three modes whose flags and sampling come from validated declarative content;
- status, logs, health checks, and a stop that verifies process identity before killing anything.

It is a finished, opinionated setup rather than a fitting algorithm. It does not survey the model
landscape to suggest what you should run, and it does not stop at making memory fit: it gives you
three defined ways to use one combination that is known to work, and then offers to tune that
combination for your machine.

It acquires and releases that one pinned model, and nothing else: it is not a generic model
manager, not a registry, and it runs no plugins.

## Start here

If this is your first time opening the project, the simplest path is:

1. check the [requirements](#requirements);
2. [install the release](#installation);
3. optionally open `bora tui` to inspect the machine and see the truthful next step;
4. run `bora engine install`, which installs the engine and downloads the [model](#model);
5. start `coding`, `studio`, or `vstudio`;
6. once that works, [calibrate the machine](#calibration-is-the-second-step-not-the-entry-price);
7. use the [full documentation](docs/README.md) when you want configuration and details.

## Project status

> [!WARNING]
> The `0.3` series is **not stable** and is intended for evaluation, exactly like `0.1` and `0.2`.
> The CLI, configuration, record formats, procedures, and performance carry no stability guarantee.
> Do not use it for critical workloads without independent verification and backups of your local
> data.

Version **`0.3.2`** is distributed exclusively through GitHub Releases. Its distribution is
`bora-workbench` and its command is `bora`. An installation of the previous `qwen-launcher` series
is replaced rather than upgraded: its configuration, data, cache, and state directories are not
read by `bora`.

Calibration uses one working protocol. The removed protocol switch and record formats are not
supported, and a record written by the previous launcher is diagnosed as superseded. Re-run
`calibrate` after installing instead of copying or converting an old record.

## Requirements

- Ubuntu 22.04+ x86-64 or Windows 11 x86-64;
- CPU, or a single NVIDIA CUDA GPU;
- at least **28 GiB total RAM** and **22 GiB available** for the default model;
- room for the GGUF (22,663,387,424 bytes), the mmproj (902,822,528 bytes), the engine, and logs;
- HTTPS connectivity to install the tool, the engine, and the model, unless they are already
  available locally.

CUDA on multi-GPU hosts is blocked because isolation has only been verified on single-GPU hosts.
If `nvidia-smi` is unavailable or unreliable, the launcher falls back to CPU and prints a warning.

## Installation

Install the exact `v0.3.2` wheel from the GitHub Release. The commands below download the release
manifest, verify the installer and wheel against it, and install the tool with pinned uv `0.11.28`
and CPython `3.12.13`. You do not need to install uv or Python first, and no administrator
privileges are used.

### Ubuntu

Open a terminal in a new directory, copy the entire block, and press Enter:

```bash
version="0.3.2"
base="https://github.com/tommasonovelli/bora-workbench/releases/download/v${version}"
wheel="bora_workbench-${version}-py3-none-any.whl"

curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/install.sh" --output install.sh
curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/$wheel" --output "$wheel"
curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/SHA256SUMS" --output SHA256SUMS
installer_sha256="$(awk '$2 == "install.sh" { print $1 }' SHA256SUMS)"
wheel_sha256="$(awk -v wheel="$wheel" '$2 == wheel { print $1 }' SHA256SUMS)"
test "${#installer_sha256}" -eq 64
test "${#wheel_sha256}" -eq 64
printf '%s  %s\n' "$installer_sha256" install.sh | sha256sum --check -
printf '%s  %s\n' "$wheel_sha256" "$wheel" | sha256sum --check -
sh ./install.sh --wheel "./$wheel" --sha256 "$wheel_sha256"
```

### Windows

Open PowerShell in a new directory, copy the entire block, and press Enter:

```powershell
$Version = "0.3.2"
$Base = "https://github.com/tommasonovelli/bora-workbench/releases/download/v$Version"
$Wheel = "bora_workbench-$Version-py3-none-any.whl"

Invoke-WebRequest -Uri "$Base/install.ps1" -OutFile install.ps1
Invoke-WebRequest -Uri "$Base/$Wheel" -OutFile $Wheel
Invoke-WebRequest -Uri "$Base/SHA256SUMS" -OutFile SHA256SUMS

$Expected = @{}
Get-Content .\SHA256SUMS | ForEach-Object {
    if ($_ -match '^([0-9a-f]{64})\s+(.+)$') {
        $Expected[$Matches[2]] = $Matches[1]
    }
}
foreach ($File in @("install.ps1", $Wheel)) {
    if (-not $Expected.ContainsKey($File)) {
        throw "$File is missing from SHA256SUMS"
    }
    $Actual = (Get-FileHash ".\$File" -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected[$File]) {
        throw "$File SHA-256 mismatch"
    }
}
$WheelSha256 = $Expected[$Wheel]
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Wheel ".\$Wheel" -Sha256 $WheelSha256
```

`ExecutionPolicy Bypass` applies only to that PowerShell process; it does not change the system
policy. The downloaded files can be deleted after installation.

### Verify the installation

Open a new terminal or PowerShell window, then run:

```bash
bora --version
bora validate
bora doctor
```

If `bora` is not found, close and reopen the shell once so it reloads the user PATH. See
[Installation and first run](docs/installation.md) for requirements, engine setup, model placement,
and removal.

### Optional terminal dashboard

```bash
bora tui
bora tui --plain
```

The TUI shows seven read-only screens, deterministic next-step advice, and exact current commands.
Opening and `r` refreshes may run bounded local hardware and engine probes, but perform no mutation,
model hashing, or network request. Selecting an action closes and restores the TUI before the
existing CLI callback owns normal terminal I/O, prompts, and exit codes. The complete CLI remains
the accessible and scriptable path; see [Terminal workbench](docs/tui.md) for keys, motion controls,
and handoff details.

### Updating

```bash
bora update --check   # report only
bora update           # verify and install the newest published release
```

`update` installs only a strictly newer GitHub Release, verifies the wheel's SHA-256 against that
release's `SHA256SUMS`, and installs it with uv. **The managed engine is not reinstalled**: it lives
under the data root and survives the update, and the command tells you whether the new version pins
a different `llama.cpp` release and therefore needs `bora engine install` afterwards. Configuration
and calibration records are untouched.

## Model

The weights are not bundled. `bora engine install` downloads them, and `bora pull` does it on its
own:

```bash
bora pull            # download and verify the pinned artifacts
bora rm              # delete them and free the disk
bora rm --dry-run    # list what would be deleted, and delete nothing
```

Both artifacts come from revision `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`, over HTTPS, and are
accepted only if their name, size, and SHA-256 match `engine.lock`:

```text
Qwen3.6-35B-A3B-UD-Q4_K_M.gguf   21.1 GiB
mmproj-BF16.gguf                  0.8 GiB, only needed by vstudio
```

They land in the managed store under the data root. A copy already sitting in the Hugging Face
cache — from an earlier version of this tool, or from any other tool — is still used and is never
downloaded twice: the store is only searched first. Nothing is ever written into that cache.

The name and size are checked every launch. The SHA-256 is recomputed only when a file is new or
has changed, because a receipt kept under the cache root records the last successful verification;
`pull` writes that receipt itself, so the first launch after a download starts immediately.

`rm` deletes the store copies after one confirmation, then asks a **second, separate** question
about copies in the Hugging Face cache, because that cache is shared with everything else on the
machine. `uninstall` behaves the same way. Cache deletion never reaches outside the pinned snapshot
of the locked repository, and `--keep-hf` skips it entirely.

## First run

One command installs the engine for the detected hardware and downloads the model:

```bash
bora engine install          # engine + weights
bora engine install --no-model   # engine only
bora engine status
```

Then pick an experience and start it:

```bash
bora coding
```

After READY the CLI shows the API/UI URLs and the log path. All three modes serve the API at
`http://127.0.0.1:<llama_port>/v1`; `coding` keeps UI and vision disabled, while `studio` and
`vstudio` also serve the built-in UI and open the browser only when `open_browser=true`. The process
stays in the foreground, and `Ctrl-C` stops it and cleans up the state.

Control it from another terminal:

```bash
bora status
bora stop
```

### Use it from a coding agent

With `bora coding` running, the API is a plain OpenAI-compatible endpoint at
`http://127.0.0.1:<llama_port>/v1`, and it reports the model as **Qwen 3.6**. For the
[pi](https://pi.dev/) terminal agent there is one command that wires it up:

```bash
bora pi            # write a provider named "bora" into pi's models.json
bora pi --print    # print that entry instead, and change nothing
bora pi --install  # install pi with npm first, when it is missing
bora pi remove     # delete that provider entry again
bora pi uninstall  # remove pi itself, then ask about the entry separately
```

It shows the entry, asks once, keeps a backup, and leaves every other provider alone. Afterwards:

```bash
pi --provider bora --model "Qwen 3.6"
```

The context window it hands over is the one this machine actually serves — a running service is
asked first, then the active `coding` calibration record, then the verified baseline — and the
command says which of the three answered. Run it again after calibrating: the entry is a copy, and
nothing rewrites it on its own.

The full command surface, options, and exit codes are in [Commands](docs/commands.md).

## Calibration is the second step, not the entry price

The launcher is useful before you ever calibrate. All three modes start on the verified baseline —
`ctx=8192`, and on CUDA `n_cpu_moe=48` — and the CLI states plainly that it is not optimized.

Calibration is what you run once the setup already works, to fit it to *this* machine:

```bash
bora calibrate --mode all
```

It measures `coding`, `studio`, and `vstudio`, finds how much context the hardware can actually
serve, and compares feasible configurations using the requested optimization rule. Each mode gets
one private calibrated cell. This applies `max-context` to all three:

```bash
bora calibrate --mode all --preference max-context
```

Run modes separately when they should retain different choices, for example `coding` with `fast`,
`studio` with `balanced`, and `vstudio` with `max-context`. Recalibrating one mode replaces only
that mode's cell.

It does not change the model or the quality of the answers: it changes how much context you can
hold, how the work is split between CPU and GPU, and the throughput you get from that split.

Calibration can run for a long time and starts many temporary processes; it always shows a preflight
and asks for confirmation. `max-context` is the quickest of the three, because it stops at the first
context the hardware can serve. Read [Local calibration](docs/calibration.md) before running it.

## Concepts in one minute

- **Engine**: the `llama-server` executable from the pinned release.
- **Mode**: the service behavior (UI, vision, and sampling).
- **Baseline**: the verified configuration used when no local calibration exists.
- **Local record**: the private result of calibrating this machine, for one mode only.
- **Calibrated cell**: the one measured preference and set of launch parameters stored for a mode.

The launcher reuses a record only when the machine, model, engine, mode, and current memory are still
compatible. Otherwise it explains why and falls back to the baseline.

## Minimal configuration

The file is `config_dir()/config.toml`; precedence is environment > TOML > defaults.

```toml
llama_port = 8080
open_browser = true
```

The available keys are `model`, `model_path`, `llama_port`, `engine_path`, and `open_browser`.
Unknown keys and malformed values are errors; the launcher never rewrites the file.

See [Configuration and local data](docs/configuration.md) for Linux/Windows paths, environment
variables, and the record layout.

## Security and privacy

- exclusive bind to `127.0.0.1`;
- HTTPS and SHA-256 mandatory for assets;
- confined extraction and atomic engine activation;
- no `shell=True`, `sudo`, or automatic elevation;
- stop based on `pid + create_time`, not on the PID alone;
- `CUDA_VISIBLE_DEVICES` set in the child environment only;
- config, records, and logs are never uploaded automatically;
- nothing is ever written into the Hugging Face cache, and deleting from it needs its own explicit
  confirmation and never reaches outside the pinned snapshot of the locked repository.

## Documentation

The [full documentation](docs/README.md) follows a path for readers starting from scratch:
installation → commands → configuration → architecture → calibration → operations → development →
releasing. The [terminal workbench](docs/tui.md) is an optional guide beside that complete CLI path.

Work that is not implemented yet lives only in [IMPLEMENTATION_SPEC.md](IMPLEMENTATION_SPEC.md).
The measured evidence behind the locks and reports is kept separately in
[`evidence/`](evidence/README.md).

## Development

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
```

For packaging or resources:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [Development and contributions](docs/development.md)
before changing the repository.

## Licenses

The launcher is distributed under the [MIT](LICENSE) license. Managed installations keep the
`llama.cpp` MIT license and, for Windows CUDA, the NVIDIA CUDA Toolkit EULA. The model and mmproj
are not redistributed and remain subject to the model license.
