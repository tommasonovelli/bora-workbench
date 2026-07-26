# bora-workbench

[![CI](https://github.com/tommasonovelli/bora-workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/tommasonovelli/bora-workbench/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/tommasonovelli/bora-workbench.svg)](https://github.com/tommasonovelli/bora-workbench/releases/tag/v0.2.0)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-31213/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**One Qwen setup, three local experiences.**

| Command | What you get |
|---|---|
| `bora coding` | a local OpenAI-compatible API for editors, scripts, and agents |
| `bora studio` | browser-based local chat in the built-in `llama.cpp` UI |
| `bora vstudio` | the same UI with the pinned vision projector, for multimodal chat |

`bora-workbench` is a ready-to-use local Qwen environment. It installs the verified `llama.cpp`
engine for the hardware it detects, resolves and checks the model, and manages the complete service
lifecycle: start, health check, status, logs, and an identity-safe stop. Services listen on
`127.0.0.1` only.

You provide the weights. Everything else — engine build, flags, checksums, ports, and process
lifetime — is already decided, pinned, and verified.

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

It is not a generic model manager and it runs no plugins.

## Start here

If this is your first time opening the project, the simplest path is:

1. check the [requirements](#requirements);
2. [install the release](#installation);
3. make the [pinned model](#model) available;
4. run `engine install`;
5. start `coding`, `studio`, or `vstudio`;
6. once that works, [calibrate the machine](#calibration-is-the-second-step-not-the-entry-price);
7. use the [full documentation](docs/README.md) when you want configuration and details.

## Project status

> [!WARNING]
> The `0.2` series is **not stable** and is intended for evaluation, exactly like `0.1` before it.
> The CLI, configuration, record formats, procedures, and performance carry no stability guarantee.
> Do not use it for critical workloads without independent verification and backups of your local
> data.

Version **`0.2.0`** is the first release named `bora-workbench`, whose command is `bora`. An
installation of the previous `qwen-launcher` series is replaced rather than upgraded: its
configuration, data, cache, and state directories are not read by `bora`.

Calibration uses one working protocol. The removed protocol switch and record formats are not
supported, and a record written by the previous launcher is diagnosed as superseded. Re-run
`calibrate` after installing instead of copying or converting an old record.

## Requirements

- Ubuntu 22.04+ x86-64 or Windows 11 x86-64;
- CPU, or a single NVIDIA CUDA GPU;
- at least **28 GiB total RAM** and **22 GiB available** for the default model;
- room for the GGUF (22,663,387,424 bytes), the mmproj (902,822,528 bytes), the engine, and logs;
- the model already present in the pinned Hugging Face cache;
- HTTPS connectivity to install the tool and the engine, unless the artifacts are already available.

CUDA on multi-GPU hosts is blocked because isolation has only been verified on single-GPU hosts.
If `nvidia-smi` is unavailable or unreliable, the launcher falls back to CPU and prints a warning.

## Installation

Install the exact `v0.2.0` wheel from the GitHub Release. The commands below download the installer
and wheel, verify both SHA-256 digests, and then install the tool with pinned uv `0.11.28` and
CPython `3.12.13`. You do not need to install uv or Python first, and no administrator privileges
are used.

### Ubuntu

Open a terminal in a new directory, copy the entire block, and press Enter:

```bash
version="0.2.0"
base="https://github.com/tommasonovelli/bora-workbench/releases/download/v${version}"
wheel="bora_workbench-${version}-py3-none-any.whl"
installer_sha256="102be4606a3b71dfd088a333ed3fe2fed0e2faa61b9c60febe4aa05603ea1ba6"
wheel_sha256="9a3fc0d3c7f6887ddd87cceed45bc588e36a61b71ba246a471e9e172430b7f27"

curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/install.sh" --output install.sh
curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/$wheel" --output "$wheel"
printf '%s  %s\n' "$installer_sha256" install.sh | sha256sum --check -
printf '%s  %s\n' "$wheel_sha256" "$wheel" | sha256sum --check -
sh ./install.sh --wheel "./$wheel" --sha256 "$wheel_sha256"
```

### Windows

Open PowerShell in a new directory, copy the entire block, and press Enter:

```powershell
$Version = "0.2.0"
$Base = "https://github.com/tommasonovelli/bora-workbench/releases/download/v$Version"
$Wheel = "bora_workbench-$Version-py3-none-any.whl"
$InstallerSha256 = "ad9adaa7c4ed1bcf94e64f199dc5e02695f1eb62a6dcaadcd4b2ce0bfacba128"
$WheelSha256 = "9a3fc0d3c7f6887ddd87cceed45bc588e36a61b71ba246a471e9e172430b7f27"

Invoke-WebRequest -Uri "$Base/install.ps1" -OutFile install.ps1
Invoke-WebRequest -Uri "$Base/$Wheel" -OutFile $Wheel
if ((Get-FileHash .\install.ps1 -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InstallerSha256) {
    throw "install.ps1 SHA-256 mismatch"
}
if ((Get-FileHash ".\$Wheel" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $WheelSha256) {
    throw "$Wheel SHA-256 mismatch"
}
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

## Model

The weights are not bundled and the launcher does not download them. For the default model it reads
the Hugging Face snapshot of revision `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d` read-only and
verifies the name, size, and SHA-256 of:

```text
Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
mmproj-BF16.gguf
```

The mmproj is only needed by `vstudio`. Acquire the files separately from the
[pinned repository revision](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/tree/5bc3e238d916f48a861bac2f8a1990a0e9b7e98d)
with a tool of your choice. The Hugging Face cache is never modified, and `uninstall` never removes
it.

## First run

Install the engine that matches the detected hardware:

```bash
bora engine install
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
and asks for confirmation. Read [Local calibration](docs/calibration.md) before running it.

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
- the Hugging Face cache is never modified or deleted.

## Documentation

The [full documentation](docs/README.md) follows a path for readers starting from scratch:
installation → commands → configuration → architecture → calibration → operations → development →
releasing.

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
