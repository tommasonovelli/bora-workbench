# Commands

The general form is:

```text
qwen-launcher [--version] <command> [options]
```

`--help` is available on the main group and on every command. Typer also exposes
`--install-completion` and `--show-completion` for the current shell.

## Summary

| Command | Purpose | Changes local data? |
|---|---|---:|
| `--version` | shows the installed version | no |
| `validate` | validates resources or a local bundle | no |
| `doctor` | describes configuration, hardware, engine, and records | no |
| `engine status` | inspects the managed engine | no |
| `engine install` | installs and activates the engine from the lock | yes |
| `coding` | starts the text API | state and logs |
| `studio` | starts the built-in text UI | state and logs |
| `vstudio` | starts the UI with vision | state and logs |
| `status` | shows live services and clears stale state | if needed |
| `stop` | stops verified managed services | yes |
| `calibrate` | measures the machine and manages local records | yes |
| `uninstall` | deletes the managed roots after confirmation | yes |

## `validate`

```bash
qwen-launcher validate
qwen-launcher validate --path <bundle-directory>
```

Without `--path` it validates the installed resources:

- JSON Schema Draft 2020-12;
- modes, policies, and reports;
- references and SHA-256 between policy and evidence;
- engine lock semantics and flag coverage;
- cross-cutting constraints a schema cannot express.

With `--path` it validates a shareable bundle produced by the `calibration/v1` laboratory, including
the manifest, relative references, and the privacy scan. Errors report the file, the field path, and
the reason. Warnings alone exit with 0; at least one error exits with 1.

## `doctor`

```bash
qwen-launcher doctor
```

Shows the version, resolved configuration, OS, CPU, RAM, backend, GPU/VRAM, the number of shared
seeds, the managed engine, the four public directories, and content validation. For each mode it
also evaluates the state of the local record:

- active and valid, with the calibrated parameters applied to launches (`ctx` and, on CUDA,
  `--n-cpu-moe`);
- a candidate awaiting activation;
- absent;
- incompatible or stale;
- superseded schema;
- insufficient current headroom.

The command creates no directories and fixes no problem automatically. An invalid configuration
exits with 2; a hardware or content error with 1; diagnostic warnings with 0.

## `engine status`

```bash
qwen-launcher engine status
```

Shows the active manifest, release, backend, executable, and compatibility with `engine.lock`. A
missing engine is an informational state and exits with 0; an installation that is present but
incompatible exits with 1.

## `engine install`

```bash
qwen-launcher engine install
qwen-launcher engine install --force
```

Detects CPU/CUDA, selects the exact asset set from the lock, downloads over HTTPS, verifies SHA-256,
extracts to staging, verifies the executable, and activates a new immutable directory. A target that
is already active and compatible is a no-op. `--force` reinstalls the same target anyway; it does
not disable TLS, checksums, confinement, or the compatibility probes.

The command shows the current phase during cache check, download, extraction, build, verification,
and activation. On a terminal, download and extraction have a byte progress bar with the asset
position, average speed, and computed ETA; without a reliable measurement the other phases show no
invented estimate. Redirected output stays line-oriented. It may use the network and, on Ubuntu
CUDA, run CMake and a build lasting several minutes: the phase stays visible even while CMake has
not finished yet. The `--version` and `--help` probes are bounded to 60 seconds each. The command
installs no system prerequisites and never elevates privileges.

## Run modes

```bash
qwen-launcher coding [--force]
qwen-launcher studio [--force]
qwen-launcher vstudio [--force]
```

All three follow the same flow: configuration → hardware → RAM gate → content → model → plan →
engine → port → process → health check → foreground.

| Mode | UI | Vision | Sampling `(temp, top_p, top_k)` |
|---|---:|---:|---|
| `coding` | no | no | `(0.6, 0.95, 20)` |
| `studio` | yes | no | `(0.7, 0.8, 20)` |
| `vstudio` | yes | yes | `(0.7, 0.8, 20)` |

`--force` skips only the 28 GiB total and 22 GiB available thresholds of the default model. It does
not skip configuration, platform, multi-GPU, engine, model, checksum, port, or health checks.

Once READY, the CLI shows:

- backend and mode;
- the local record, or the non-optimized baseline;
- the API at `http://127.0.0.1:<port>/v1`;
- for `studio`/`vstudio`, the UI at `http://127.0.0.1:<port>/`;
- the log path.

The contract also exposes `/health`, `/v1/models`, `/v1/chat/completions`, and `/metrics`. The
service listens on `127.0.0.1` only. `studio` and `vstudio` open the browser only after READY and
only when `open_browser=true`.

With `coding` running, a minimal request from another POSIX terminal is:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  --header 'Content-Type: application/json' \
  --data '{"messages":[{"role":"user","content":"Write a Python sum function."}],"max_tokens":128,"stream":false}'
