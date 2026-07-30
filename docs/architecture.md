# Architecture

## Product scope

`bora-workbench` is a specialized launcher, not a generic model manager. It governs one precise
combination of:

- the default Qwen model and vision projector;
- a verified `llama.cpp` release;
- three declarative modes;
- CPU/CUDA detection;
- local per-mode calibration;
- safe process installation and lifecycle.

The core decides **how** to validate, measure, and govern. The versioned JSON declares **which**
modes, contracts, and shared evidence are available. No content executes arbitrary code.

## Startup flow

```text
CLI
 └─ strict configuration
     └─ hardware detection
         └─ RAM gate and GPU support
             └─ validated declarative catalog
                 └─ model resolution and verification
                     └─ compatible local record, or baseline
                         └─ immutable LaunchPlan
                             └─ engine resolution and probes
                                 └─ command expanded from engine.lock only
                                     └─ state + process + health check
                                         └─ READY endpoints in the foreground
```

An error stops the flow at the point where it is detected. There are no silent fallbacks to
different models, releases, flags, ports, or assets.

## Optional terminal-front-end flow

Bare `bora` adds presentation around the same explicit command tree without entering the launch
flow itself; there is no `tui` subcommand:

```text
interactive terminal capability check
 └─ static Textual chrome
     └─ one thread worker calls the synchronous read-only snapshot collector
         └─ seven snapshot-backed views and exact command composers
             └─ Textual exits and restores the terminal
                 └─ existing Click/Typer leaf callback runs in the same bora process
```

Opening and refresh never call a mutating CLI presenter such as `status`; they use structured
read-only inspections instead. The snapshot may run bounded hardware and engine probes, but performs
no network request, payload hash, receipt write, state cleanup, directory creation, or service
start. There is no background snapshot poll: only opening and a serialized explicit refresh collect
again.

Textual owns only its presentation event loop, one optional motion timer shared by every page, and
one thread worker for the synchronous collector. Sections animate the same wind/sea frame as home
rather than freezing a copy of it. No core module gains an async API, scheduler, executor, or UI
knowledge. A
selected command returns from Textual first; using the existing parser afterwards keeps all
validation, confirmation, lifecycle, and exit-code ownership in the real callback and leaves no TUI
parent around update or uninstall. Successful returning callbacks wait for terminal acknowledgement
before another Textual lifetime begins, so their output remains readable.

## Repository components

| Area | Current responsibility |
|---|---|
| `cli.py`, `_cli_*` | Typer input, Rich presentation, confirmations, and exit codes |
| `snapshot.py` | structured, synchronous, non-mutating facts shared by diagnostics and the TUI |
| `tui/` | Textual presentation, pure advice/command composition/motion, and seven screens |
| `paths.py` | computing the four per-OS roots, without creating them |
| `config.py` | TOML, environment, precedence, and types |
| `hardware.py` | CPU/RAM, NVIDIA, GPU processes, and telemetry |
| `profiles.py` | runtime modes, gates, and `LaunchPlan` |
| `engine.py`, `_engine_*` | lock, model, assets, download/build, installation, and command |
| `process.py`, `_process_*` | port, startup lock, process, health, state, status, and stop |
| `uninstall.py` | confined removal of the managed roots |
| `update.py` | published release lookup, checksum-verified wheel, and uv installation |
| `_tool_handoff.py`, `_tool_helper.py` | identifying the uv installation and running one uv command after this process exits |
| `calibration.py`, `_calibration_*` | target preparation, search, records, evidence, and reuse |
| `benchmark.py`, `benchmark_quick.py` | the immutable feasibility probe and the quick-bench |
| `validation.py`, `_validation_*` | JSON Schema and cross-cutting semantic invariants |
| `resources/` | lock, schemas, modes, policies, reports, benchmarks, and notices in the wheel |
| `install.sh`, `install.ps1` | tool installation from an explicit source |
| `scripts/verify_wheel.py` | external verification of the wheel and sdist |
| `tests/` | offline suite with fakes for server, processes, network, and hardware |
| `.github/workflows/` | cross-platform CI and publication from tested artifacts |
| `evidence/` | measured output and provenance manifests, outside the manuals |

