# Local calibration

## In brief

Calibration exists to find a configuration suited to **this machine**. It does not change the model
and does not improve answer quality: it first maximizes the feasible context, then compares
throughput and memory margin inside the domain of protocol v5.

You do not need to know the `llama.cpp` parameters to get started:

```bash
qwen-launcher calibrate --mode all
```

The command:

1. checks the model, engine, memory, and concurrent processes;
2. shows what it will run and asks for confirmation;
3. starts several temporary servers, so it can take from many minutes to hours;
4. measures `coding`, `studio`, and `vstudio` separately;
5. saves a private record for every completed mode;
6. activates the records by default, so they are evaluated on the next launch.

It performs no uploads, does not modify `config.toml`, and publishes no results.

### Engine contract compatibility note

Preparing the contract for the cross-context spike changes the `command_contract_sha256`. Existing
local `calibration-record/v2`, `/v3`, and `/v4` records stay readable for diagnostics, but they are
no longer reusable: re-run `calibrate`. Public v3 seeds remain nothing more than hints for probe
ordering and never become envelopes.

`vstudio` keeps `--mmproj` but emits neither `--spec-type` nor `--spec-draft-n-max`: the pinned model
card does not declare the vision+MTP combination supported, even though the local Spike 0 completed
it. This conservative choice stays in place until a dedicated spike provides new evidence.

With the `mode/v2` migration (0.1.4) the three modes also emit `--min-p`, `--presence-penalty`,
`--repeat-penalty`, and `--reasoning` (coding `on`; studio and vstudio `off`); temperature, top-p,
and top-k are unchanged. These tokens come from the mode content and do not change the
`command_contract_sha256`.

