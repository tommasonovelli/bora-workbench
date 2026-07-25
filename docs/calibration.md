# Local calibration

## In brief

Calibration finds a configuration suited to **this machine**. It does not change the model and does
not improve answer quality: it finds how much context your hardware can actually serve, and how fast
each feasible configuration responds.

You do not need to know any `llama.cpp` parameter to start:

```bash
qwen-launcher calibrate --mode all
```

The command:

1. checks the model, the engine, memory, and concurrent processes;
2. prints exactly what it will run and asks for confirmation;
3. starts many short-lived servers, so it takes from tens of minutes to hours;
4. measures `coding`, `studio`, and `vstudio`;
5. writes a private record per completed mode;
6. activates those records by default, so the next launch uses them.

It uploads nothing, never edits `config.toml`, and publishes no result.

## What you get: three envelopes per mode

A single run measures **three** launch envelopes for each mode and stores all of them in the record:

| Envelope | What it optimizes |
| --- | --- |
| `fast` | the lowest end-to-end latency on a short prompt, among configurations with `ctx ≥ 16384` |
| `balanced` | the largest context whose short-prompt latency stays within `1.10×` that of `fast` |
| `max-context` | the largest feasible context, ordered by throughput, then memory margin, then caution |

Only one of the three drives a launch: the **active preference**, chosen with `--preference`
(default `balanced`). The other two stay in the record, so switching later costs one command
instead of a new measurement run.

## Essential terms

- **Baseline**: a verified but non-optimized configuration (`ctx=8192`; on CUDA `n_cpu_moe=48`). It
  makes the launcher usable before any calibration.
- **Envelope**: the launch parameters chosen for one mode, mainly `ctx` and, on CUDA, `n_cpu_moe`.
- **`ctx`**: the server's context window limit, in tokens.
- **`n_cpu_moe`**: how many MoE blocks stay on the CPU. Lower values use more VRAM; higher values
  move weights and work toward RAM and CPU. Throughput is not assumed to be monotonic in it.
- **Probe**: a short feasibility trial. It answers one question — does this configuration start and
  serve at all — and nothing about speed.
- **Sample**: a feasible configuration measured with the quick-bench, so it can be compared.
- **Local record**: a private JSON holding the measurements, the machine identity, and the three
  envelopes.
- **Candidate**: a valid record that launches do not use yet.
- **Active record**: the only record that can enter a launch plan.
- **Headroom**: memory still free beyond the measured requirement.

## Before you start

You need:

- the default model and, for `vstudio`, the mmproj already present and verifiable;
- a compatible `llama.cpp b10011` already installed;
- at least 28 GiB of total RAM and 22 GiB available at preflight;
- no managed service running;
- on CUDA, a single NVIDIA GPU and no other GPU-intensive workload.

Check first:

```bash
qwen-launcher validate
qwen-launcher doctor
qwen-launcher engine status
qwen-launcher status
```

Calibration uses `llama_port` when it is free; when it is busy, each trial picks a temporary port on
`127.0.0.1`. Ordinary launches stay strict about the configured port.

### Concurrent GPU contexts

Outside WDDM, a compute process that is already present makes the measurement unreliable and stops
the run. On Windows/WDDM some desktop processes are unavoidable, so the launcher captures the
compute-process population once for the whole run, using PID, creation time, and opaque executable
identity. A respawn of the same executable is tolerated within the initial multiplicity; new files,
unreadable identities, or extra instances invalidate the run. None of this produces hardcoded OS
profiles: the differences enter the decision only through the RAM and VRAM observed on the spot.

## Everyday use

Calibrate every mode and activate the results:

```bash
qwen-launcher calibrate --mode all
```

Calibrate a single mode:

```bash
qwen-launcher calibrate --mode coding
```

Pick which envelope the records will launch with:

```bash
qwen-launcher calibrate --mode all --preference fast
qwen-launcher calibrate --mode all --preference max-context
```

On an interactive terminal the CLI shows a bar, the elapsed time, the running trial, and a remaining
time learned from the current phase alone. Every phase total is a **cap**, not a schedule: the count
reads `≤N` and the search usually finishes below it. When output is redirected, one stable line per
completed trial is written instead.

A trial crash is isolated from any production service; its reason and logs are kept.

