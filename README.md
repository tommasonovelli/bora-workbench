# qwen-launcher

[![CI](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/tommasonovelli/qwen-launcher.svg)](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.4)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-31213/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`qwen-launcher` installs, calibrates, and governs one precise local configuration of Qwen and
`llama.cpp`. It is meant for anyone who wants to start the model without rebuilding flags, checksums,
profiles, and server lifecycle every time.

The project pins:

- the `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M` model;
- `llama.cpp b10011` at its verified commit;
- three usage modes (`coding`, `studio`, `vstudio`);
- a safe engine installation;
- local calibration for the current machine;
- status, logs, health checks, and identity-safe stop.

It is not a generic model manager and it runs no plugins. Services listen on `127.0.0.1` only.

## Start here

If this is your first time opening the project, the simplest path is:

1. check the [requirements](#requirements);
2. [install the release](#installation);
3. make the [pinned model](#model) available;
4. run `engine install`;
5. start `coding`, or calibrate the machine first;
6. use the [full documentation](docs/README.md) when you want to understand configuration and details.

## Project status

> [!WARNING]
> The `0.1` series is intended for evaluation. The CLI, configuration, record formats, procedures,
> and performance carry no stability guarantee. Do not use it for critical workloads without
> independent verification and backups of your local data.

The current release is **`0.1.4`**, published on
[GitHub Releases](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.4). It keeps
`calibration/v5` as the default and adds `calibration/v6-lite` as an opt-in experimental protocol
(`--protocol v6 --preference`, `calibration-record/v5` records) under a recorded maintainer override
(D-063). Promoting v6 to the default remains conditional on a human GO verdict. PyPI remains
unavailable.

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
base="https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.4"
wheel="qwen_launcher-0.1.4-py3-none-any.whl"
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
$base = "https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.4"
$wheel = "qwen_launcher-0.1.4-py3-none-any.whl"
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

You can then start right away on the verified baseline:

```bash
qwen-launcher coding
```

The baseline uses `ctx=8192` and, on CUDA, `n_cpu_moe=48`. It works, but it is not optimized.

To measure the machine first and activate a local configuration for every mode:

```bash
qwen-launcher calibrate --mode all
```

Calibration can run for a long time and starts many temporary processes; it always shows a preflight
and asks for confirmation. Read [Local calibration](docs/calibration.md) before running it.

## Concepts in one minute

- **Engine**: the `llama-server` executable from the pinned release.
- **Mode**: the service behavior (UI, vision, and sampling).
- **Baseline**: the verified configuration used when no local calibration exists.
- **Local record**: the private result of calibrating this machine, for one mode only.
- **Shared seed**: a hint about trial ordering; it never copies another machine's configuration.

The launcher reuses a record only when the machine, model, engine, mode, and current memory are still
compatible. Otherwise it explains why and falls back to the baseline.

## Available modes

| Command | Experience |
|---|---|
| `qwen-launcher coding` | text-only OpenAI-compatible API, UI and vision disabled |
| `qwen-launcher studio` | text chat in the built-in llama.cpp UI |
| `qwen-launcher vstudio` | built-in UI with the pinned vision projector |

After READY the CLI shows the API/UI URLs and the log path. `studio` and `vstudio` open the browser
only when `open_browser=true`. The process stays in the foreground; `Ctrl-C` stops it and cleans up
the state.

Control it from another terminal:

```bash
qwen-launcher status
qwen-launcher stop
```

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
