# Commands

The general form is:

```text
bora [--version] <command> [options]
```

`--help` is available on the main group and on every command. Typer also exposes
`--install-completion` and `--show-completion` for the current shell.

## Summary

| Command | Purpose | Changes local data? |
|---|---|---:|
| `--version` | shows the installed version | no |
| `validate` | validates the installed resources | no |
| `doctor` | describes configuration, hardware, engine, and records | no |
| `engine status` | inspects the managed engine | no |
| `engine install` | installs the engine from the lock and downloads the model | yes |
| `pull` | downloads and verifies the pinned model | yes |
| `rm` | deletes the pinned model after confirmation | yes |
| `pi` | connects the pi coding agent to the local service | pi's config |
| `coding` | starts the text API | state and logs |
| `studio` | starts the built-in text UI | state and logs |
| `vstudio` | starts the UI with vision | state and logs |
| `status` | shows live services and clears stale state | if needed |
| `stop` | stops verified managed services | yes |
| `calibrate` | measures the machine and manages local records | yes |
| `update` | installs the newest published release, engine untouched | the Python tool |
| `uninstall` | deletes the managed roots after confirmation | yes |

## `validate`

```bash
bora validate
```

It validates the installed resources:

- JSON Schema Draft 2020-12;
- modes, policies, and reports;
- references and SHA-256 between policy and evidence;
- engine lock semantics and flag coverage;
- cross-cutting constraints a schema cannot express.

Errors report the file, the field path, and the reason. Warnings alone exit with 0; at least one
error exits with 1.

## `doctor`

```bash
bora doctor
```

Shows the version, resolved configuration, OS, CPU, RAM, backend, GPU/VRAM, the managed engine, the
four public directories, and content validation. For each mode it also evaluates the state of the
local record:

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
bora engine status
```

Shows the active manifest, release, backend, executable, and compatibility with `engine.lock`. A
missing engine is an informational state and exits with 0; an installation that is present but
incompatible exits with 1.

## `engine install`

```bash
bora engine install
bora engine install --force
bora engine install --no-model
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

Once the engine is active it downloads the pinned model, exactly as `pull` does, so that a first
setup is one command. `--no-model` installs only the engine. Note that the model is about 22 GB:
`--no-model` is the option to use on a metered connection, or when the weights are being acquired
another way.

## `pull`

```bash
bora pull
bora pull qwen
```

Downloads **everything the model needs** — the weights and the vision projector — into the managed
store at `<data root>/models`, and verifies each against its locked size and SHA-256. The URL
contains the pinned revision, so a moved branch or a re-uploaded file cannot change what arrives.

The model name is optional because this distribution pins exactly one model; `qwen` and no argument
are the same request, and any other name fails immediately instead of being read as the default.
There is no third artifact to fetch: MTP is a property of these weights, not a separate download,
and the launcher enables it through engine flags.

On a terminal each artifact shows transferred bytes against the total, the measured rate, and a
computed ETA; redirected output prints nothing per chunk. Bytes are written to a partial file and
published by atomic rename, so an interrupted download never leaves something that looks complete.
Rerunning after an interruption resumes the work at file granularity: a complete, verified artifact
is recognized and skipped.

A successful download also writes the verification receipt, so the first launch afterwards starts
without rehashing about 21 GiB.

## `rm`

```bash
bora rm
bora rm qwen
bora rm --keep-hf
bora rm --dry-run
```

Deletes everything `pull` installed — both artifacts, their verification receipts, and the store
directory once it is empty — and reports the space freed. The model name is optional on the same
terms as `pull`. Nothing this tool did not write is touched without the second question below. It asks up to two questions, and both
default to no:

1. the copies in the managed store, which belong to this tool;
2. the copies in the Hugging Face cache, which is **shared with every other tool on the machine**.

Answering yes to the first never implies the second. `--keep-hf` skips the second question
entirely, and `--dry-run` lists every file and byte count without asking or deleting anything.