Only `paths.py`, `process.py`, `hardware.py`, and `engine.py` carry platform branches. The private
modules separate internal responsibilities without creating a plugin API.

## Declarative resources

Resources are read with `importlib.resources` as a `Traversable`; the code never assumes a wheel is
extracted on disk. The schemas are JSON Schema 2020-12 and forbid undeclared properties.

| Contract | Current role |
|---|---|
| `mode/v2` | mode services, complete sampling, and reasoning |
| `profile/v1` | compatibility with class-based evidence; no production envelope is distributed |
| `calibration-policy/v2` | the public reference method, distributed as evidence only |
| `calibration-report/v2` | privacy-safe public reference evidence |
| `calibration-record/v6` | one private calibrated preference cell for one mode |
| `engine-lock/v1` | engine identity, command, API, health, and assets |

The installed catalog contains three modes, one public reference policy, and one reference report.
It contains no production `profile/v1` profiles, and nothing in the shared report reaches the
runtime catalog: context, hardware, tok/s, and the observed envelope cannot enter another host's
plan.

`bora validate` meta-validates the schemas—including the closed `engine-lock/v1` schema—validates
the documents, and reconstructs the
links JSON Schema cannot express, including digests, domain, reserves, candidates, and lock
compatibility.

## Modes and launch plan

A mode contains behavior, not performance:

| Mode | UI | Vision | Temperature | top-p | top-k |
|---|---:|---:|---:|---:|---:|
| `coding` | no | no | 0.6 | 0.95 | 20 |
| `studio` | yes | no | 0.7 | 0.8 | 20 |
| `vstudio` | yes | yes | 0.7 | 0.8 | 20 |

`LaunchPlan` merges, unambiguously:

- mode and sampling;
- model identity and physical path;
- port;
- backend and GPU index;
- `ctx` and `n_cpu_moe` from the mode's calibrated cell or the baseline;
- diagnostic references and warnings.

The plan uses a record only when it is the active record for that mode, semantically valid, and
compatible with the model, digest, engine release/commit/contract, OS, backend, components, driver,
and current memory. A maximum drift of 1 MiB is tolerated when comparing total RAM; RAM and VRAM
headroom use the reserves measured with that single calibrated cell.

If the record is missing or not reusable, the baseline is `ctx=8192` and, on CUDA, `n_cpu_moe=48`.
It is always presented as not optimized. Old hardware classes and shared reports produce no
nearest-match.

## Hardware

Detection reads CPU and memory through `psutil`. For NVIDIA it runs, without a shell and with a
5-second timeout:

```text
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader,nounits
```

With multiple devices it picks the one with the most total VRAM and, on a tie, the lowest index;
CUDA startup is blocked anyway, because multi-GPU isolation is unverified. On a supported CUDA host,
`CUDA_VISIBLE_DEVICES=<index>` is added to the child environment only. The launcher's own
environment is never modified.

RAM and VRAM are always binary GiB. For the default model the gate requires 28 GiB total and 22 GiB
available. Different models receive no thresholds invented from the default model.

## Engine and model

The current contract is:

```text
llama.cpp release: b10011
source commit:      bf2c86ddc0685f580595954056c2e77ebabfab4f
model:              unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M
```

`engine.lock` is both an asset lock and the machine language of the command. It contains:

- the `--version` and `--help` probes;
- the complete vocabulary of allowed flags;
- templates for model, context, sampling, network, UI, vision, and backend;
- the API endpoints and the exact health response;
- HTTPS URLs, roles, formats, executables, and asset SHA-256 digests.

The builder expands known placeholders only. The current command pins host `127.0.0.1`, metrics,
Jinja, flash attention, mmap, a single slot, MTP, and CORS on `localhost`; it enables or disables UI
and vision explicitly. CUDA uses `-ngl 99`, the plan's `n_cpu_moe`, and a `q8_0` K/V cache; CPU
receives no CUDA arguments. The weights remain `UD-Q4_K_M`: Q8 concerns the KV cache.

