# `calibrate_v3.md` — Implemented redesign of the `calibration/v3` confirmation

> **Status:** design approved, implemented, and backed by the Step 5A Windows CUDA v3 Gate.
> It answers the real `coding` run of 18 July 2026 (`CALIBRATION-REJECTED` for v2); the clean
> `--mode all --no-activate` run of 19 July is locally `CALIBRATION-ACCEPTED` for coding, studio, and
> vstudio. The empirical coverage remains `GATE-PARTIAL`; D-047 authorizes Step 5B and defers
> materially different hardware to a future, non-blocking follow-up.
> **Date:** 19 July 2026. **Evidence cited:** `docs/calibration-gate-v3-windows.md`, the
> `calibration-record/v1` record of the v2 run, `docs/calibration-v2-design.md`, and the mini-spikes.

## 1. Summary

The 18 July run is formally correct but unconvincing, and the flaw is not a bug: it is a structural
limit of the confirmation design. The eight observed problems have three root causes:

1. **the finalists are measured in disjoint time windows**, on an environment that drifts over
   time, with an extreme order statistic (the maximum) that a single burst makes decisive — hence
   problems 1, 2, 3 and the choice of 38 despite an 11% median disadvantage;
2. **the objective and the lifecycle are implicit** — the protocol does not declare what it
   optimizes (problem 4) and activates the record before the Gate accepts it (problem 8);
3. **evidence and reserves are incomplete** — no GPU telemetry (5), passive RAM (6), a record that
   does not keep the individual startups, and deleted logs (7).

The implemented solution, `calibration/v3`, adds no statistics: **it changes the geometry of the
measurement so that environmental drift cancels itself out**, and it makes the objective and
lifecycle explicit. In five points:

1. **Paired confirmation (ABBA).** The same 4 fresh startups as today, but interleaved by round:
   round 1 `A→B`, round 2 `B→A`, with a full `benchmark/v1` on every startup. Every finalist is
   therefore measured twice, on two fresh processes, at identical average temporal positions.
2. **Dominance by unanimity of the rounds.** A dominates B only when A's session median exceeds B's
   **in every round**. No new threshold: the rule stays derived from local measurements only.
   Without unanimity the finalists are equivalent and, as today, the VRAM margin and then caution
   decide.
3. **A universal RAM reserve** (2.0 GiB) with the same semantics as the VRAM reserve: violating it
   during a trial makes the probe infeasible or discards the finalist. The local Gate did not
   approach it; testing it on different capacities remains a non-blocking D-047 follow-up.
4. **A `calibration-record/v2` record** with per-startup evidence (baseline, peak, release and its
   duration, RAM, benchmark session, GPU telemetry, temporal order) and retention of the last run's
   logs; `validate` reconstructs the rounds, unanimity, and the choice.
5. **A candidate → active cycle.** The record is born as a `candidate` and is atomically promoted to
   active in the same command (the unaware user still does everything with a single `calibrate`);
   `--no-activate` stops the promotion for the Gate's experimental runs. The v1→v2 schema change
   also makes today's rejected record automatically inert, without migrations.

Cost relative to today: **zero additional startups** (4, as now), two extra benchmark sessions
(about 24 total requests against 14, a few minutes). Screening does not change: it remains the
measured bisection within 12 probes, with only two robustness fixes (section 4).

### The user experience remains the requirement

The guiding principle does not change and is the yardstick for every choice below: a user who knows
nothing about `llama-server` runs `qwen-launcher calibrate`, waits, and gets the best configuration
for their machine — zero mandatory input, no second command, no technical decision. All the
sophistication of this proposal is internal to the protocol; the interface stays a single command
that ends with a plain-language verdict. The only new options (`--no-activate`, `--target-ctx`) are
optional and meant for the maintainer or the expert user; the default path never requires them.

## 2. Diagnosis: why the protocol chose 38

The numbers from the real record:

| Finalist | Measurements (tok/s) | Median | Maximum | Minimum free VRAM |
|---|---|---:|---:|---:|
| 37 | 22.19 · 22.28 · 24.20 · 23.18 · 22.85 | 22.85 | 24.20 | 0.649 GiB |
| 38 | 23.79 · 23.77 · 18.69 · 19.71 · 20.52 | 20.52 | 23.79 | 0.930 GiB |

