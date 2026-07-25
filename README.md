# qwen-launcher

[![CI](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/tommasonovelli/qwen-launcher.svg)](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.5)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-31213/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**One Qwen setup, three local experiences.**

| Command | What you get |
|---|---|
| `qwen-launcher coding` | a local OpenAI-compatible API for editors, scripts, and agents |
| `qwen-launcher studio` | browser-based local chat in the built-in `llama.cpp` UI |
| `qwen-launcher vstudio` | the same UI with the pinned vision projector, for multimodal chat |

`qwen-launcher` is a ready-to-use local Qwen environment. It installs the verified `llama.cpp`
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
> The `0.1` series is intended for evaluation. The CLI, configuration, record formats, procedures,
> and performance carry no stability guarantee. Do not use it for critical workloads without
> independent verification and backups of your local data.

The current release is **`0.1.5`**, published on
[GitHub Releases](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.5). It is the
first fully English release and republishes the calibration evidence with a regenerated digest
chain; the runtime is unchanged. PyPI remains unavailable.

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

The release attaches the wheel, sdist, installers, and `SHA256SUMS` produced by the cross-platform
test/build run. Use the wheel digest reported in the attached manifest.

### Ubuntu

```bash
base="https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.5"
wheel="qwen_launcher-0.1.5-py3-none-any.whl"
curl --fail --location "$base/install.sh" --output install.sh
curl --fail --location "$base/$wheel" --output "$wheel"
curl --fail --location "$base/SHA256SUMS" --output SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
wheel_sha256="$(awk -v wheel="$wheel" '$2 == wheel { print $1 }' SHA256SUMS)"
test "${#wheel_sha256}" -eq 64
sh ./install.sh --wheel "./$wheel" --sha256 "$wheel_sha256"
```

### Windows

From PowerShell:

```powershell
$base = "https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.5"
$wheel = "qwen_launcher-0.1.5-py3-none-any.whl"
Invoke-WebRequest "$base/install.ps1" -OutFile install.ps1
Invoke-WebRequest "$base/$wheel" -OutFile $wheel
Invoke-WebRequest "$base/SHA256SUMS" -OutFile SHA256SUMS
$pattern = "^[0-9a-f]{64}\s+$([regex]::Escape($wheel))$"
$entry = Select-String -Path .\SHA256SUMS -Pattern $pattern
if ($null -eq $entry) { throw "Wheel digest missing from SHA256SUMS" }
$sha256 = ($entry.Line -split "\s+")[0]
if ((Get-FileHash $wheel -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha256) {
  throw "Wheel SHA-256 mismatch"
}
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Wheel ".\$wheel" -Sha256 $sha256
```

The installers pin uv `0.11.28` and CPython `3.12.13`, require an explicit source, and never use
administrative privileges. Details and alternatives are in
[Installation and first run](docs/installation.md).

Verify immediately:

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
```

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
qwen-launcher engine install
qwen-launcher engine status
```

Then pick an experience and start it:

```bash
qwen-launcher coding
```

After READY the CLI shows the API/UI URLs and the log path. All three modes serve the API at
`http://127.0.0.1:<llama_port>/v1`; `coding` keeps UI and vision disabled, while `studio` and
`vstudio` also serve the built-in UI and open the browser only when `open_browser=true`. The process
stays in the foreground, and `Ctrl-C` stops it and cleans up the state.

Control it from another terminal:

```bash
qwen-launcher status
qwen-launcher stop
```

The full command surface, options, and exit codes are in [Commands](docs/commands.md).

## Calibration is the second step, not the entry price

The launcher is useful before you ever calibrate. All three modes start on the verified baseline —
`ctx=8192`, and on CUDA `n_cpu_moe=48` — and the CLI states plainly that it is not optimized.

Calibration is what you run once the setup already works, to fit it to *this* machine:

```bash
qwen-launcher calibrate --mode all
```

It measures `coding`, `studio`, and `vstudio`, finds how much context the hardware can actually
serve, and compares the feasible configurations by latency, throughput, and memory margin. Each mode
gets one private record holding three launch envelopes — `fast`, `balanced`, and `max-context` — of
which one is active:

```bash
qwen-launcher calibrate --mode all --preference max-context
```

It does not change the model or the quality of the answers: it changes how much context you can
hold, how the work is split between CPU and GPU, and the throughput you get from that split.

Calibration can run for a long time and starts many temporary processes; it always shows a preflight
and asks for confirmation. Read [Local calibration](docs/calibration.md) before running it.

## Concepts in one minute

- **Engine**: the `llama-server` executable from the pinned release.
- **Mode**: the service behavior (UI, vision, and sampling).
- **Baseline**: the verified configuration used when no local calibration exists.
- **Local record**: the private result of calibrating this machine, for one mode only.
- **Envelope**: one measured set of launch parameters; a record holds three, one of them active.

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
uv run --frozen qwen-launcher validate
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