Cache deletion cannot leave the pinned snapshot of the locked repository: it removes only the
artifacts `engine.lock` names, follows a symlinked entry no further than that repository's own
`blobs/`, keeps a blob another snapshot still references, refuses a symlinked cache directory, and
prunes only already-empty directories. When the last snapshot goes, the cached repository goes with
it, `refs` included: what those refs name is a revision whose files no longer exist. A repository
that still holds another revision keeps everything, and repositories belonging to other tools are
never examined. Nothing is ever written into that cache.

## `pi`

```bash
bora pi
bora pi --print
bora pi --install
```

Writes one provider named `bora` into pi's own model store, `~/.pi/agent/models.json`: the loopback
base URL built from the configured port, a placeholder API key that the managed server ignores, and
the model id `Qwen 3.6` — the same name `/v1/models` reports. The context window comes from this
machine's local calibration record when one applies, and from the verified baseline otherwise.

The entry is shown before anything is written, the confirmation defaults to no, the previous file
is kept as `models.json.bak`, and the replacement is atomic. Every other provider in that file is
preserved; a file that cannot be parsed is reported rather than overwritten.

`--print` shows the entry and writes nothing, which is also the way to configure any other
OpenAI-compatible client by hand. `--install` runs
`npm install -g --ignore-scripts @earendil-works/pi-coding-agent` after showing the command and
asking: this project pins no digest for pi and does not claim to verify it. Without `--install`, an
absent pi is reported with the vendor's instructions for Ubuntu and Windows.

Afterwards, with `bora coding` running:

```bash
pi --provider bora --model "Qwen 3.6"
```

## Run modes

```bash
bora coding [--force]
bora studio [--force]
bora vstudio [--force]
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
only when `open_browser=true`. `/v1/models` reports the model as `Qwen 3.6`, which is the alias the
engine is launched with; that name is what a client sends back in a request.

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
bora status
```

Shows the service, PID, mode, backend, port, and log. It first verifies each entry through
`pid + create_time`; dead entries, reused PIDs, and PIDs this account can no longer open are
removed with a warning. Malformed JSON state is quarantined as `services.corrupt-<timestamp>.json`.
No services at all is a success with exit code 0.

It also inspects the trial roots of a calibration run that never finished, so a server left behind
by an interrupted `calibrate` is visible here instead of only in the task manager.

## `stop`

```bash
bora stop
```

Stops only processes whose identity matches the state. It waits up to 10 seconds after `terminate`,
then uses `kill` and waits up to 5 seconds. It is idempotent: no services returns 0. Do not delete
`services.json` by hand while the process is alive.

Like `status`, it covers the trial roots of an unfinished calibration, so it is the command that
ends a server an interrupted run left holding VRAM. Running it while a calibration is in progress
therefore stops that calibration's current trial.

## `calibrate`

```bash
bora calibrate --mode <coding|studio|vstudio|all> [--preference <envelope>]
```

The command shows a preflight and asks for confirmation before starting any process. It measures
one `fast`, `balanced`, or `max-context` cell per selected mode, writes that cell into one candidate
record per completed mode, and activates it atomically unless told otherwise.

| Option | Effect |
|---|---|
| `--mode <id\|all>` | the packaged mode to measure, or every mode (required) |
| `--preference fast\|balanced\|max-context` | optimization rule measured for the cell, default `balanced` |
| `--no-activate` | keeps the new records as candidates, leaving the active ones untouched |
| `--activate` | promotes candidates measured earlier, without new trials |
| `--target-ctx N` | collapses the context ladder onto a single approved step |

```bash
bora calibrate --mode all
bora calibrate --mode coding --preference fast
bora calibrate --mode all --preference max-context --no-activate
bora calibrate --mode all --activate
bora calibrate --mode coding --target-ctx 98304
```