The current rule asks 37's median (22.85) to exceed 38's maximum (23.79). But 38's first two
measurements belong to a fast regime that disappears halfway through the session
(23.79 → 18.69): the series is not stationary, and the maximum — the most fragile statistic there
is — captures exactly the regime that vanished. A single ambient burst on 38 thus cancels an 11.35%
median advantage for 37, and the rule falls back to the VRAM margin.

The essential point: **on a real desktop the noise is not i.i.d., it is drift plus bursts.** Any
rule comparing two series collected at different times — with any statistic — stays exposed to the
question "is the candidate faster, or was the machine less loaded?". The current protocol cannot
answer, because it measures 37 in full and then 38 in full (problem 3), benchmarks each finalist
only once (problem 2), and keeps no evidence to distinguish the cases (problem 7).

The alternatives discarded, and why:

- **statistical stationarity or significance tests** (half-series comparison, trend, rank): they
  require significance thresholds, that is, invented constants, forbidden by the project's
  principles (`CALIBRATE.md` section 2.2: the criterion derives from locally measured noise); they
  also add re-measurement cycles of unpredictable duration;
- **more measurements per session** (10, 20…): they pay linear time for a problem that is not fast
  variance (already tamed by the median of 5) but slow drift, which more measurements in the same
  time window do not correct at all;
- **fixed equivalence bands** ("2%"): already excluded by the evidence from the two hosts
  (dispersion 0.14–18.8% on the same hardware).

The right answer is a design one, not a statistical one: **make the comparison fair by
construction**, so that drift hits both finalists equally. It is the classic paired ABBA design, and
it is simpler — not more complex — than the current protocol to explain.

## 3. The heart of the proposal: paired confirmation and round unanimity

### 3.1 Confirmation structure

For the two finalists A (boundary, more aggressive) and B (the conservative neighbor), the
confirmation runs `CONFIRM_ROUNDS = 2` deterministic rounds:

```text
round 1:  fresh startup A (full benchmark/v1)  →  fresh startup B (full benchmark/v1)
round 2:  fresh startup B (full benchmark/v1)  →  fresh startup A (full benchmark/v1)
```

- every startup stays a fresh, isolated process, with the mode's real workload, VRAM and RAM
  monitoring at 250 ms, and release verification: nothing that makes a startup "stable" today is
  removed;
- **every startup runs a full `benchmark/v1`** (one excluded warm-up plus five measurements): "2
  stable startups" goes back to meaning "performance confirmed over 2 startups" (problem 2);
- the internal order is reversed in the second round: under linear drift the average temporal
  positions of A (1st and 4th) and B (2nd and 3rd) are identical, so drift favors neither
  (problem 3);
- the order is fixed and deterministic, never random: `validate` must be able to reconstruct it;
- the number of startups per finalist stays 2: the D-039 constant "2 stable startups" becomes "2
  rounds", with no additional loading cost.

`benchmark/v1` does not change one bit (byte-identical resources, one warm-up, five measurements):
only the number of sessions calibration runs and how it compares them changes. The benchmark
protocol and the calibration protocol stay versioned separately.

### 3.2 Selection rule

For finalist F and round r, the **session median** `m(F, r)` is the median of that session's five
measurements — robust to individual bursts by construction.

> **A dominates B if and only if `m(A, r) > m(B, r)` in every round.** Otherwise the finalists are
> equivalent and the current order applies: the largest minimum free VRAM observed, then the more
> conservative one. An exact tie in a round is not a win.

Properties, all verifiable from the record:

- **zero new constants**: no bands, no percentages, no p-values; only order comparisons between
  local measurements — exactly the design constraint that already excluded fixed thresholds;
- **symmetric** (the current "A's median against B's maximum" was not) and safe from a single
  outlier's veto: the raw maximum is no longer decisional and survives only as evidence;
- **unanimity is the implicit equivalence test**: a real, reproducible advantage wins both paired
  rounds; an advantage that appears only once — a burst, drift, bimodality — produces disagreeing
  rounds and falls back safely on the memory margin. On a quiet host (dispersion < 1%) unanimity
  almost always emerges; on a noisy host the rule degrades into the same conservative fallback as
  today, but only when the disagreement is real;
- **deterministic and reconstructible**: `validate` recomputes the session medians, round winners,
  unanimity, and the tie-break from the record's per-startup data.