The lock also carries `model_alias_contract`, the name `/v1/models` reports. It sits outside
`command_contract` deliberately: `command_contract_sha256` binds every calibration record to those
exact bytes, and renaming the model changes no measured behavior, so the digest — and every
existing record — stays valid.

The default model is looked for in the managed store at `data_dir()/models` and then, read-only, in
the snapshot of the pinned revision. Both are verified by name, size, and digest. Name and size are
checked on every resolution; the digest is recomputed unless a receipt under the cache root still
matches the path, size, modification time, and expected value, and writing that receipt is
best-effort, so an unwritable cache costs time rather than the launch.

`pull` writes only into the store, using the same verified transfer as the engine assets: HTTPS to
the pinned revision, a `.part` file, a mandatory digest, and an atomic rename. `--hf-repo` is not
used and nothing is ever written into the Hugging Face cache, so the launcher resolves no remote
branches and fabricates no snapshots or refs. Deleting from that cache is possible only through
`rm` and `uninstall`, confined to the pinned artifacts of the locked repository and gated by a
confirmation of its own.

### Managed installation

Assets are downloaded into unique `.part` files under the managed cache. Extraction rejects absolute
paths, drive letters, `..`, special files, and escaping links. The only symlinks allowed are
relative, confined, and present in the verified Ubuntu tar.

Every result moves from staging into a new directory under:

```text
data_dir()/engine/installations/
```

Activation atomically replaces `data_dir()/engine/current.json`, which contains a relative path
verified as a descendant. A download, hash, extraction, build, probe, or activation error leaves the
previous installation intact.

## Process and state

Before startup the launcher:

1. acquires `start.lock` with exclusive creation;
2. clears dead state or state with a reused PID;
3. refuses another managed service;
4. verifies that the configured port is free on loopback;
5. creates the log;
6. starts `llama-server` without a shell and records `pid + create_time`;
7. writes `services.json` atomically;
8. releases the lock and waits for READY.

Health polling uses 2-second requests every second, for up to 15 minutes. Connection refused,
timeouts, 503, and 5xx are transient. READY requires HTTP 200 and the exact JSON body
`{"status":"ok"}`; a 4xx, or an incompatible 200 body, fails immediately.

The state is version 1 and is replaced through a temporary file in the same directory, followed by
flush and `replace`. Malformed JSON is renamed, not overwritten. `status` and `stop` always verify
`pid + create_time`; they never terminate a process based on the PID alone.

## Calibration

Calibration uses the same model, command, health, and workload contracts as a launch, but every
trial lives in isolated state. The v4 search monitors RAM and VRAM, uses fresh processes, and
produces atomic private records. The benchmark is not a standalone command: it is an internal
component run on every confirmation session.

The algorithm, record lifecycle, and empirical limits are described in
[Calibration](calibration.md).

## Security boundaries and side effects

Importing `bora_workbench` uses no network, creates no directories, writes no state, and starts no
processes. It does not import `bora_workbench.tui` or Textual; the framework enters only after bare
`bora` passes its terminal and motion-configuration checks. Every side effect
belongs to the operation that requires it.

The main invariants:

- no `shell=True`, `eval`, `exec`, `sudo`, or automatic elevation;
- no bind on `0.0.0.0`;
- TLS and checksums cannot be disabled;
- deletions limited to the managed roots, plus the pinned artifacts of the locked repository in the
  Hugging Face cache, which need their own separate confirmation;
- nothing is ever written into the Hugging Face cache;
- config and records are never uploaded;
- unrelated processes are protected by full identity checks;
- tests use no real network, GPU, model, or server.

The artifacts under [`evidence/`](../evidence/README.md) document what was measured; they do not
widen the supported perimeter beyond the locks and the explicit claims.

**Next:** [Local calibration](calibration.md)
