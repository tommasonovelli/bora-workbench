# Spike 0 — llama.cpp b10011

## Status

**Overall decision: `GO`. Ubuntu and Windows results: `PASS`.**

The required matrix is complete on Ubuntu 24.04 and Windows 11, with the CPU and CUDA backends in
the `coding`, `studio`, and `vstudio` modes. The `GO` covers only Qwen 3.6, the release, and the
trial envelope stated here. The measurements define no RAM/VRAM tiers and do not change the
production settings of the three modes.

The machine has a single GPU. `CUDA_VISIBLE_DEVICES=0` exposed `CUDA0` to the child without
modifying the parent environment, but selecting among several physical GPUs could not be tested.
Consequently 0.1 must refuse CUDA startup on multi-GPU hosts until that case is verified; this
declared limit does not invalidate execution on the single-GPU host tested here.

## Verified versions

- engine: `ggml-org/llama.cpp` tag `b10011`;
- commit: `bf2c86ddc0685f580595954056c2e77ebabfab4f`;
- probe: `version: 10011 (bf2c86ddc)`, Clang Windows and GNU Linux x86-64 builds;
- engine license: MIT;
- model: `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`;
- model revision: `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`;
- declared model license: Apache-2.0; the base model text was acquired at revision
  `995ad96eacd98c81ed38be0c5b274b04031597b0`;
- GGUF: SHA-256 `0b21525e972670ed59e1812e170b27c26355381f0656ecc4e25617ece7dac58b`;
- mmproj BF16: SHA-256 `da63cb47a76763c712393f8a017070188a304fa39f8aeea6edc629ed7b975cfa`.

The launcher does not redistribute the weights and does not modify the Hugging Face cache.

## Machines

Both tests use an Intel Core i5-10400F, 6 cores / 12 threads, about 32 GiB RAM, and an NVIDIA
GeForce RTX 2060 SUPER with 8192 MiB.

- Ubuntu 24.04 x86-64, kernel `6.17.0-40-generic`, NVIDIA driver `595.71.05`, CUDA toolkit
  `12.0.140`;
- Windows 11 Pro x86-64, build `10.0.26200`, NVIDIA driver `610.47`, CUDA UMD `13.3`.

The complete output is in `spike-0/ubuntu-b10011/system-info.txt` and
`spike-0/windows-b10011/system-info.json`/`nvidia-smi.txt`.

## Verified assets and runtime

### Ubuntu CPU and CUDA

The official CPU asset tested is:

```text
llama-b10011-bin-ubuntu-x64.tar.gz
https://github.com/ggml-org/llama.cpp/releases/download/b10011/llama-b10011-bin-ubuntu-x64.tar.gz
sha256: 3cae0a514d2e95062be5b1ca19474446080a1cc12ae5cb1a89d0534bcd013ec1
```

CUDA was built from the archive of the exact commit, SHA-256
`8a43d487370d775a4f6a6faa1f27085c51eae13d7d2b9dc403b551966114f397`, setting
`LLAMA_BUILD_NUMBER=10011` and the full commit because the source archive contains no `.git`. The
CMake command and the raw log are archived.

### Windows CPU

```text
llama-b10011-bin-win-cpu-x64.zip
sha256: 5cb0676f1b6341aa1f3144c3d7fd00bd638a0ce676954712444aecd61f71ad36
```

The asset was downloaded from the official release, verified before extraction, and tested in the
three modes. `--list-devices` does not list CUDA and the CPU commands contain no `-ngl` or
`-ncmoe`.

### Windows CUDA 13.3

The pair actually paired up and tested is:

```text
llama-b10011-bin-win-cuda-13.3-x64.zip
sha256: 2af4f3c1fb42afa85c76a782187444e44f33c08fa31b9000e6baeb18342c6ea2

cudart-llama-bin-win-cuda-13.3-x64.zip
sha256: 1462a050eb4c684921ba51dcc4cc488a036674c3e73e9945ee705b854808d03e
```

The runtime contains exactly `cublas64_13.dll`, `cublasLt64_13.dll`, and `cudart64_13.dll`.
`extracted-files.json` records the size and SHA-256 of every extracted file. The version, help,
devices, loading, and the whole matrix were run with this pair, not with the pre-existing b9987
installation found on the machine.

## Licenses and redistributability

- The llama.cpp MIT text was acquired from the exact commit and has SHA-256
  `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`.
  The binary zips do not include the text: a managed distribution must preserve its copyright and
  permission notice.
- The CUDA Toolkit EULA v13.3, updated on 26 January 2026, is archived with SHA-256
  `6180cc2a02db890cf87ba52f078b7a222b04dcb3c2650865763d4f32ad663a5c`.
  Section 2.6 Attachment A lists the Windows variants of the CUDA Runtime (`cudart`) and CUDA BLAS
  (`cublas`, `cublasLt`) as redistributable, subject to the distribution requirements of section
  1.1.2. The runtime zip contains only those three DLLs but not the EULA; the current managed
  installation therefore keeps the verified NVIDIA notice alongside the assets.
- The model and mmproj are not redistributed by the launcher.

This is a technical verification of the terms applicable to the assets, not legal advice.

## Observed contract