The resulting selection labels (recorded in the record): `dominance-unanimous-rounds`,
`equivalent-prefer-minimum-free-vram`, `equivalent-prefer-prudent`,
`equivalent-after-baseline-drift` (section 3.3), `single-finalist`, `cpu-baseline-confirmation`.

### 3.3 Baseline drift: from discard to honest degradation

Today a baseline drift beyond 0.125 GiB between a finalist's two startups **discards** it. With
interleaving, the two startups of the same finalist are further apart in time, and on WDDM the
desktop baseline already oscillates by about 0.1 GiB: keeping the discard would mean failing both
finalists on many normal hosts and making the whole run fail — the opposite of the generality
required.

The fix uses a fact already true in the code: memory safety **does not depend** on baseline
stability, because the reserve is verified on every sample as absolute free VRAM
(`_calibration_vram.py`: `vram_free_gib < minimum_free_gib` on every sample). If the environment
takes memory and the reserve holds, the envelope is demonstrated even more strongly; if the reserve
falls, the probe/finalist is already discarded by the existing rule.

So in v3, baseline drift beyond tolerance during confirmation:

- **discards no finalist** (neither of them is at fault);
- **switches off dominance claims**: the selection declares equivalence with the
  `equivalent-after-baseline-drift` label and decides by VRAM margin and caution — if the
  environment moved, the speed comparison is not reliable and the protocol says so instead of
  pretending;
- stays recorded per startup in the record (the baseline of each of the 4 startups, and the overall
  excursion).

Run invalidations stay strict: a compute executable file outside the WDDM baseline (D-046), a driver
change, a capacity change, or a broken monitor. A respawn of the same file within the initial
multiplicity is evidence only; it changes neither reserves nor selection.

### 3.4 The 18 July run under the new rule

Honesty first: a different protocol would have produced different measurements; the run cannot be
re-run on paper. But the two possible outcomes are both defensible, and that is the point:

- **if 38's fast regime was the environment** (a less loaded machine at the start of confirmation),
  the interleaved rounds let both finalists taste it; 37's session medians (22.8–23.2 observed)
  beat those of 38's slow regime (19.7–20.5) in both rounds → **dominance, 37 wins**, that is, the
  11%-faster candidate the current protocol lost;
- **if 38 is genuinely bimodal across fresh startups** (sometimes it starts "fast"), the rounds
  split → equivalence → margin → 38 wins, but this time the choice rests on paired evidence and the
  record shows why, instead of a lone maximum.

In both cases the answer to "is it faster, or was the machine less loaded?" is in the record.

## 4. Screening: two robustness fixes, no strategy change

The measured bisection stays as it is (it is already the part that works: boundary 37 found in 7
probes out of 12). Two fixes:

1. **The monotonicity check uses only feasible probes.** Today `has_monotonic_violation` also
   compares the peaks of failed probes. But an OOM probe's peak is a truncated observation (the
   process dies during a partial load): on another machine it can come out *lower* than the peak of
   a successful conservative probe and trigger a spurious linear degradation that burns the budget.
   Infeasible probes must contribute only the feasibility sign to the bisection; the monotonic model
   is checked on complete loads only. It is a pure portability fix (in the real run the saturated
   peaks 7.79–7.83 GiB caused no harm, by a few hundredths of a GiB).
2. **Interpolation-guided split, with a bisection fallback.** The measured feasible peaks are
   already almost perfectly linear along the axis: 41→5.61, 39→6.40, 38→6.89, 37→7.34 GiB, that is,
   about 0.4 GiB per block. After two feasible probes the boundary can be estimated by interpolation
   (here: limit 8.0−0.5=7.5 GiB → prediction ≈ 37) and the probe aimed there, instead of at the
   blind midpoint (20). Safety rule: the interpolated point counts only when it falls inside the
   current bracket and narrows it, otherwise the midpoint — correctness stays that of the bisection,
   the prediction **orders and never excludes** (the same principle as the seeds, D-035/D-038).
   Typical: 4–5 probes instead of 6–7; the worst case is unchanged. The v3 implementation uses it
   exclusively as ordering inside the bracket.

## 5. Universal RAM reserve (problem 6)

An implemented constant, symmetric to the VRAM reserve:

> `RAM_RESERVE_GIB = 2.0`: if during a trial the minimum available RAM drops below the reserve, the
> probe is infeasible / the finalist is discarded, with an explicit reason
> ("minimum available RAM reserve was violated").

Rationale for the value: it is an absolute margin against paging, independent of the machine's size
(Windows degrades similarly near exhaustion at 16 as at 64 GiB); the current prerequisites (28 GiB
total) and the real measurement (minimum 9.6 GiB available) make it inert on healthy hosts and
active only where today we would accept an envelope on the edge of thrashing. Declared provenance:
this proposal. The Windows Gate observed at least 8.602 GiB available in the accepted trials, so it
verified the monitor and the rule but did not stress the threshold; validation on hardware with less
RAM remains open.

Consistency with reuse: the headroom check at launch already requires
`available RAM ≥ measured requirement`; it becomes `≥ requirement + RAM reserve`, mirroring the VRAM
branch.

A measured caveat to record in the design: with mmap, much of the model is reclaimable page cache;
Windows's "available RAM" includes the standby list, so the reserve mostly hits real private
allocations — that is the intended behavior, but the Gate must observe it at least once on a host
with less RAM before the value can be declared final.

## 6. GPU telemetry: evidence, not decision (problem 5)

The VRAM monitor already queries `nvidia-smi` every 250 ms: the same query can also ask for
`utilization.gpu`, `temperature.gpu`, `clocks.current.sm`, `power.draw`, and the throttling flags
declared by the driver (`clocks_event_reasons.active` / the historical alias
`clocks_throttle_reasons.active`). Zero cost, no new sampler.

Rules:

- **evidence-only in v3**: the telemetry lands in the record per startup (aggregates: maximum
  utilization, minimum SM clock, maximum temperature, throttling flags observed) and explains the
  "fast/slow regime" cases such as 38's; **no decision** depends on it, because any decisional use
  would require thresholds ("how hot is too hot?") that the principles forbid — and on small GPUs
  thermal throttling under prolonged load is normal, not an invalid environment;
- **guaranteed portability**: fields the driver does not support → `null` in the record, never an
  error (a failed telemetry query must not break a calibration);
- the Gate, once evidence is collected, will be able to decide whether a driver flag (which is not
  an invented threshold: the hardware declares it) deserves to become decisional in a future
  protocol.

This also answers the remaining WDDM limit: a desktop context already present that starts working
does not necessarily change instance, but it leaves a trace in utilization/clocks and in the
comparison between rounds.

### 6.1 Run-scoped WDDM identity (D-046)

Two real Gate attempts showed the same desktop context recreated with different PIDs. The PID was
therefore an asymmetric proxy: it admitted any change of activity as long as the instance stayed
alive, but it invalidated the ordinary lifecycle of the same executable. V3 now uses an immutable
baseline for the whole run:

- every instance is `pid + create_time`; the managed process is excluded by that pair alone;
- the executable uses a local volume/file-id digest (`st_dev + st_ino`), keeping no paths;
- the current multiset must be a sub-multiset of the initial population. A respawn of the same file
  is allowed within the initial multiplicity; new files, unreadable identities, or additional
  instances still invalidate the run;
- respawns are counted as per-trial evidence and feed no thresholds or selection;
- the gaps between trials are not sampled. An event entirely confined to a gap overlaps no
  measurement; if it persists into the next trial it is compared against the run baseline and cannot
  be silently absorbed.

The rule governs measurement hygiene, not security against hostile processes. Absolute reserves,
ABBA, telemetry, and the ban on concurrent workloads stay unchanged.

## 7. The `calibration-record/v2` record and evidence (problem 7)

The v2 schema keeps everything needed to redo the run's arithmetic without the logs:

- **for every confirmation startup** (and in reduced form for every probe): the round, the global
  position in the temporal order, start/end timestamps, VRAM baseline/peak/minimum free, the release
  value and **duration**, RAM baseline/minimum, the complete benchmark session (warm-up + 5
  measurements), telemetry (or `null`), the number of initial WDDM contexts, and the respawns
  allowed as evidence only;
- **for the selection**: session medians, the winner of each round, the unanimity/equivalence
  outcome, the excursion of the confirmation baselines, and the
  `equivalent-after-baseline-drift` flag;
- unchanged: hardware/contract identity, the envelope, the observed minimums, the algorithm's
  constants, and the screening probes with their outcomes and reasons.

