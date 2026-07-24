# Hardware calibration audit

Audit date: 2026-07-22. Release addendum: 2026-07-23. v5 scale addendum: 2026-07-23.

This document is the non-normative technical report required for the calibration review. It
describes sources, measurements, limits, and decisions; it does not replace
`IMPLEMENTATION_SPEC.md`, the locks, or the [current user guide](docs/calibration.md). It contains no
private reasoning or model transcripts: it keeps verifiable conclusions only.

## Summary outcome

The current `calibration/v5` method derives from v4 and is conservative within its own domain, but
its "best fit" name must be read precisely:

- it maximizes the context among `131072`, `98304`, `65536`, `49152`, `32768`, `16384`, `8192`;
- on CUDA it finds the memory boundary of `n_cpu_moe` and compares only that value and the more
  conservative neighbor;
- it measures RAM, VRAM, and ambient load locally, so it need not introduce hardcoded compromises
  for Windows or Ubuntu;
- it does not prove the global throughput optimum across all `n_cpu_moe` values;
- it does not calibrate threads, batch, MTP parameters, draft cache, sampling, or quantization;
- on CPU it confirms `ctx=8192` by default, while still accepting an explicit expert target.

The first change of the audit improved observability and interpretation. D-053 introduced v4 with a
0.3 GiB VRAM reserve and `calibration-record/v3`. D-055 now introduces v5: it adds 96K and 48K to
the scale, raises the cap to 14, and produces `calibration-record/v4`, without changing the boundary
search, ABBA, or the reserves. Historical v2/v3 records stay readable and keep their own reserves.
The other extensions listed here remain proposals, not implemented features.

## Source hierarchy

The decisions respect the repository order:

1. `engine.lock`, pinned content, and their digests;
2. measured evidence under `evidence/`;
3. schemas and tests;
4. `IMPLEMENTATION_SPEC.md`;
5. primary documentation for the exact version;
6. current upstream documentation, useful only for formulating new spikes.

For this audit the following stay unchanged:

- the `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M` model, revision
  `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`, and the pinned SHA-256;
- `llama.cpp b10011`, commit `bf2c86ddc0685f580595954056c2e77ebabfab4f`;
- MTP draft maximum 2, parallelism 1, flash attention, mmap, and the Q8 K/V cache on CUDA;
- the `n_cpu_moe=[0,41]` domain, the 2 GiB RAM reserve, and the 0.125 GiB release tolerance;
- the v4 VRAM reserve of 0.3 GiB; records produced by `calibration/v3` keep 0.5 GiB;
- the Calibration Gate status `GATE-PARTIAL`.

## Context analysis

The Qwen model card declares 262,144 native tokens and recommends at least 128K where possible. The
v4 ceiling of 131,072 satisfies that recommendation when feasible, but it uses only half of the
declared native context. Extending the domain automatically from a current page would be incorrect:
local compatibility also depends on the engine release, cache, MTP, quantization, and memory.

The v4 scale `128K → 64K` could skip a best fit at 96K. D-055 closes the gap with a new versioned
method: v5 automatically tries 98,304 and 49,152 tokens and uses a cap of 14 probes, sufficient for
the two additional steps and the full search over the `[0,41]` domain. Trying 262K automatically
stays outside the current protocol.

On CPU, 8,192 is the automatic baseline and not a technical maximum: the approved expert targets
remain valid. A real automatic search for the maximum CPU context is work for a later protocol.

## RAM, VRAM, and the operating environment

The fit cannot come from the nominal RAM+VRAM sum alone. Mmap, resident pages, the KV cache, MoE
weights, MTP, and desktop processes produce different and partly overlapping pressures. v4 makes the
decision from local measurements during every fresh process and revalidates the headroom when the
record is reused.

The environmental differences are already handled at the right point:

- outside WDDM, an unrelated compute context invalidates the run;
- on WDDM, the initial desktop population is identified and watched for the whole run;
- RAM and VRAM are sampled every 250 ms on both platforms;
- the current load can make an envelope infeasible without becoming a constant for that OS.

A fixed "Windows margin" or "Ubuntu margin" must therefore not be added. What is needed instead is
controlled repetitions on the same hardware/driver and on materially different hardware, because the
current public evidence covers a single Windows host.

## `n_cpu_moe` analysis

Lower values leave more MoE weights on the GPU; higher values save VRAM but increase the work and
traffic on the CPU/RAM side. Throughput is not assumed to be monotonic. v4 uses an adaptive search
to find the first feasible value, then confirms only `boundary` and `boundary+1` in ABBA order.