- version: `--version`, exit 0, contains `version: 10011` and `bf2c86ddc`;
- full help: `--help`, exit 0, with every flag of the contract;
- health while loading: HTTP 503 with the error `Loading model`;
- health when ready: HTTP 200 with `{"status":"ok"}`;
- models: `/v1/models`; chat: `/v1/chat/completions`; metrics: `/metrics`; UI: `/`;
- host: `127.0.0.1`; CORS restricted with `--cors-origins localhost`;
- explicit UI: `--webui` / `--no-webui`;
- explicit vision: `--mmproj <file>` / `--no-mmproj`;
- CUDA: `-ngl 99 -ncmoe 48`; CPU: no CUDA arguments;
- MTP: `--spec-type draft-mtp --spec-draft-n-max 2`;
- sampling for coding `(0.6, 0.95, 20)`, studio/vstudio `(0.7, 0.8, 20)`.

The complete arrays are in `spike-0.json`, in the Ubuntu `commands.json`, and in the `command.json`
of every Windows test. The contract contains no parameter derived from RAM, VRAM, or speed.

## Functional matrix

| OS | Backend | Mode | UI | Vision | MTP | Health/API/metrics | Stop/log | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Ubuntu | CPU | coding | off | off | yes | yes | yes | PASS |
| Ubuntu | CPU | studio | on | off | yes | yes | yes | PASS |
| Ubuntu | CPU | vstudio | on | on | yes | yes | yes | PASS |
| Ubuntu | CUDA | coding | off | off | yes | yes | yes | PASS |
| Ubuntu | CUDA | studio | on | off | yes | yes | yes | PASS |
| Ubuntu | CUDA | vstudio | on | on | yes | yes | yes | PASS |
| Windows | CPU | coding | off | off | yes | yes | yes | PASS |
| Windows | CPU | studio | on | off | yes | yes | yes | PASS |
| Windows | CPU | vstudio | on | on | yes | yes | yes | PASS |
| Windows | CUDA | coding | off | off | yes | yes | yes | PASS |
| Windows | CUDA | studio | on | off | yes | yes | yes | PASS |
| Windows | CUDA | vstudio | on | on | yes | yes | yes | PASS |

The red PNG was recognized as `Rosso` on CPU and CUDA on both operating systems. The explicit UI
returns 200 with gzip support; `--no-webui` returns 404. The responses contain MTP draft activity.
On Windows every process was terminated, the port was found closed, and stdout/stderr are kept in
the corresponding `server.log`.

## GPU isolation

On Ubuntu and Windows, `CUDA_VISIBLE_DEVICES=0` exposes `CUDA0`; on Windows the server's PID was
observed on the GPU. The parent process's variable was absent before and after the tests. The host
has a single GPU, so there is no evidence of remapping among several physical GPUs. Furthermore, in
the current Windows test an empty value passed through `CreateProcess` did not hide the GPU, while
the non-existent index `99` exposed no devices; the preliminary PowerShell archive instead showed no
devices with the empty value. The launcher does not use the empty value: it always sets a concrete
index. In order not to promise more than was tested, multi-GPU CUDA must stay blocked in 0.1.

## `benchmark/v1` benchmark

The protocol uses a fixed prompt and request with recorded SHA-256 digests, `max_tokens=256`,
`ignore_eos=true`, seed `424242`, one excluded warm-up, and five measurements, with no concurrent
clients. Every response has `completion_tokens=256`, `predicted_n=256`, and `finish_reason=length`;
tok/s comes from `response.timings.predicted_per_second`, cross-checked with
`predicted_n / predicted_ms`.

| OS | Backend | Mode | Min tok/s | Median tok/s | Max tok/s |
|---|---|---|---:|---:|---:|
| Ubuntu | CPU | coding | 10.865 | 11.042 | 11.234 |
| Ubuntu | CPU | studio | 11.097 | 11.261 | 11.507 |
| Ubuntu | CPU | vstudio | 11.404 | 11.457 | 11.490 |
| Ubuntu | CUDA | coding | 31.493 | 31.524 | 31.547 |
| Ubuntu | CUDA | studio | 34.279 | 34.294 | 34.388 |
| Ubuntu | CUDA | vstudio | 35.037 | 35.214 | 35.253 |
| Windows | CPU | coding | 8.437 | 8.710 | 8.967 |
| Windows | CPU | studio | 8.162 | 9.087 | 9.267 |
| Windows | CPU | vstudio | 8.378 | 8.394 | 8.498 |
| Windows | CUDA | coding | 15.503 | 19.281 | 19.598 |
| Windows | CUDA | studio | 23.958 | 24.393 | 24.787 |
| Windows | CUDA | vstudio | 23.749 | 24.365 | 24.495 |

That is 12 excluded warm-ups and 60 valid measurements. The numbers describe only this machine,
release, model, context 8192, and trial envelope; they are neither profiles nor guidance for
choosing experts, layers, RAM, or VRAM.

## Evidence and integrity

- `evidence/engine/spike-0/SHA256SUMS`: the global manifest of the active evidence;
- `evidence/engine/spike-0/windows-b10011/SHA256SUMS`: all 229 raw Windows outputs;
- `evidence/engine/spike-0/research/`: release/model metadata and the acquired license texts.

## Decision

The outcome is `GO` for the contract pinned today. The release, commit, Windows CPU/CUDA 13.3
assets, runtime, help/version, command, health, API, UI, vision, MTP, sampling, metrics, stop/log,
and benchmark were verified without inventing data. These measurements demonstrate feasibility, not
an optimal envelope or a transferable profile. Multi-GPU CUDA stays outside the verified scope, and
the managed installations keep the required MIT/NVIDIA notices.