The **runtime logs of the last run** are preserved (today `.runtime-*` is deleted): a
`calibration/evidence/<run-id>/` directory with single-slot rotation — the new run deletes the
previous one only after writing its own. Bounded disk, diagnosis possible, no unbounded growth. The
records stay private and local; the sharing path with redaction and the privacy scanner does not
change (local timestamps and telemetry are not identifying, and in any case they do not leave the
machine except through a redacted bundle).

`verify_record` v2 extends the current reconstruction: per-session medians from the stored
measurements, round winners, unanimity, the tie-break, and consistency between the per-startup
evidence and the aggregates — the choice stays provable after the fact, an existing requirement
(D-038) applied to the new rule.

## 8. Lifecycle: candidate → active (problem 8)

- `calibrate` first writes `records/<mode>.candidate.json`, then — the default behavior —
  **atomically promotes** it to `records/<mode>.json` (a rename in the same directory); any previous
  active record survives as `<mode>.previous.json` (one slot, zero-cost rollback). The unaware user
  keeps living with a single command and an immediately active record: D-038 stays true to the
  letter.
- `--no-activate` stops the flow at the candidate: it is the mode for the Gate's experimental runs —
  a result that has not been accepted does not become operational. `doctor` shows the per-mode
  state: active, candidate pending, absent, invalid, superseded schema, no headroom. A subsequent
  `calibrate --activate` promotes the candidate without re-running the search.
- **Today's rejected record neutralizes itself**: when v3 arrives, `coding.json` (schema v1,
  protocol v2) no longer passes load validation and every launch falls back to the baseline with
  actionable diagnostics ("superseded protocol record: re-run calibrate"). No migration code.
  Manually quarantining the current file as evidence (moving it under `data/calibrations/`) remains
  an explicit action to be taken **only with authorization** — it was not performed in this session.

## 9. The declared objective (problem 4)

`calibration/v3` declares the objective — in the design, in the record (`objective`), and in the
output:

> **Lexicographic objective:** (1) the largest feasible context on the mode's approved scale;
> (2) at that context, the throughput confirmed by paired dominance; (3) on a tie, the memory
> margin; (4) on a tie, caution.

Why context-first stays the right default for the unaware user:

- context is functional capability (a coding agent with 131k *can do things* it cannot at 32k);
  tok/s is comfort — and the protocol maximizes it anyway within the context;
- the alternative ("also explore 65536, 32768, …" and choose the trade-off) multiplies the duration
  by about 5 and requires a context/speed utility function that no local measurement can decide on
  the user's behalf: it would be an invented constant disguised as optimization;
- the choice stays honest because it is **declared**: the record no longer claims to be "the best
  envelope in absolute terms", but "the fastest envelope confirmed at the largest feasible
  context" — which is what the code actually does.

Two optional post-Gate extensions, neither of which touches the default path:

- `--target-ctx <value from the scale>`: an expert user who prefers speed pins the scale to a single
  step (the existing machinery does the rest; about 10 lines);
- an **informational suggestion** in the final summary, derived from the measured VRAM slope: "at
  ctx 32768 about N more blocks would fit on the GPU; if you prefer speed over context,
  `calibrate --target-ctx 32768`". It is a (measured) capacity prediction, never a tok/s promise;
  and it is labeled as such.

## 10. Complexity and duration (the "less than linear" question)

Where the time goes, and what can be compressed:

- **Screening: it is already sublinear.** The bisection is `O(log₂ 41) ≈ 6` probes (7 observed, cap
  12); a linear scan would have used up to 41. Below the logarithm one can only descend on average,
  with the interpolated split of section 4 (typically 4–5 probes): the theoretical floor is 2
  *measured* probes — a feasible boundary and an infeasible neighbor — because the boundary must be
  demonstrated, not predicted. Any scheme with fewer measurements would stop being a calibration.
- **The dominant cost is process startup** (model loading, minutes), not the arithmetic. That is why
  the v3 confirmation keeps **exactly 4 startups, as today** and spends the gain where it pays off:
  4 benchmark sessions instead of 2 (about +10 requests ≈ a few minutes) buy a doubling of the
  performance evidence and temporal fairness — the best information-per-minute ratio of the whole
  protocol.
- **No parallelism**: a single GPU and memory contention would make the measurements mutually
  contaminated; seriality is a correctness requirement, not naivety.