The default calibration remains `calibration/v5`. `calibration/v6-lite` is available as an **opt-in
experimental** protocol (`--protocol v6`): it was implemented on the maintainer's decision (D-063)
before the GO verdict of the cross-context spike, which remains the precondition for promoting it to
the default. See [calibration/v6-lite (experimental)](#calibrationv6-lite-experimental).

## Essential terms

- **Baseline**: a verified but non-optimized configuration (`ctx=8192`; on CUDA `n_cpu_moe=48`). It
  makes the launcher usable without calibration.
- **Envelope**: the pair of performance parameters chosen for a mode, mainly `ctx` and, on CUDA,
  `n_cpu_moe`.
- **`ctx`**: the server's context window limit, in tokens.
- **`n_cpu_moe`**: the number of MoE blocks left on the CPU; lower values use more VRAM, higher
  values move weights and work toward RAM and CPU. Throughput is not assumed to be monotonic.
- **Local record**: a private JSON that keeps the measurements, machine identity, and selected
  envelope.
- **Candidate**: a valid record that launches do not use yet.
- **Active record**: the only record that can enter the launch plan.
- **Shared seed**: a probe-ordering hint that comes from public evidence; it is not a configuration
  to copy.
- **Headroom**: memory free beyond the measured requirement.
- **Benchmark**: a repeatable measurement of an already chosen envelope; on its own it is not a
  calibration.

## Before you start

You need:

- the default model and, for `vstudio`, the mmproj already present and verifiable;
- a compatible `llama.cpp b10011` already available;
- at least 28 GiB of total RAM and 22 GiB available at preflight;
- no active managed service;
- on CUDA, a single NVIDIA GPU and no concurrent GPU-intensive workload.

Check first:

```bash
qwen-launcher validate
qwen-launcher doctor
qwen-launcher engine status
qwen-launcher status
```

Calibration uses `llama_port` when it is free. On the current branch, if the port is busy each trial
picks a temporary port on `127.0.0.1`; ordinary launches stay strict about the configured port. This
fix is not present in the public `0.1.0` artifacts.

### Concurrent GPU contexts

Outside WDDM, a compute process that is already present makes the measurement unreliable and blocks
the run. On Windows/WDDM some desktop processes are unavoidable: the launcher captures an initial
population for the whole run using the PID, creation time, and opaque executable identity. A respawn
of the same executable is allowed within the initial multiplicity; new files, unreadable identities,
or additional instances invalidate the run. The Ubuntu/Windows differences and the desktop load
produce no hardcoded OS profiles: they enter the decision through the RAM/VRAM and baselines
observed on the spot.

## Normal use

Calibrate every mode and activate the results:

```bash
qwen-launcher calibrate --mode all
```

Calibrate a single mode:

```bash
qwen-launcher calibrate --mode coding
```

On an interactive terminal the CLI shows a spinner, a bar, the elapsed time, the running trial, and
a remaining time learned from the current phase alone. Screening waits for two processes and uses
the median; confirmation, which has homogeneous trials and an exact total, shows a first ETA after
the first trial and stabilizes it with the median. In screening, `14` is a cap: the count uses `≤14`
and the time is a projection up to the cap, not a guaranteed limit. If the output is redirected, one
stable line per completed trial is kept. At the end, the summary explains the selection rule and the
lowest measured RAM/VRAM values.

A trial crash is isolated from the production service; the reason and the logs are kept.

When it finishes, check:

```bash
qwen-launcher doctor
qwen-launcher coding
```

If the record is valid and has enough headroom, startup shows `local-calibration-record`; otherwise
it explains why and uses the baseline.

## Measuring without activating

For an experiment, or to prepare evidence:

```bash
qwen-launcher calibrate --mode all --no-activate
```

The results are written as:

```text
data_dir()/calibration/records/<mode>.candidate.json
```

Launches keep using the previous active record or the baseline. After checking `doctor`, promote the
candidates without repeating the trials:

```bash
qwen-launcher calibrate --mode all --activate
```

Promotion is atomic. If an active record already exists, a copy of it is kept in:

```text
<mode>.previous.json
```

There is a single previous slot; there is no automatic CLI rollback command. Do not rename or edit
records by hand.

## Explicit context for expert users

The normal search tries, in order:

```text
131072 → 98304 → 65536 → 49152 → 32768 → 16384 → 8192
```

You can pin one of the approved targets:

```bash
qwen-launcher calibrate --mode coding --target-ctx 98304
```

Allowed values: `131072`, `98304`, `65536`, `49152`, `32768`, `16384`, `8192`. All of them also
belong to the automatic scale; `--target-ctx` exists to pin one of them for a separate measurement.
Candidates are always compared at the same context.

`131072` is the automatic ceiling of the current protocol, not proof that the model does not support
larger contexts. "Best fit" therefore means the best inside the v5 domain listed above.

## How the v5 search works

This section explains the algorithm; it is not required in order to use the command.

The objective is lexicographic:

1. the largest feasible context;
2. the throughput confirmed at that context;
3. the larger memory margin;
4. the more conservative configuration.

On CUDA the `n_cpu_moe` domain is read from the GGUF metadata and is `[0, block_count]`; for the
pinned model the expected and verified maximum is 41. A shared report can suggest the first point,
but it does not narrow the domain.

For each mode the calibrator:

1. descends the context scale only when the most conservative configuration is not feasible;
2. looks for the CUDA boundary with at most 14 probes and fresh processes;
3. monitors RAM and VRAM every 250 ms;
4. requires at least 2.0 GiB of available RAM during every trial;
5. on CUDA requires at least 0.3 GiB of free VRAM (about 307 MiB) and release within 0.125 GiB of
   the baseline;
6. considers monotonicity only between completed probes; a partial OOM invents no peak;
7. picks the first feasible value at the boundary and, when available, the single more conservative
   neighbor;
8. confirms them in two paired rounds: `A→B` and `B→A`;
9. runs a full `benchmark/v1` in each of the four startups;
10. uses throughput only when the same finalist wins both rounds; otherwise it prefers margin and
    caution.

A VRAM baseline drift beyond 0.125 GiB disables winning by throughput, but it does not eliminate a
finalist that respected the absolute reserves. Telemetry such as utilization, clocks, temperature,
power, and throttling is collected when available only to explain the evidence; it introduces no
thresholds.

On CPU there is no verified tuning axis: by default v5 confirms the engine baseline at `ctx=8192`
instead of simulating a search. An expert `--target-ctx` can pin one of the other approved values,
but it introduces no automatic axis.

The CUDA search therefore finds a memory boundary and compares two adjacent values: it performs no
global `n_cpu_moe` sweep and does not prove that no distant value has higher throughput. v5 keeps
the search, benchmark, and finalists of v4, adds the 96K and 48K steps, and raises the cap from 12
to 14 to keep the worst-case budget sufficient. It produces `calibration-record/v4`; historical
v2/v3 records stay readable.

## `benchmark/v1`

Every valid session runs:

1. a full warm-up excluded from the results;
2. five measured requests;
3. exactly 256 completion tokens per request;
4. `max_tokens=256`, `ignore_eos=true`, and seed `424242`;
5. a check of `finish_reason=length`, the token count, and the timing;
6. a minimum, median, and maximum summary.

The prompt and request resources are immutable in the wheel. Tok/s measures the envelope's speed
under the observed conditions, not semantic quality and not a promise for another machine. The
current CLI exposes no standalone `benchmark` command.

## Records and reuse

An active record is revalidated on every launch. These must match:

- the schema and the reconstruction of probes, sessions, medians, and selection;
- the model, filename, and digest;
- the release, commit, and engine contract digest;
- the mode and backend;
- the OS, CPU/GPU, driver, and stable hardware identity;
- the current available memory.

The recorded total RAM stays exact; on the current branch the comparison allows at most 1 MiB of
difference to absorb the observed reporting noise. Reuse requires the RAM requirement plus the
recorded reserve and, on CUDA, the VRAM requirement plus 0.3 GiB for v3/v4 records, or 0.5 GiB for a
historical v2 record. The migration therefore does not weaken the headroom of already measured
records.

A candidate, previous, invalid, or unsupported-schema file never drives a launch. The
`calibration-record/v2`, `/v3`, and `/v4` records stay supported and readable, but the ones created
with the previous contract do not match the current digest and therefore do not drive a launch;
`/v1` is diagnosed as superseded. The remedy is to re-run `calibrate`, not to convert files by hand.

## Private files

The records live in:

```text
data_dir()/calibration/records/
```

The logs and detailed evidence of the last run live in:

```text
data_dir()/calibration/evidence/<run-id>/
```

Once a new run has been preserved, the launcher deletes only the previous evidence directories with
a managed UUID name. These files can contain operational details and must not be published without
review.

## Shared evidence and the empirical limit

The wheel distributes a `calibration-policy/v2` policy and a `calibration-report/v2` report of the
historical v3 method. v5 uses that report only as an ordering seed; it does not present it as proof
of the new reserve. The report really covers a single scope:

- Windows 11 build 10.0.26200;
- CUDA, NVIDIA driver 610.47;
- RTX 2060 SUPER 8 GiB;
- 31.92 GiB RAM;
- all three modes.

The overall status remains `GATE-PARTIAL`: the maintainer attested real v4 Gates on Ubuntu and
Windows before 0.1.1, but materially different hardware is still missing and the Windows v4 Gate was
never turned into public evidence. The observed values are not transferred. The loader extracts only
`n_cpu_moe` as an ordering seed for the exact model, engine, backend, and mode; the user's machine
still runs the full search.

The checksummed sources are in
[`evidence/calibration/windows-11-rtx-2060-super-v3/`](../evidence/calibration/windows-11-rtx-2060-super-v3/).

## Contributing new evidence

Publication is manual: the launcher performs no logins, uploads, commits, remote branches, issues,
or pull requests. The current public contract describes only v3; do not convert a private v5 record
into a v2 report. A v5 contribution requires a separate declarative step with a new schema, privacy
review, manifest, and checksums.

To prepare the Gate without activating the results:

```bash
qwen-launcher calibrate --mode all --no-activate
```

Keep both the successful outcome and the failures privately, without hostnames, usernames, serial
numbers, UUIDs, absolute paths, credentials, prompts, or raw logs. The Windows v4 Gate attested for
0.1.1 is no substitute for a future redacted and manifested public contribution.

Pull request checklist:

- [ ] the versioned public schema and the v5 method are consistent;
- [ ] successful and failed runs reported without reconstructing missing fields;
- [ ] `privacy_reviewed=true` only after reviewing the final bytes;
- [ ] explicit scope, portability limit, seed, SHA-256, and manifest;
- [ ] a declarative PR with no changes to the Python core;
- [ ] `qwen-launcher validate`, Ruff, pytest, build, and wheel verification green.

## calibration/v6-lite (experimental)

> [!WARNING]
> **`--protocol v6` does not work yet.** The protocol ships as code, but its real trial adapter has
> never been validated on hardware: only the search, selection, confirmation, gate, and record logic
> is exercised, by offline tests with fakes. Use `calibration/v5` — the default — for any real
> calibration. The section below describes the intended design, not behavior you can rely on today.

`calibration/v6-lite` is an **opt-in** protocol (`--protocol v6`); `calibration/v5` remains the
default. It was implemented on a recorded maintainer decision (D-063) before the GO verdict of the
cross-context spike: promoting it to the default remains a human decision recorded in
`IMPLEMENTATION_SPEC.md`, never declared by the agent.

Instead of a single envelope, v6-lite measures three envelopes per mode and writes all of them into
the record:

- **`fast`** — the lowest end-to-end median for the short prompt with `ctx ≥ 16384`;
- **`balanced`** — the largest context whose short end-to-end stays within `1.10×` that of `fast`;
- **`max_context`** — the largest feasible context, with the v5 throughput→margin→caution ordering.

Pipeline: a **shared** hardware search for `coding`+`studio` (same model, backend, no mmproj, same
MTP) over the contexts `131072 → 65536 → 32768` (refining `98304`/`49152` adjacent to the winner);
`vstudio` has its own search (`--mmproj`, speculative disabled). For every step, a conservative probe
at `n_cpu_moe = 41`, then bisection of the VRAM side only; the `boundary`, `boundary+2`, and
conservative-point samples are measured with the **quick-bench** (1 warm-up + 3 short non-cached
requests + 1 request of about 8K). The selection is confirmed by a 2-round ABBA with a third round
only when ambiguous, then by a final per-envelope gate (smoke at about 80% of the context, a 4-turn
multi-turn, vision for `vstudio`). Expect roughly **40–60 processes** for `--mode all`.

The v6 trial reserves, written into the record: **0.5 GiB VRAM, 2.0 GiB RAM, 0.125 GiB** release
tolerance. At launch **only** the `active_preference` envelope is evaluated, with its measured
requirements; if the headroom is insufficient the baseline is used (`ctx=8192`, `n_cpu_moe=48`).
`--preference` pins the active envelope in the record (default `balanced`) and never modifies
`config.toml`; `--target-ctx` collapses the scale onto a single step. The record is
`calibration-record/v5`: the same identity and digests as v4, the three envelopes, the thresholds,
the reserves, and the selection inputs (per-round medians) sufficient to reconstruct the choice;
probes, discards, and logs stay in the `evidence/` tree.

### Examples

```bash
# Measure the three envelopes for every mode and activate the `balanced` envelope (default)
qwen-launcher calibrate --mode all --protocol v6

# Coding only, with the `fast` envelope as the active preference in the record
qwen-launcher calibrate --mode coding --protocol v6 --preference fast

# Measure without activating: writes the candidates and leaves the active records untouched
qwen-launcher calibrate --mode all --protocol v6 --preference max-context --no-activate

# Collapse the search onto a single approved context (131072, 98304, 65536, 49152, 32768)
qwen-launcher calibrate --mode coding --protocol v6 --target-ctx 65536

# Maximum performance at a fixed context: `--target-ctx` and `--preference` combine.
# fast = lowest latency at that context; max-context = highest throughput at that context.
qwen-launcher calibrate --mode coding --protocol v6 --target-ctx 65536 --preference fast
qwen-launcher calibrate --mode coding --protocol v6 --target-ctx 65536 --preference max-context

# Promote already measured v6 candidates, without re-running the trials
qwen-launcher calibrate --mode coding --protocol v6 --activate
```

With `--target-ctx` the three envelopes are still measured at the same context and differ only in
`n_cpu_moe`: at a fixed context `fast` and `max-context` often coincide, but they optimize different
metrics (end-to-end latency versus decode throughput).

After calibration, `doctor` shows the active envelope and the normal launch commands use the
`active_preference` envelope (or the baseline when the headroom is insufficient):

```bash
qwen-launcher doctor      # active envelope parameters and record status
qwen-launcher coding      # launches using the recorded active_preference envelope
```

Constraints: `--preference` is rejected without `--protocol v6`; `--activate` does not combine with
`--target-ctx`; `--activate` and `--no-activate` are mutually exclusive.

Note: only the search, selection, confirmation, gate, and record logic is covered, by offline tests
with fakes. The real trial adapter has **not** been validated on hardware, and `--protocol v6` does
not work yet — see the warning at the top of this section.

## v1 laboratory

`--protocol v1` remains available for explicit experiments and bundle compatibility. It requires
candidates and technical settings, measures only the supplied list, and produces a draft under
`data_dir()/calibrations/`. It does not monitor RAM, does not create a `calibration-record/v4`, and
does not activate results. For a new user the correct path is always the default v5 protocol.

**Next:** [Operations and diagnostics](operations.md)