`coding` and `studio` share one hardware search, while `vstudio` runs its own. These groups share
hardware, not a decision: if one of them cannot finish, the modes that already completed still get
their records written and activated. The summary then names the group that produced nothing, and
the command still exits with an error, because the run was not complete. Re-run just that mode:

```bash
qwen-launcher calibrate --mode vstudio
```

On a nearly full GPU the memory boundary can move between two measurements of the same
configuration: a point the search accepted may violate the VRAM reserve when it is re-measured. Such
a point can never become a launch envelope, so it is dropped — during the search the point is simply
not used, during confirmation the surviving finalist is confirmed, and at the gate the rival is
tried instead. None of these ends the mode.

When it finishes, check the result and launch:

```bash
qwen-launcher doctor
qwen-launcher coding
```

If the active record is valid and the headroom is sufficient, startup reports
`local-calibration-record`; otherwise it explains why and falls back to the baseline.

## Measuring without activating

To experiment, or to prepare evidence before committing to it:

```bash
qwen-launcher calibrate --mode all --no-activate
```

Results are written as candidates:

```text
data_dir()/calibration/records/<mode>.candidate.json
```

Launches keep using the previous active record, or the baseline. After reviewing `doctor`, promote
the candidates without repeating any trial:

```bash
qwen-launcher calibrate --mode all --activate
```

Promotion is atomic. If an active record already exists, a copy of it is kept in:

```text
<mode>.previous.json
```

There is exactly one previous slot and no automatic rollback command. Do not rename or hand-edit
records.

## Pinning one context

The search descends this ladder:

```text
131072 → 98304 → 65536 → 49152 → 32768 → 16384 → 8192
```

You can collapse it onto a single approved step:

```bash
qwen-launcher calibrate --mode coding --target-ctx 98304
```

Allowed values: `131072`, `98304`, `65536`, `49152`, `32768`, `16384`, `8192` — every step of the
ladder. At a fixed context the three envelopes are still measured and differ only in `n_cpu_moe`, so
`fast` and `max-context` often coincide there; they still optimize different metrics (end-to-end
latency versus decode throughput).

`131072` is the ceiling this protocol searches, not a claim about what the model supports.

## Worked examples

```bash
# Everything, activated, with the default balanced envelope
qwen-launcher calibrate --mode all

# Coding only, recording `fast` as the envelope launches will use
qwen-launcher calibrate --mode coding --preference fast

# Measure everything but leave the active records untouched
qwen-launcher calibrate --mode all --preference max-context --no-activate

# Promote candidates measured earlier, without re-running any trial
qwen-launcher calibrate --mode all --activate

# Lowest latency at a fixed context
qwen-launcher calibrate --mode coding --target-ctx 65536 --preference fast

# Highest throughput at that same fixed context
qwen-launcher calibrate --mode coding --target-ctx 65536 --preference max-context
```

Constraints: `--activate` does not combine with `--target-ctx`, and `--activate` and `--no-activate`
are mutually exclusive. Both are reported as input errors before any process starts.

## How the search works

This section explains the algorithm; you do not need it in order to run the command.

`coding` and `studio` share one hardware search: same model, same backend, no mmproj, same
speculative decoding, so their feasible region is the same and measuring it twice would only cost
time. `vstudio` searches on its own, because it loads the projector and disables speculative
decoding.

For each context on the ladder, the search:

1. probes the conservative offload position `n_cpu_moe = 41` once;
2. if VRAM refuses even that, declares the whole context infeasible — one probe — and descends;
3. if RAM refuses it, descends toward more aggressive offload until it finds a feasible anchor;
4. bisects the VRAM side below that anchor to find the boundary, the least offload that still runs;
5. measures the boundary, `boundary+2`, and the conservative anchor with the quick-bench.

Feasibility is treated as a **class**, not a number: a probe either started and served or it did
not, and an out-of-memory failure is read from the trial's own logs to tell a VRAM refusal from a
RAM one. A partial load invents no memory peak.

Throughout, RAM and VRAM are polled every 250 ms. Every trial must keep at least **2.0 GiB** of RAM
available and, on CUDA, **0.5 GiB** of VRAM free, and must release VRAM within **0.125 GiB** of the
baseline after stopping. These reserves are written into the record, so a record is always
re-evaluated against exactly the margins it was measured with.