- The design estimate was 30–45 minutes per mode and 1.5–2 hours for `all`. The real Windows Gate
  completed `all` in **27 minutes and 3 seconds**: coding 8.61 min, studio 7.99 min, vstudio
  9.52 min. The interpolated split and the local loading times explain the gap; the figure does not
  become a promise on other hardware. The CLI shows per-phase progress with an online learned
  estimate.
- A possible future item, subject to a mini-spike: `coding` and `studio` differ only in sampling and
  UI; if a spike verifies that the server's memory envelope is identical, `all` can share the
  screening between the two (about −6 probes) while still confirming per mode. Not needed now.

## 11. Constants and provenance (D-039 update)

| Constant | Value | Windows v3 Gate evidence |
|---|---:|---|
| Minimum VRAM reserve | 0.5 GiB | governed the boundary; discarded vstudio 38 at 0.488 GiB; accepted studio/vstudio minimums 0.503/0.505 GiB |
| Release/drift tolerance | 0.125 GiB | maximum release 0.0176 GiB and maximum drift 0.0176 GiB |
| Confirmation rounds | 2 | complete ABBA order in the three modes; a benchmark on every startup |
| Minimum RAM reserve | 2.0 GiB | accepted minimum 8.602 GiB; threshold not stressed |
| Screening probe cap per mode | 12 | 7/6/7 probes used for coding/studio/vstudio |
| Context scale | 131072 → 8192 | `ctx=131072` feasible and selected in the three modes |
| Selection rule | round unanimity on session medians | unanimous dominance, equivalence on disagreeing rounds, and a single finalist after a reserve discard were all observed |

No per-machine constant; every effect comes through local measurements. The provenance is recorded
in D-039/D-041–D-046. The local Gate backs the values on the 32/8 machine; D-047 defers testing on
heterogeneous hardware to a non-blocking follow-up and forbids describing it as already done.

## 12. Versioning, decisions, migration

- **Protocol `calibration/v3`**, not a silent revision of v2: the project's reproducibility is
  "algorithm version + recorded measurements", so a different algorithm gets a different id. v2
  produced no accepted results and is not published: its code is **replaced** by v3 (no third live
  protocol), `--protocol v1` stays the historical laboratory, and `docs/calibration-v2-design.md`
  receives the "superseded" status with a pointer to the v3 design. The 18 July run stays preserved
  evidence of why v2 was rejected.
- **Schema `calibration-record/v2`** in the wheel; v1 records become "invalid, superseded schema"
  with actionable diagnostics (that is the automatic quarantine of the current record).
- **Decisions recorded in the spec:** D-041 paired confirmation and dominance by unanimity; D-042
  the universal RAM reserve; D-043 the candidate→active cycle with atomic promotion and
  `--no-activate`; D-044 evidence-only GPU telemetry; D-045 monotonicity on feasible probes only and
  the interpolated split as ordering only; D-046 run-scoped WDDM executable identity.
- **What does not change**, and it is most of it: zero mandatory input, one context per comparison,
  measured bisection with a cap and honest degradation, the VRAM reserve on every sample, release
  with tolerance, D-040/D-046 on WDDM, run invalidations, a byte-identical `benchmark/v1`, reuse
  identity and headroom without nearest-match, seeds as ordering only, honest confirmation of the
  baseline on CPU (now with a benchmark on both startups), privacy and bundles, module boundaries,
  and the code size limits.

## 13. Honest limits of the proposal

1. It does not rehabilitate the v2 run of 18 July: the new v3 run is distinct evidence and does not
   retroactively reinterpret measurements collected with another protocol.
2. With 2 rounds, a burst falling exactly inside one session can still produce disagreeing rounds →
   equivalence → margin: that is the intended fallback, conservative and declared, not a wrong
   choice; the Gate can raise the rounds to 3 (unanimity over 3, still without thresholds) if the
   evidence calls for it — at the cost of 2 additional startups.
3. A **constant** ambient load for the whole run lowers the absolute tok/s of both finalists: the
   comparison stays fair, the absolute values stay relative to the environment (the record declares
   it; the telemetry documents it).
4. The Windows Gate observed the RAM reserve with mmap, but with at least 8.602 GiB available: the
   semantics near 2 GiB, and on a host with less RAM, remain unproven.