```

Replace `8080` if `llama_port` differs. Any client compatible with the local OpenAI chat completions
endpoint works; the current managed server requires no key.

The command stays attached to the process. `Ctrl-C` terminates the server, removes the state, and
returns 130. A natural non-zero exit returns 1 and points to the log.

## `status`

```bash
qwen-launcher status
```

Shows the service, PID, mode, backend, port, and log. It first verifies each entry through
`pid + create_time`; dead entries or reused PIDs are removed with a warning. Malformed JSON state is
quarantined as `services.corrupt-<timestamp>.json`. No services at all is a success with exit code
0.

## `stop`

```bash
qwen-launcher stop
```

Stops only processes whose identity matches the state. It waits up to 10 seconds after `terminate`,
then uses `kill` and waits up to 5 seconds. It is idempotent: no services returns 0. Do not delete
`services.json` by hand while the process is alive.

## `calibrate`: current v5 protocol

```bash
qwen-launcher calibrate --mode <coding|studio|vstudio|all>
```

`--protocol v5` is the default. The command shows a preflight and asks for confirmation before
starting processes. By default it writes one candidate per completed mode and activates it
atomically.

v5 options:

```bash
qwen-launcher calibrate --mode all --no-activate
qwen-launcher calibrate --mode coding --activate
qwen-launcher calibrate --mode coding --target-ctx 98304
```

| Option | Effect |
|---|---|
| `--no-activate` | keeps the new records as candidates without changing the active ones |
| `--activate` | promotes already valid candidates, without new trials |
| `--target-ctx N` | uses a single approved expert context |

The allowed targets are `131072`, `98304`, `65536`, `49152`, `32768`, `16384`, and `8192`; they are
the same steps used by the automatic scale. `--activate` cannot be combined with `--target-ctx`;
`--activate` and `--no-activate` are mutually exclusive.

The three options are handled by the command's specialized parser. `calibrate --help` lists them in
the epilog together with the v1 extras, while the table generated by Typer contains only the common
options; the syntax above is the one actually supported.

On an interactive terminal the v5 run shows a live bar with the phase, trial, elapsed time, and an
adaptive estimate; redirected output stays line-oriented. Screening shows `≤14` and a duration
projection up to that cap, not a limit or a promise. The final summary includes the selection
rationale and the lowest observed RAM/VRAM values.

Calibration performs no uploads, does not modify `config.toml`, and installs neither the model nor
the engine. Trials use the configured port when it is free; on the current branch they fall back to
a system-assigned loopback port when it is busy. This fallback does not apply to the three normal
launches.

Algorithm and record details: [Calibration](calibration.md).

## `calibrate`: experimental v6 protocol

```bash
qwen-launcher calibrate --mode all --protocol v6 --preference balanced
```

`calibration/v6-lite` is **opt-in** (`--protocol v6`); `v5` remains the default. It measures three
envelopes per mode (`fast`, `balanced`, `max_context`) and writes all of them into the
`calibration-record/v5` record.

| Option | Effect |
|---|---|
| `--protocol v6` | runs the experimental three-envelope search (v5 remains the default) |
| `--preference fast\|balanced\|max-context` | pins the active envelope in the record (default `balanced`); only with `v6` |
| `--target-ctx N` | collapses the v6 scale onto a single approved step |
| `--no-activate` / `--activate` | as in v5: keeps or promotes the candidates |

Allowed v6 targets: `131072`, `98304`, `65536`, `49152`, `32768`. `--preference` is rejected without
`--protocol v6`. v6 trial reserves: 0.5 GiB VRAM, 2.0 GiB RAM, 0.125 GiB release tolerance.
Promoting v6 to the default protocol is a human decision (D-063), never automatic.
Details: [Calibration — calibration/v6-lite](calibration.md#calibrationv6-lite-experimental).

## `calibrate`: v1 laboratory

The historical protocol remains executable only as an explicit laboratory and produces a draft
bundle, not an active record:

```bash
qwen-launcher calibrate \
  --mode coding \
  --protocol v1 \
  --candidate safe:8192:41 \
  --candidate mixed:8192:30 \
  --settings 2:0.5:0.125
```

On CUDA each candidate uses `ID:CTX:N_CPU_MOE` and the settings use
`RUNS:MIN_FREE_VRAM_GIB:RELEASE_TOLERANCE_GIB`. On CPU the candidate uses `ID:CTX` and `--settings`
contains only `RUNS`. `--candidate` is repeatable. If candidates or settings are missing, the CLI
asks for them interactively; it assigns no implicit defaults.

The v5 options are not valid with `--protocol v1`. Candidates and `--settings` are not valid with
v5. `--protocol v3` and `--protocol v4` start no new runs; historical records remain supported.

## `uninstall`

```bash
qwen-launcher uninstall
```

Refuses to proceed while a live managed service exists. It shows the configuration, data, cache,
state, and the current Python installation, then asks for a single confirmation. If the command
comes from the supported `uv tool` installation, it also removes the Python tool through uv as soon
as the process exits; uv itself and the Hugging Face cache stay unchanged. A Python installation not
managed by uv is reported explicitly and is not removed on a guess. A normal cancellation deletes
nothing and exits with 0; `Ctrl-C` exits with 130.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | success, empty state, or warnings only |
| `1` | expected operational error or failed validation |
| `2` | invalid CLI input or configuration |
| `130` | keyboard interrupt |

Expected operational errors are written to stderr without a traceback. A traceback instead indicates
an unexpected bug and should be reported with the command that was run, the output, and a log
reviewed for private data.

**Next:** [Configuration and local data](configuration.md)