Allowed targets: `131072`, `98304`, `65536`, `49152`, `32768` — the same steps the automatic ladder
descends. The approved scale also names `16384` and `8192`, but the pinned quick-bench long request
does not fit in them, so asking for one is refused before any process starts.
`--activate` cannot be combined with `--target-ctx`, and `--activate` and
`--no-activate` are mutually exclusive. `--activate` cannot relabel a candidate with
`--preference`; each conflict is an input error reported before any process starts.

`--mode all` applies the same preference to all three modes. Run individual mode commands when,
for example, `coding` should retain `fast`, `studio` `balanced`, and `vstudio` `max-context`.

`max-context` is the cheapest preference to measure: the ladder descends, so the first context that
yields a sample already wins and the remaining steps are skipped. `fast` and `balanced` compare
latency across contexts and walk the whole ladder.

`--mode` and `--preference` are ordinary Typer options; the other three are handled by the command's
specialized parser, so `calibrate --help` lists them in the epilog rather than in the generated
table. The syntax above is the one actually supported.

Trial reserves, written into every record: 0.5 GiB VRAM, 2.0 GiB RAM, 0.125 GiB release tolerance.

On an interactive terminal the run shows a live bar with the phase, the trial, the elapsed time, and
an estimate learned from the current phase; redirected output stays line-oriented, one line per
completed trial. Every phase total is a cap (`<=N`), not a schedule or a promise. The final summary
prints the one measured cell per completed mode and reports its observed RAM and VRAM minima.

Calibration uploads nothing, does not modify `config.toml`, and installs neither the model nor the
engine. Trials use the configured port when it is free and fall back to a system-assigned loopback
port when it is busy; that fallback does not apply to the three normal launches.

Algorithm and record details: [Calibration](calibration.md).

## `update`

```bash
bora update --check
bora update
```

Compares the installed version with the newest GitHub Release and, unless `--check` was given,
installs it. Both forms print the installed and the published version first; when nothing newer is
published, both exit with 0 and change nothing. An update never downgrades: only a strictly newer
`major.minor.patch` is installed.

The installation repeats the trust chain of the documented manual install. The command downloads
the release `SHA256SUMS` and the release wheel over HTTPS, refuses any hop that leaves HTTPS,
compares the wheel's SHA-256 with the manifest, and only then hands the verified file to
`uv tool install --force --python 3.12.13`. The wheel is kept under the managed cache root.

**The managed engine is not reinstalled.** It lives under the data root and survives the tool
replacement untouched. Before scheduling the installation, `update` reads `engine.lock` out of the
downloaded wheel and reports one of three things: that the new version keeps the active engine
release, that it pins a different one and `bora engine install` is required afterwards, or that the
lock could not be read and `bora engine status` should be checked. Calibration records, the
configuration, and the model are equally untouched.

Two situations are refused with exit code 1: a live managed service, because the running launcher
still holds the environment uv has to replace, and an installation `uv tool` does not own — a
development checkout for example — which must use the documented installer instead.

Because Windows cannot replace the environment of the process that is still running, `uv` is invoked
by a helper that waits for this command to exit, exactly as `uninstall` does. Exit code 0 therefore
reports that the installation was *scheduled*, not that uv succeeded: uv writes its own output to
the same terminal a moment later, and `bora --version` is the confirmation.

## `uninstall`

```bash
bora uninstall
```

Refuses to proceed while a live managed service exists. It shows the configuration, data, cache,
state, and the current Python installation, then asks for a single confirmation. If the command
comes from the supported `uv tool` installation, it also removes the Python tool through uv as soon
as the process exits; uv itself stays unchanged. A Python installation not managed by uv is reported
explicitly and is not removed on a guess. A normal cancellation deletes nothing and exits with 0;
`Ctrl-C` exits with 130.

The model store is inside the data root, so its weights go with it. Weights that also exist in the
Hugging Face cache are offered afterwards as a **separate question**, defaulting to no and using
the same confinement rules as `rm`. It is asked only once the managed roots are actually gone, and
a failure or refusal there leaves the completed uninstall successful.

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