5. The telemetry is best-effort by construction: on drivers that do not expose it the record holds
   `null` and the environmental explanation stays partial (never blocking).
6. The gaps between trials are not sampled; D-046 prevents the absorption of persistent contexts but
   does not record events born and ended entirely outside a measurement window.

## 14. Implementation and tests completed in Step 5A

The code was separated by responsibility within the limits of 200 lines/file and 40/function:

| Area | Change |
|---|---|
| `_calibration_v2_search.py` → `_calibration_v3_search.py` | monotonicity on feasible probes only, selection by unanimity, and a safe interpolated split |
| `_calibration_v2_confirm.py` → `_calibration_v3_confirm.py` | ABBA rounds with a benchmark per startup; drift → degradation flag (about 80 lines reorganized) |
| `_calibration_v2_runner.py` → `_calibration_v3_runner.py` | round orchestration, selection labels, evidence dir with rotation (about 30 lines) |
| `_calibration_ram.py` | the RAM reserve in the monitor's validate (about 10 lines) |
| `_hardware_monitoring.py` / `_calibration_vram.py` | optional telemetry and a run-scoped WDDM executable baseline |
| record: schema v2 + `_record_build` / `_record_checks` / `_record` | per-startup evidence, round/unanimity reconstruction, candidate/active/previous paths (about 120 lines) |
| `_calibration_reuse.py`, `_cli_doctor.py` | RAM headroom + reserve; candidate/superseded-schema states (about 30 lines) |
| `_cli_calibration_v2.py` → `_cli_calibration_v3.py` | `--no-activate`/`--activate`, per-phase progress, plain-language summary (about 40 lines) |

The deterministic offline suite covers (a fake trial runner, no hardware):

- the ABBA order emitted exactly (global positions 1–4 recorded);
- dominance: a win in both rounds → `dominance-unanimous-rounds`; disagreeing rounds or a tie →
  equivalence → margin → caution (a fixture with the numbers of the 18 July run: on the recorded
  data the new rule selects 37);
- baseline drift during confirmation → no discard, label `equivalent-after-baseline-drift`;
- a violated RAM reserve during screening → an infeasible probe with a reason; during confirmation →
  a discarded finalist;
- a monotonicity regression: a truncated OOM peak lower than a conservative feasible peak → no
  spurious degradation;
- the interpolated split inside the bracket, the midpoint fallback, and the cap respected;
- v2 records: construction/loading/verification, reconstruction of the selection, actionable
  rejection of v1 records, atomic candidate→active→previous promotion, and `--no-activate` not
  activating;
- absent telemetry → `null` without errors;
- a respawn of the same file allowed and counted, while a new file, extra multiplicity, an
  unreadable identity, and a recycled managed PID are rejected without serializing paths.

Local Windows verification: uv 0.11.28, CPython 3.12.13, Ruff, 314 offline tests, `validate`, the
build, and the isolated wheel all green. The D-046 baseline resolved 20/20 real WDDM identities
without serializing paths. The Ubuntu/Windows CI matrices are green on the D-046 commit `6f69d77`
(run `29684539755`) and the doctor lifecycle commit `2d4cc22` (run `29684866498`). The real Gate is
described in `docs/calibration-gate-v3-windows.md`.

## 15. Operational path

1. ~~approve the RAM reserve, ABBA, the lifecycle, telemetry, and the interpolated split~~ —
   completed with D-041–D-046;
2. ~~implement v3 and the offline tests~~ — completed; the experimental runs use `--no-activate`;
3. ~~re-run the Calibration Gate on Tommaso's machine~~ — completed on 19 July 2026 with a locally
   accepted outcome for the three modes and the candidates left inactive;
4. ~~implement Step 5B with the empirical coverage explicitly limited to the measured machine and
   without distributing its envelope as a remote optimum~~ — completed with the v2 policy/report,
   checksums, and ordering-only seeds;
5. in the future, repeat the Gate on at least one materially different case and update the evidence,
   without making the follow-up blocking for Step 5B.

The updated conclusion stays honest: `CALIBRATION-REJECTED` applies to protocol v2, while v3
explains which envelope wins and why on the measured machine. The Windows result is
`CALIBRATION-ACCEPTED` for the three modes; D-047 allows proceeding with Step 5B without calling the
empirical coverage complete.