The three envelopes are then selected from the samples, confirmed with two paired `A→B`/`B→A`
rounds — a third round only when the first two disagree or disperse — and each one finally passes a
gate in a fresh process: a smoke request at about 80% of the context **measured in tokens**, a
four-turn conversation, and, for `vstudio`, the pinned image request.

A context the hardware cannot afford is rejected after a single probe, so a small card spends most
of the run on the steps it can actually serve. As a measured reference, on an RTX 2060 SUPER (8 GiB)
with 32 GiB of RAM, `--mode all` costs roughly **100 fresh processes and a little over two hours**,
split about evenly between the shared text group and `vstudio`. Your hardware will differ: a card
that can hold more contexts spends more trials measuring them and fewer rejecting them.

On CPU there is no offload axis to search: the baseline context is confirmed, `n_cpu_moe` is
recorded as null, and the same envelope is written for all three preferences.

### The quick-bench

Each sample runs, against a fresh server:

1. one warm-up request, excluded from the results;
2. three short non-cached requests (128 completion tokens each);
3. one request of about 8K prompt tokens (64 completion tokens).

Every metric comes from the response `timings` and the wall clock — no log parsing. The request
payloads are byte-pinned in the wheel and checksummed, because changing them would change what is
measured. Tok/s describes the envelope's speed under the observed conditions; it is not a semantic
quality score and not a promise about another machine.

## Records and reuse

An active record is revalidated on every launch. All of this must match:

- the record schema and its internal consistency (reserves, active envelope);
- the model, filename, and digest;
- the engine release, commit, and command-contract digest;
- the mode and the backend;
- the OS, CPU, GPU, driver, and stable hardware identity;
- the memory available right now.

Recorded total RAM stays exact, but the comparison tolerates up to 1 MiB of difference to absorb
reporting noise. Reuse additionally requires the measured RAM need plus the recorded RAM reserve
and, on CUDA, the measured VRAM need plus the recorded VRAM reserve.

A candidate, a previous, an invalid, or an unreadable record never drives a launch. A record written
by an older launcher is diagnosed as superseded rather than misread; the remedy is to re-run
`calibrate`, never to convert files by hand.

## Private files

Records:

```text
data_dir()/calibration/records/
```

Logs and detailed evidence of the most recent run:

```text
data_dir()/calibration/evidence/<run-id>/
```

Once a new run is preserved, the launcher deletes only the previous managed evidence directories.
These files can contain operational details and must not be published without review.

## Shared evidence and its limits

The wheel distributes a `calibration-policy/v2` policy and a `calibration-report/v2` report covering
one machine only:

- Windows 11 build 10.0.26200;
- CUDA, NVIDIA driver 610.47;
- RTX 2060 SUPER 8 GiB;
- 31.92 GiB RAM;
- all three modes.

This evidence is descriptive. No value in it becomes a launch plan on your machine, and the launcher
never derives an envelope from it: your hardware runs the full search regardless. The overall status
stays `GATE-PARTIAL` — materially different hardware is still missing from the public record.

The checksummed sources live in
[`evidence/calibration/windows-11-rtx-2060-super-v3/`](../evidence/calibration/windows-11-rtx-2060-super-v3/).

## Contributing new evidence

Publication is manual: the launcher performs no logins, uploads, commits, remote branches, issues,
or pull requests. The public schema currently describes the historical reference method only; a
contribution
based on the current protocol needs a separate declarative step with its own schema, privacy review,
manifest, and checksums.

Prepare it without activating anything:

```bash
qwen-launcher calibrate --mode all --no-activate
```

Keep both successes and failures private until reviewed, and strip hostnames, usernames, serial
numbers, UUIDs, absolute paths, credentials, prompts, and raw logs.

Pull request checklist:

- [ ] the versioned public schema and the documented method are consistent;
- [ ] successful and failed runs reported without reconstructing missing fields;
- [ ] `privacy_reviewed=true` only after reviewing the final bytes;
- [ ] explicit scope, portability limit, SHA-256, and manifest;
- [ ] a declarative PR with no changes to the Python core;
- [ ] `qwen-launcher validate`, Ruff, pytest, build, and wheel verification green.

**Next:** [Operations and diagnostics](operations.md)