That is efficient for finding the memory boundary, not for proving maximum throughput over the
`[0,41]` domain. A value far from the boundary could be faster because of CPU, bandwidth, MTP, or
scheduling effects. A later protocol should separate:

1. the feasibility and context search;
2. controlled performance sampling of the feasible domain;
3. paired confirmation of the finalists produced by the second stage.

The design must first fix the budget, stop rule, noise handling, and record reconstruction; an
opportunistic sweep must not be bolted onto v4.

## Axes available but not calibrated

The help of the exact b10011 binary exposes real axes that the current contract leaves at their
defaults or does not use:

- generation and batch threads (`--threads`, `--threads-batch`);
- logical and physical batch (observed defaults 2048 and 512);
- threads, K/V cache, and `n_cpu_moe` of the draft model;
- the maximum number of MTP draft tokens;
- other kinds of speculative decoding.

Unsloth suggests 2 draft tokens as a good starting point, but explicitly states that the optimum is
hardware-dependent; its current MoE results also show smaller gains than dense models and generally
advise against more than 2 because of the drop in acceptance. The already pinned value of 2
therefore stays reasonable, but it is not proven optimal across the whole supported matrix. A future
spike must measure at least MTP off/1/2/3, acceptance, prefill, decode, RAM/VRAM, and the
interaction with `n_cpu_moe`, without extrapolating upstream percentages to the launcher.

The current model guide proposes different quantizations, among them `UD-Q4_K_XL` and NVFP4 on
Blackwell hardware. They do not override `UD-Q4_K_M` and the published digests: changing the
quantization means changing identity, requirements, quality, and gates, not silently optimizing the
0.1 calibration.

## Sampling divergence, kept separate from calibration

The exact model card recommends `min_p=0.0` for the documented profiles. The launcher's command
contract expands only temperature, `top_p`, and `top_k`; the b10011 help therefore reports its own
default `min_p=0.05`. This is a known divergence, but it does not prove the launcher should change
the value.

Adopting `min_p=0.0` would require a coordinated change of the mode content and the command
contract. The contract digest takes part in validation, so every local record would become
incompatible and would need recalibration. Furthermore `benchmark/v1`, with 256 tokens and
`ignore_eos`, measures throughput rather than quality or sampling regressions. The decision belongs
to a separate spike with an assessment of quality, thinking/non-thinking, loops, tool calling, and
the three-mode matrix; not to this commit.

## Implemented UX improvement

Without altering evidence, schema, or selection, the command now:

- emits an event before and after every trial, so waits do not look like hangs;
- uses a Rich bar with a spinner, phase, count, elapsed, and remaining time on a TTY;
- keeps one line per completed trial when the output is redirected;
- separates durations by phase: screening after two samples, confirmation after one and then the
  median;
- shows `≤14` in screening and projects the duration up to the cap without calling it a guaranteed
  limit;
- closes the live display on errors and `Ctrl-C`, keeping a phase summary;
- explains the selection rule and shows the finalist's minimum RAM/VRAM;
- makes the extras handled by the specialized parser visible in `calibrate --help`.

The progress events are internal and not persisted; they require no new schema. D-053 is a separate
change: timestamps, ABBA order, and the benchmark stay unchanged, while the protocol and record move
to v4 and v3 respectively.

## Local empirical calibration

D-055 is verified only by offline fakes in this commit; a real v5 Gate remains manual. All the real
runs described below belong to v3/v4 and are not reinterpreted as evidence for v5.

Every real run was executed on `coding`, CUDA, automatic, and `--no-activate` in isolated roots. No
user record or candidate was modified; after extracting the aggregates the temporary roots are
deleted. These are local verifications, not portable public evidence.

Observed host:

- Ubuntu 24.04, Intel Core i5-10400F (6 cores/12 threads);
- 31.26 GiB RAM;
- NVIDIA RTX 2060 SUPER 8 GiB, driver 595.71.05;
- the model and engine pinned above.

### v3 baseline at 0.5 GiB

The original run (4 min 47 s, exit 0) selected `ctx=131072, n_cpu_moe=38`: 37 and 38 won one round
each and the tie-break preferred 1.248 GiB of minimum free VRAM against 0.783 GiB. The value 36 did
not respect the reserve. The 37/38 medians were 34.745/34.671 tok/s.

### v4 Gate at 0.3 GiB

The negative outcomes were preserved as well:

| Run | Outcome | Observation |
|---|---:|---|
| 1, 5 min 20 s | exit 1 | boundary 36; 36 violates 0.3 GiB during confirmation and 37 does not release within tolerance; no valid finalist |
| 2, 4 min 50 s | exit 0 | boundary 37; 36 drops to 0.051 GiB and is discarded; 37 and 38 are valid |

Aggregates of the valid retry:

| Field | Observation |
|---|---:|
| screening probes | 7 |
| maximum v4 context | 131,072, feasible |
| finalists | 37 and 38 |
| round 1 / round 2 winner | 37 / 37 |
| selection | `n_cpu_moe=37`, unanimous dominance |
| round medians, 37 | 34.907 / 34.258 tok/s |
| round medians, 38 | 34.647 / 34.067 tok/s |
| selected aggregate median | 34.763 tok/s |
| minimum free VRAM, 37 / 38 | 0.509 / 0.962 GiB |
| selected minimum available RAM | 25.577 GiB |
| VRAM baseline drift | 0.0117 GiB |

The result does not authorize `n_cpu_moe=36`: the full benchmark brings it close to VRAM exhaustion.
It also does not demonstrate the benefit of the 0.3 threshold, because the selected finalist stays
above 0.5 GiB and one run in two failed. On 23 July 2026 the maintainer attested the real Windows v4
Gate, including record reuse, and decided `RELEASE` after the Ubuntu and Windows tests. No private
value or log from the Gate was reconstructed or added to the public evidence; coverage therefore
remains `GATE-PARTIAL` while materially different hardware is missing.

## Recommended priorities for a later protocol

1. D-053 versioned only the reserve change as v4; the scale and finalists stay unchanged.
2. Evaluate 262K as an experimental axis, with an explicit budget and memory requirements.
3. Separate the boundary search from the throughput search inside the feasible `n_cpu_moe` domain.
4. Add a real CPU context search, keeping a short path to the baseline.
5. Run single-variable spikes on threads, batch, and MTP; only then test the main interactions.
6. Treat sampling/thinking and quantization as separate contract and quality audits.
7. After the Windows v4 Gate attested by the maintainer, repeat on materially different hardware and
   publish only redacted and manifested reports.

Any later method must stay deterministic, budget-bounded, interruptible, reconstructible from the
record, and validated offline with fakes before the real gates.

## Claude Fable consultation

Claude Fable was consulted three times with `--model fable --effort max` and read-only access. The
first two reviews covered the memory boundary, UX, CPU baseline, and the `min_p` cascade. The third
reviewed D-053 and the two v4 runs: it identified that the first version of the code applied 0.3 GiB
to the reuse of historical v2 records as well. The migration was corrected so that every record
keeps its own reserve, with dedicated tests. It also confirmed that, at the time of the audit, the
missing Windows Gate and the inconsistency between code/spec/docs blocked a stable release; the
subsequent human Gate is recorded above without attributing measurements to it that were not kept.
No consultant output is empirical evidence, and no file was modified by the consultant.

## Primary sources consulted

Versioned repository sources:

- [`engine.lock`](src/qwen_launcher/resources/engine.lock);
- [`evidence/engine/spike-0.md`](evidence/engine/spike-0.md) and the b10011 help for
  [Ubuntu CUDA](evidence/engine/spike-0/ubuntu-b10011/cuda-help.txt) /
  [Windows CUDA](evidence/engine/spike-0/windows-b10011/cuda-help.txt);
- the [Ubuntu KV Q8 spike](evidence/engine/kv-q8-ubuntu.md) and
  [Windows](evidence/engine/kv-q8-windows.md);
- the [public v3 protocol](evidence/calibration/windows-11-rtx-2060-super-v3/protocol.md) and the
  [Calibration Gate](evidence/calibration/windows-11-rtx-2060-super-v3/gate.md).

Primary upstream sources, subordinate to the locks:

- [Qwen/Qwen3.6-35B-A3B model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B);
- [Unsloth GGUF at the pinned revision](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/blob/5bc3e238d916f48a861bac2f8a1990a0e9b7e98d/README.md);
- the [Unsloth Qwen3.6 guide](https://unsloth.ai/docs/models/qwen3.6) and the
  [MTP guide](https://unsloth.ai/docs/models/mtp);
- the [llama.cpp b10011 release](https://github.com/ggml-org/llama.cpp/releases/tag/b10011);
- [llama.cpp MTP PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673);
- [llama.cpp `n_cpu_moe` PR #15077](https://github.com/ggml-org/llama.cpp/pull/15077).

The current upstream pages were consulted on 2026-07-22 and may change; the flags and defaults of
the b10011 binary were also re-checked against the verified local executable.
