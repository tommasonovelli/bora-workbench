# bora-workbench — Implementation specification and roadmap

This is the only normative plan in the repository. It describes the constraints future work must
preserve and the activities not implemented yet. The behavior available today is documented in
[`docs/`](docs/README.md); the measured provenance of the locks and reports is kept in
[`evidence/`](evidence/README.md).

## 0. Actual status and tracker

Updated on 30 July 2026.

### Completed baseline

- [x] The 0.1 milestone is implemented: Python package, configuration, resources, hardware, engine,
  lifecycle, three modes, local v3 calibration, validation, installers, uninstall, CI, and release.
- [x] Version `0.1.0`, tag `v0.1.0`, and the GitHub Release are public.
- [x] Release run `29739366272` is green for the Ubuntu/Windows tests, the build, and the wheel
  verification.
- [x] `llama.cpp b10011`, the model, mmproj, assets, flags, API, and health are pinned and verified.
- [x] The Q8 K/V cache with mmap is enabled on CUDA only; the weights remain `UD-Q4_K_M`.
- [x] `calibration/v3` and `calibration-record/v2` produced the local Windows CUDA Gate accepted for
  `coding`, `studio`, and `vstudio`; the three original candidates remain inactive.
- [x] The public v2 policy and report keep the v3 method/evidence and give v4 nothing but ordering
  seeds, never another host's envelope.
- [x] The post-release fixes D-051 and D-052 are on the branch: a temporary port for the trials and a
  maximum tolerance of 1 MiB when comparing total RAM.
- [x] The maintainer attested the real Ubuntu and Windows Gates for `calibration/v4`, including
  record reuse, and decided `RELEASE` on 23 July 2026.
- [x] Version `0.1.1`, tag `v0.1.1`, and the GitHub Release distribute D-051, D-052, D-053, and the
  runtime progress; PyPI is excluded from this release's authorization.
- [x] On the branch after the release, `calibration/v5` inserts 96K and 48K into the automatic scale
  and keeps reading v2/v3 records.
- [x] Version `0.1.2`, tag `v0.1.2`, and the GitHub Release distribute `calibration/v5` and the
  stabilization following `0.1.1`; PyPI remains excluded.
- [x] The maintainer decided `RELEASE` on 23 July 2026, explicitly waiving a new manual
  cross-platform Gate; that waiver is not described as a passed Gate.
- [x] Phase 0 of `calibration/v6-lite` fixes cleanup precedence, separates the VRAM causes,
  introduces the four-outcome taxonomy, and prepares the engine contract exactly once.
- [x] Phase 1 on the agent side prepares `scripts/spike_ctx/`, the fake dry-run, the protocol, and a
  redacted template; no real run or verdict was performed.
- [x] Version `0.1.3`, tag `v0.1.3`, and the GitHub Release distribute D-058–D-062 from the green
  workflow's artifacts; PyPI remains excluded and no spike Gate is declared.
- [x] Version `0.1.4` distributes opt-in `calibration/v6-lite` (D-063/D-064): `mode/v2`, quick-bench,
  the v6 engine, v5 records, the `--protocol v6 --preference` CLI, and v5 reuse/`doctor`; `v5`
  remains the default and the offline suite stays green.
- [x] The three-envelope protocol is repaired and becomes the only calibration protocol (D-067):
  the laboratory and paired-search protocols, the `--protocol` option, and the older record formats
  are removed, and the CLI exposes one calibration command.
- [x] The trial adapter is validated on Ubuntu (D-067), measured on 25 July 2026 on an RTX 2060
  SUPER 8 GiB. The shared `coding`+`studio` group completed its search, its pairing, and six
  envelope gates; a separate `vstudio` run completed 44 trials in 61 minutes and wrote a valid
  candidate record whose three envelopes all passed smoke, multi-turn, and the vision gate. No
  candidate was activated.
- [x] The repository is fully English (D-065): documentation, normative plan, changelog, and
  measured-evidence prose. The byte-pinned benchmark payloads and the mirroring spike prompt keep
  their original text because they are measurement inputs.
- [x] Version `0.1.5` republishes the calibration evidence with a regenerated digest chain and
  realigns the published artifacts with the branch; no runtime behavior changes.
- [x] Version `0.1.6`, tag `v0.1.6`, and the GitHub Release distribute D-067: one working
  calibration protocol, validated on hardware on Ubuntu, with the redundant protocols and record
  formats removed. PyPI remains excluded.
- [x] On 26 July 2026 the maintainer selected the current repository/package refactor as the
  `0.2.0` scope, postponed the earlier router/Open WebUI/benchmark roadmap, and closed the failed
  `qwen-launcher==0.1.0` PyPI recovery (D-068). This is not a passed Gate and authorizes no remote
  operation.
- [x] Calibration stores one requested preference cell per mode in `calibration-record/v6`
  (D-069). An individual mode can retain a different preference; `--mode all` applies one
  preference to all selected modes. The historical v5 three-envelope records are superseded and
  never migrated.
- [x] Version `0.2.0`, tag `v0.2.0`, and its GitHub Release are public from the green release
  workflow; later documentation changes do not alter those immutable artifacts.
- [x] D-070 selects GitHub Releases as the only current distribution channel and prepares `0.2.1`
  to remove the registry workflow, installer options, and current publication instructions.
- [x] A real Windows CUDA run on 26 July 2026 exposed the defects of D-071 and, after them, wrote a
  valid `coding` candidate at `ctx=32768`, `n_cpu_moe=33`, with 0.589 GiB of VRAM free at its
  minimum. `0.2.2` distributes those fixes; the candidate was not activated.
- [x] `0.2.3` adds `bora update` (D-073): a checksum-verified installation of the newest published
  GitHub Release through uv, which never downgrades and never reinstalls the managed engine. The
  D-056 uv handoff is generalized to any uv command. The offline suite covers version ordering,
  the manifest gate, the HTTPS rule, and every refusal.
- [x] Calibration and startup stop paying for work no decision reads (D-074/D-075/D-076):
  confirmation rounds drop the long request, a `max_context` ladder stops at its first feasible
  context, and the model's SHA-256 is receipt-cached behind unconditional filename and size checks.
  The selected cell, the recorded evidence, and the final gate are unchanged. `0.2.4` distributes
  them (D-077), which also carries `TUI.md` as a non-normative design proposal.
- [x] `0.3.2` makes the pi handoff report what this machine actually serves and makes both of its
  writes reversible (D-082). The context window comes from a service already listening on the
  configured port, else the active `coding` record, else the verified baseline, and the command
  names which of the three it used; an activated `coding` calibration ends by naming the command
  that applies the new window; `bora pi remove` and `bora pi uninstall` undo the entry and the
  package as two separate consents.
- [x] On 29 July 2026 the maintainer selected the reduced `0.4.0` TUI scope and its current-command,
  read-only, post-UI handoff boundary (D-083–D-085). This authorizes local implementation and local
  commits only; it does not authorize release operations or Open WebUI work.
- [x] The TUI dependency gate accepted MIT-licensed Textual `8.2.8` under the narrow presentation
  concurrency boundary, with the exact dependency graph frozen in `uv.lock` (D-086).
- [x] TUI steps E1–E9 implement the responsive seven-screen dashboard, exact same-process handoff,
  command composers, finite optional motion, and complete optional manual without changing the core
  engine, model, calibration, or record contracts (D-083–D-087).
- [x] D-090 adds the exact `bora pi launch` handoff and replaces the home decoration with continuous,
  multicolour Unicode wind and layered fractional-block sea while preserving every TUI kill switch.
- [x] Version `0.4.2`, tag `v0.4.2`, and its GitHub Release distribute D-090 from the exact green
  release-workflow bundle under D-091; no registry publication or Gate claim is made.
- [x] On 30 July 2026 the maintainer selected the unified blue-and-white workbench, bare-`bora`
  entry, readable post-command acknowledgement, and `0.4.3` release boundary in D-092.
- [x] On 30 July 2026 the maintainer directed the shared wind/sea graphic to keep animating on every
  workbench page instead of freezing in a section, and selected `0.4.4` as its release (D-093).

### Open work

- [ ] Perform, as `0.1.2` post-release verification, the real upgrade from `0.1.1`, calibration
  without activation, and a complete uninstall on Ubuntu and Windows.
- [ ] Validate the trial adapter on Windows: server startup, monitoring with the 0.5/2.0/0.125
  reserves, quick-bench, and gate. The logic is covered by offline tests on both platforms.
- [~] Repeat `calibrate --no-activate` on materially different hardware; coverage remains
  `GATE-PARTIAL` and no envelope is transferred between hosts.
- [ ] Complete the `0.2.1` automated suite, cross-platform release CI, exact artifact verification,
  and documented manual limitations without calling them a Gate.
- [ ] Run `bora update` for real on Ubuntu and Windows, from a published release to the next one,
  and confirm that the managed engine and the local records survive it. The logic is covered by
  offline tests on both platforms; the deferred uv installation is not.
- [ ] Run `bora pull`, `bora rm`, and `bora pi` for real on Ubuntu and on Windows. The store, the
  confined cache deletion, and the pi writer are covered by offline tests on both platforms; the
  actual 22 GB transfer, and the three symlink tests that a plain Windows account cannot run, are
  not.
- [~] `bora pi` was exercised on Windows on 28 July 2026 against an isolated home and an isolated
  state root: the window came from a registered `coding` service, from the baseline with its
  diagnostic when no record existed, and `pi remove` deleted only the `bora` provider while keeping
  the backup. The npm removal and `bora pi launch` were never run for real, on either platform.
- [ ] Repeat the visual and one-core CPU observation for the continuous 6 fps decoration on Ubuntu
  and Windows. D-087 measured the superseded finite 8 fps effect and is not evidence for the
  continuous timer, which D-093 also keeps running while a section is open, so the observation is no
  longer bounded to the central menu.
- [ ] Router and standalone benchmark remain deferred post-0.2 backlog.
- [~] The managed Open WebUI was installed and started once for real on Ubuntu, through the
  production code path: it reached `/ready` with `{"status": true}`, reported the name `Open WebUI`
  with authentication off, left no key file in the working directory, and stopped cleanly. The
  resolved environment measured 6.4 GB on that host. Nothing equivalent was run on Windows, and the
  first-start duration and the resident memory beside a loaded model remain unmeasured, with no
  figure for either stated anywhere. The installer, the environment, the readiness contract, the
  two-role state, the browser gate, and the fallback are covered by offline tests on both platforms.
- [ ] Confirm on a real instance that Open WebUI's image requests reach llama-server with the pinned
  mmproj, which is what `vstudio` depends on and what no source reading establishes.

No local candidate is activated. Backlog B and Backlog D are complete; Backlogs A and C remain
unstarted without another explicit request. Pushes, tags, releases, uploads, and remote settings always require
authorization in the current session.

---

## 1. Product and perimeter

### 1.1 Current product

`bora-workbench` is a specialized local distribution built around
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`. It detects the hardware, verifies the model and
engine, builds a plan, governs `llama-server`, exposes three modes, and measures one envelope
locally for each machine.

Since `0.3.0` it also acquires and releases that pinned model: `pull` downloads it into a managed
store, `rm` deletes it again, and `engine install` does both halves of a first setup (D-078).

It is still not a generic model manager, a model registry, a plugin framework, or a multi-backend
orchestrator. A model exists here only if `engine.lock` pins its repository, revision, filenames,
sizes, and digests.

### 1.2 Platforms

- Ubuntu 22.04+ x86-64;
- Windows 11 x86-64;
- CPU, or a single NVIDIA CUDA GPU;
- services exclusively on `127.0.0.1`.

Out of perimeter: macOS, ARM, Vulkan, ROCm, distributed multi-GPU, auto-update, native GUI, Python
plugins, writing into the Hugging Face cache, and arbitrary user modes.

### 1.3 The 0.2 and 0.3 boundaries

`0.3.0` gives the launcher ownership of the pinned model: the managed store, `pull`, `rm`, the
acquisition folded into `engine install`, the separate cached-weights question in `uninstall`, the
API alias, and the pi handoff (D-078 to D-081). It changes no engine release, no calibration
protocol, no record format, and no `command_contract_sha256`, so every existing
`calibration-record/v6` stays valid. It adds no second model: the catalog is still exactly what
`engine.lock` pins, and supporting another one remains a future decision with its own evidence.

`0.3.2` finishes that handoff (D-082): the window pi is given is the one this machine actually
serves and says where it came from, a calibration that activates a `coding` record names the command
that applies it, and both writes into pi's world can be taken back. It changes no engine, model,
calibration, or record behavior either.


`0.2.0` is the repository/package refactor from `qwen-launcher` to `bora-workbench`, including the
`bora` command, new managed-root identity, consolidated modules, and the stabilization required by
the refactor audit. It keeps the one calibration protocol and pinned engine/model behavior already
distributed in `0.1.6`.

`0.2.1` changes only the distribution boundary and its installation/release documentation: current
artifacts are published through GitHub Releases only (D-070). It does not change engine, model,
calibration, record, or candidate behavior.

The previously planned router, skills, managed Open WebUI, sync, and standalone benchmark are
post-0.2 backlog. They are not silently included in `0.2.0` and create no dependency or compatibility
claim for this release.

### 1.4 The 0.4 boundary

`0.4.0` is the interactive-front-end milestone authorized by D-083–D-088. It keeps the current CLI
names and flat package tree, adds `bora tui`, extracts a structured non-mutating read model, and
hands every real operation back to the existing CLI only after the UI runtime has ended. Bare
`bora` remains help and settings remain read-only. Textual `8.2.8` is accepted and frozen under the
narrow presentation boundary; finite motion ships after the scoped Ubuntu observation in D-087.

This boundary changes no engine release, model identity, calibration protocol, record format,
command contract, reserve, managed root, or candidate lifecycle. Open WebUI remains separately
deferred and is not represented by placeholder TUI rows, actions, or service roles.

`0.4.1` redesigns that front end's presentation under D-089 and changes nothing else. The workbench
draws on the terminal's own background, opens on one central menu whose rows summarize local state,
and gives each section a full window reached with `Enter` and left with `Esc`; a section switches the
optional flags of its marked action in place rather than listing every flag combination. The
read-only boundary, the non-mutating snapshot, the post-teardown handoff, and the motion budget stay
exactly as D-084–D-087 fixed them.

`0.4.2` distributes D-090's foreground pi shortcut and continuous multicolour home decoration under
D-091. It changes no snapshot, launch service, engine, model, calibration, record, or same-process
TUI handoff rule. The manual pi run and replacement motion observation remain follow-up checks, not
passed Gates.

`0.4.3` applies D-092's presentation and entry-point refinement. Bare `bora` is the sole workbench
entry and `bora tui` no longer exists; `bora --plain` retains the reduced presentation. One close-set
blue `Bora Workbench` title and the wind/sea identity frame every screen, with a static frame in
sections and when motion is disabled, while detail panels use a wider centred measure and explicit
blue/white hierarchy. A successful returning action waits for acknowledgement in the restored
terminal before Textual can replace its output. Core callbacks, snapshot collection, command
composition, same-process dispatch, exit codes, and every engine/model/calibration/record contract
remain unchanged.

`0.4.4` applies D-093 to optional TUI motion only. The shared wind/sea graphic keeps animating on
whichever page is visible, so an open section no longer freezes the identity every page displays. One
6 fps timer under the 12 fps ceiling serves home and sections alike, navigation neither restarts nor
duplicates it, and stopped periods still never count as elapsed animation time. Every plain, colour,
encoding, size, focus, environment, and unmount kill switch keeps its exact behaviour and remains the
only way to obtain a static frame. No snapshot, callback, prompt, network, write, service, engine,
model, calibration, record, dispatch, or exit-code contract changes.

---

## 2. Hierarchy of sources of truth

In case of conflict, the first applicable source wins:

1. versioned locks, accepted policies/reports, and structured artifacts;
2. real output of the pinned version, kept in `evidence/`;
3. schemas and tests;
4. this document;
5. official documentation for the exact pinned version;
6. current official documentation for tools not pinned yet;
7. assumptions.

Consequences:

- `latest` is forbidden in committed files;
- a pinned version does not change without an explicit instruction;
- the current branch of an upstream project does not correct the contract of a pinned release;
- a contradiction is reported and stops only the work it affects;
- flags, checksums, commits, benchmarks, endpoints, and hardware claims are not invented;
- raw files covered by a manifest stay byte-identical.

---

## 3. Active normative decisions

The identifiers stay stable because code, tests, and evidence cite them.

| ID | Decision |
|---|---|
| D-001 | Python package `>=3.12,<3.13`; development and CI on CPython `3.12.13`. |
| D-002 | uv `0.11.28`, `uv_build`, a committed `uv.lock`, and frozen commands. |
| D-003 | Runtime: `typer`, `rich`, `psutil`, `httpx`, `jsonschema`; development: `pytest`, `ruff`. |
| D-004 | `pyyaml` may enter only with the future skills/router backlog, for frontmatter read with `safe_load`. |
| D-006 | Modes = behavior; local records = performance; shared reports/profiles = seeds or evidence. |
| D-008 | A single GPU; `CUDA_VISIBLE_DEVICES` exclusively in the child environment. |
| D-010 | `coding` without UI; `studio` with UI; `vstudio` with UI and vision, always explicit. |
| D-011 | The 0.2 router uses normalized phrases, never regular expressions. |
| D-015 | Every managed service listens on `127.0.0.1` only. |
| D-017 | `engine.lock` contains machine semantics, not merely a list of flags. |
| D-018 | Immutable installations; atomic activation through `current.json`. |
| D-020 | Historical 0.2 process: local preparation, a human gate, and separate finalization. D-068 supersedes this process for `0.2.0` without claiming that the omitted Gate passed. |
| D-022 | Open WebUI will use versioned environments and an atomic activation manifest. |
| D-024 | Feasibility evidence is neither a calibrated profile nor a performance promise. |
| D-030 | The `model` identity is separate from `model_path`; the default is resolved read-only at the pinned revision. |
| D-033 | `UD-Q4_K_M` weights; the Q8 K/V cache with mmap only on the verified CUDA branch. |
| D-034 | An optimal envelope is local; equal nominal capacity authorizes neither transfer nor nearest-match. |
| D-035 | Only a compatible local record can drive a calibrated `LaunchPlan`. |
| D-039 | The `[0, 41]` domain, reserves, scale, rounds, and probe cap have declared provenance; empirical portability is partial. |
| D-041 | v3 confirmation in two `A→B/B→A` rounds, a full benchmark, and dominance by unanimity. |
| D-042 | Every trial leaves at least 2.0 GiB of RAM; reuse requires the measured requirement plus the reserve. |
| D-043 | Record lifecycle candidate → active → single previous; activation by default, `--no-activate` separates the Gate. |
| D-044 | GPU telemetry is best-effort and evidence-only, never a decision threshold. |
| D-045 | Monotonicity only between feasible probes; interpolation only to order an interior point. |
| D-046 | The run-scoped GPU compute-context population serializes no paths. It is a hard exclusivity rule off WDDM; D-071 reduces it to counted evidence on WDDM, where the desktop itself owns compute contexts. |
| D-047 | The local Gate is sufficient for the method; coverage stays `GATE-PARTIAL` while different hardware is missing. |
| D-048 | Public v2 policy/report; the loader projects only `n_cpu_moe` as probe ordering. |
| D-049 | Default-model gate: 28 GiB total RAM and 22 GiB available. |
| D-050 | In v4, `98304` was an explicit expert target outside the automatic scale. |
| D-051 | Trials use `llama_port` when free, otherwise a loopback port assigned by the OS. |
| D-052 | The total-RAM comparison tolerates at most 1 MiB; headroom and components stay strict. |
| D-053 | `calibration/v4` keeps the v3 scale, search, and ABBA but uses a 0.3 GiB VRAM reserve and produces `calibration-record/v3`; v2 records stay valid with their own 0.5 GiB reserve. |
| D-054 | Historical 0.1 workflow: the PyPI job was opt-in through `PYPI_PUBLISH_ENABLED`; `v0.1.1` published on GitHub only, as authorized. D-068 replaces the persistent switch for future publication. |
| D-055 | `calibration/v5` inserts `98304` and `49152` into the automatic scale, raises the cap to 14 probes, and produces `calibration-record/v4`; the v4 execution is retired but v2/v3 records stay readable. |
| D-056 | `uninstall` removes the four roots and its own `uv tool` installation with a single confirmation; a helper on the base Python waits for the process to exit to avoid Windows locks. Installations not managed by uv stay explicitly unchanged, and uv itself is not removed. |
| D-057 | `0.1.2` collects `calibration/v5` and the terminal, build, CI, and uninstall stabilization following `0.1.1`; the maintainer authorizes the commit, push, tag, and GitHub Release without a new manual Gate, keeps the candidates inactive, and excludes PyPI. |
| D-058 | `run_trial` applies cleanup precedence to workload failures as well: `KeyboardInterrupt`/`SystemExit` stay highest priority, while `VramEnvironmentError` and `RamError` invalidate the run. |
| D-059 | The spike and future v6 classify by class only `SUCCESS`, `MEMORY_INFEASIBLE(ram|vram)`, `RETRYABLE`, and `PROTOCOL_INVALID`; v5 does not consume the new taxonomy. |
| D-060 | The contract makes MTP parametric (`mtp2`/`disabled`), conservatively disables MTP for `vstudio`, and prepares extended sampling/reasoning. The pinned model card denies mmproj+MTP support while the local Spike 0 was PASS: the conservative choice prevails until a new spike. The new digest invalidates the reuse of historical local records exactly once, without making them unreadable; public seeds remain ordering hints only. |
| D-061 | A human cross-context spike is the decision gate for v6-lite: only a committed `GO` verdict authorizes `mode/v2`, the quick-bench, the v6 engine, and v5 records; `NO-GO` closes the work with documentation of the v5 presets. |
| D-062 | `0.1.3` distributes the Phase 0 fixes and the Phase 1 package. The maintainer authorizes the commit, push, tag, and GitHub Release ahead of the local runs, which stay post-release; they authorize neither PyPI, candidate activation, nor Phase 2 without a GO. |
| D-063 | The maintainer explicitly authorizes overriding the D-061 gate: `calibration/v6-lite` is implemented as an **opt-in** protocol (`--protocol v6`) before the GO verdict of the cross-context spike. `calibration/v5` remains the default; promoting v6 to the default remains conditional on a committed `GO`. No benchmark result and no `GO` verdict is invented: the search, selection, confirmation, gate, and record are tested offline with fakes. (This entry originally also claimed that the real trial adapter was validated on hardware; that claim was premature and is corrected by D-066.) |
| D-064 | `0.1.4` distributes v6-lite: a hard `mode/v2` migration (the three modes emit `min-p`/`presence`/`repeat`/`reasoning` without changing the digest, v2-only loader), a production quick-bench, the `_calibration_v6_*` engine (shared `coding`+`studio` search, bisection of the VRAM side only, Pareto-free selection, ABBA confirmation with a conditional third round, final per-envelope gate), a lean `calibration-record/v5` record, the `--protocol v6 --preference` CLI, and v5 reuse/`doctor`. v6 reserves 0.5/2.0/0.125 GiB. `doctor` shows the `active_preference` envelope. |

| D-065 | The repository is written in English end to end: documentation, this plan, the changelog, the pull request template, and the prose of the measured evidence. Measured values, digests, decision ids, constants, protocol names, and gate wording are preserved verbatim; the byte-pinned benchmark payloads (`benchmark-v1`, `benchmark-quick`, `calibration-v1`), the multi-turn input in `_calibration_trial.py`, and the mirroring prompt constant in `scripts/spike_ctx/quick.py` keep their original text, because they are measurement inputs and changing them would change what is measured. Translating the checksum-bound evidence changed its bytes, so the whole chain was regenerated: `gate.md`/`protocol.md` → the report's `source_references` → the report digest → the policy evidence digest → `SHA256SUMS`. `0.1.5` distributes the result and realigns the published artifacts with the branch; the artifacts of `0.1.0`–`0.1.4` embed the previous digests and are neither rebuilt nor replaced. No runtime behavior, contract, or `command_contract_sha256` changes. |

| D-066 | Correction of record, 25 July 2026: `calibration/v6-lite` **does not work**. The real trial adapter was never validated on hardware, so the corresponding claim in D-063, `CHANGELOG` `0.1.4`, `docs/calibration.md`, and `docs/releasing.md` was premature and is withdrawn. Only the search, selection, confirmation, gate, and record logic is exercised, by offline tests with fakes. `--protocol v6` stays shipped and opt-in, but the documentation must present it as non-functional; `calibration/v5` remains the only protocol for real calibration. The open tracker item for hardware validation was already correct and stands. Do not describe v6 as usable, benchmarked, or validated until a real run on Ubuntu and Windows is committed. |

| D-067 | Calibration becomes a single protocol, 25 July 2026, and the trial adapter behind D-066 is repaired. Four defects made every run fail. (1) `wait_for_health` caught only `ConnectError` and `TimeoutException`, so the `ReadError` a dying server produces escaped `start_service` and bypassed its cleanup, leaving a live child and a registered service that made the next start refuse; every transport class is now read as "not ready yet". (2) `start_service` cleaned up only for a listed set of exception classes; it now cleans up whatever escapes. (3) Exhausted VRAM was unclassifiable: the driver rejects the allocation, so free VRAM never crosses the monitored reserve and the engine only reports it by dying during model load. (4) The final gate sized its smoke prompt in words instead of tokens, overshooting the window by roughly 2.3x, so the gate could never pass. D-059 stays class-based with one declared exception: `ServerStartupError` carries the process log, and only the VRAM side of `MEMORY_INFEASIBLE` is decided from that log, because no monitor class can observe a rejected allocation. A first full hardware run then exposed two failures no offline test could reach, both caused by a memory boundary that moves between measurements on a nearly full GPU. (5) A group that failed discarded the modes that had already completed, because records were persisted only after every group finished; each group now persists its own records and the run reports which groups produced nothing while still exiting operationally. (6) A finalist that stopped fitting the reserves during ABBA failed the whole mode; the comparison is now abandoned and the surviving finalist confirmed, and the same point reached at the gate counts as a gate it cannot pass. With the protocol working, the redundant ones are removed: the `calibration/v1` laboratory, `calibration/v5`, the `--protocol` option, the `calibration-record/v2`-`/v4` formats and their schemas, `validate --path`, the repository-only cross-context spike package, and the public ordering seeds the search no longer consumes. `calibrate` is one command with `--preference`, `--target-ctx`, `--activate`, and `--no-activate`; the surviving modules drop their version infix, and user-facing documentation stops naming protocol versions. The on-disk record format keeps its identifier as a data-format marker so a record written by an older launcher is diagnosed as superseded rather than misread. |
| D-068 | On 26 July 2026 the maintainer explicitly selects the current refactor as `0.2.0`: distribution `bora-workbench`, package `bora_workbench`, command `bora`, and repository `tommasonovelli/bora-workbench`. The earlier Step 7–9 router/Open WebUI/benchmark roadmap is postponed beyond 0.2. The final version is authorized without describing the audit or manual run as a passed Gate. PyPI starts with `bora-workbench==0.2.0`; the failed historical `qwen-launcher==0.1.0` publication is closed and its artifacts are never relabelled, rebuilt, or uploaded under the new project. Local completion does not authorize a push, tag, GitHub Release, PyPI upload, remote setting, or candidate activation; each remains a separate current-session action. |
| D-069 | On 26 July 2026 the maintainer replaces the v5 three-envelope record with one calibrated preference cell per mode. `--preference fast|balanced|max-context` selects the only cell searched, confirmed, gated, and stored; `--mode all` applies the same preference to all three modes, while separate mode runs may retain different preferences. Recalibration replaces only the selected modes' candidate/active lifecycle files. The incompatible format is `calibration-record/v6`; v2–v5 records are superseded and never migrated. Candidate activation promotes the cell exactly as measured and cannot relabel it. The maintainer also authorizes commit, push to `tommasonovelli/bora-workbench`, tag `v0.2.0`, GitHub Release, and the first `bora-workbench==0.2.0` PyPI publication after automated checks and CI succeed. Manual Ubuntu/Windows calibration and hardware runs are explicitly waived for this release, remain follow-up verification, and are not a passed Gate. |
| D-070 | On 26 July 2026 the maintainer withdraws the active PyPI publication clauses of D-068/D-069 and selects GitHub Releases as the only distribution channel until a future explicit decision. Version `0.2.1` removes the registry publication job, manual dispatch, OIDC permission, separate distribution artifact, registry installer options, and current registry instructions; dependency registry URLs in `uv.lock` remain frozen input sources, not a publication path. Historical decisions and artifacts stay unchanged. The maintainer authorizes the `0.2.1` commit, push to `tommasonovelli/bora-workbench`, tag after local checks, and the GitHub Release after the tag's release CI succeeds; they explicitly waive manual Ubuntu/Windows and hardware runs, and do not authorize a registry upload, remote-setting change, candidate activation, or Gate claim. |

| D-071 | On 26 July 2026 a real Windows CUDA run showed that three defects, none of them a measurement, ended `bora calibrate` before it could write a record. (1) The redirected progress line carried `≤` and `≈`, which a legacy Windows code page cannot encode; the resulting `UnicodeEncodeError` reached the trial through `TrialProgress` and `classify` turned it into an unclassifiable run failure. Progress now stops reporting instead of raising, which is what the module already promised, and the line is ASCII. (2) Every non-success HTTP status was retryable, so the permanent `400` a too-small context returns was retried once and then reported as `remained retryable after one retry`. Only server-side and wait-and-retry statuses are retryable now, matching the health rule of section 5.9. (3) The pinned quick-bench long request measures 23180 prompt tokens and asks for 64 more, so the `16384` and `8192` steps of the approved scale can never produce a sample and CPU calibration, which used the `8192` baseline, could never succeed at all. The scale keeps its approved steps, the ladder and the CPU confirmation use only the measurable ones, and an explicit `--target-ctx` below `32768` is refused as input before any process starts. The byte-pinned payload is a measurement input and is not resized. (4) D-046 required an immutable WDDM compute-context population, which no Windows desktop can offer: the compositor, the shell, and the browser hold contexts permanently and recreate them constantly, NVIDIA reports no per-process memory under WDDM, and a context whose owner `psutil` could not open refused the run before its first trial. The exclusive-GPU rule is kept exactly where it holds — off WDDM, where a foreign context is visible and attributable — and under WDDM the population becomes a counted diagnostic, with the aggregate reserve and release checks carrying the contamination verdict. The executable-file identity that only that rule consumed is removed, so no launcher hashes another process's binary. (5) A trial registers its server under the run's own runtime tree, so `status` and `stop` never saw a server an abruptly killed run left holding VRAM, while `start` told the operator to run `bora stop`, which could not reach it; both commands now sweep the state root and every unrotated trial root. `find_verified_process` also treated an unopenable PID as an error rather than as absent, which on Windows — where PIDs are recycled quickly and the launcher shares one account with its children — meant a recycled PID could wedge `calibrate`, `status`, and `stop` alike with no way to clear the record. |

| D-072 | On 26 July 2026 the maintainer authorizes `0.2.2` as the release that distributes D-071, and authorizes the commit, the push to `tommasonovelli/bora-workbench`, the tag `v0.2.2`, and the GitHub Release. The maintainer also decides that the VRAM reserve stays at `0.5` GiB: the `0.3` GiB value of the retired `calibration/v4` and `/v5` is not restored, so record reserves, the packaged policy, and the schema constants are unchanged and existing `calibration-record/v6` records stay valid. Distribution remains GitHub Releases only (D-070). No registry upload, candidate activation, or Gate claim is authorized, and the manual Ubuntu run for this version is waived rather than performed. |

| D-073 | On 27 July 2026 the maintainer requests a self-update command and authorizes `0.2.3` to distribute it, including the commit, the push, the tag `v0.2.3`, and the GitHub Release. `bora update` reads the newest published GitHub Release, refuses anything that is not strictly newer, downloads that release's `SHA256SUMS` and wheel over HTTPS while rejecting any hop that leaves HTTPS, verifies the wheel's SHA-256 against the manifest, and installs it with `uv tool install --force --python 3.12.13`. This repeats the trust boundary of the documented manual install and introduces no new one; the release manifest is not a signature and is not described as one. Distribution stays GitHub Releases only (D-070), so no registry is queried. **The managed engine is deliberately outside the update.** It lives under the data root, is selected by `engine.lock`, and survives the tool replacement, so an update does not reinstall it, does not redownload it, and does not activate anything; the command instead reads `engine.lock` out of the downloaded wheel and reports whether `bora engine install` is now required. Configuration, calibration records, and the model are equally untouched. `update` refuses a live managed service and refuses any installation `uv tool` does not own, reporting the documented installer instead of guessing. Because Windows cannot replace the environment of the running process, uv is invoked through the D-056 handoff, now generalized to any uv command in `_tool_handoff.py`/`_tool_helper.py`; exit code 0 therefore reports a scheduled installation, not a completed one, and the helper prints uv's own failure on the same terminal. No candidate activation, registry upload, or Gate claim is authorized, and the manual Ubuntu and Windows update runs are follow-up verification rather than a passed Gate. |
| D-074 | On 27 July 2026 the maintainer decides that a paired confirmation round measures the short series only. An `A→B`/`B→A` round compares median short end-to-end latency and the dispersion of that same triple; both derive exclusively from the three short requests, so the 23180-token long request that the full quick-bench also runs is measured four to six times per confirmation and never read. Confirmation therefore runs the excluded warm-up and the three short requests, and stops there. Nothing else moves: the same number of fresh processes start, in the same `A→B→B→A` order, under the same third-round rule, and the confirmed cell is still the sample the search measured, so the record keeps the `prefill_tps` that the full quick-bench produced. The warm-up stays because the first request after a fresh start pays the memory-mapped first-touch cost, not because it is compared. The final gate is unchanged and remains the stricter memory test of the selected cell. |
| D-075 | On 27 July 2026 the maintainer decides that a `max_context` search stops the ladder at the first context that produces a sample. The approved scale is descending, `max_context` selects the largest feasible context, and its near-tie rule compares only rivals at that same context, so every remaining step is smaller and can change neither the selected cell, nor the finalist a confirmation would compare, nor the rival the gate may retry. The rule is scoped to `max_context` alone: `fast` and `balanced` compare latency across contexts and keep walking the whole ladder under the shared probe budget. An infeasible context still costs one prudent probe and the ladder still continues downward past it; only a step that actually measured a sample ends the walk. |
| D-076 | On 27 July 2026 the maintainer decides that the default model's SHA-256 verification is receipt-cached. Verifying the pinned artifacts reads 21.11 GiB, and 0.84 GiB more of projector for a vision mode, on every `calibrate` and on every mode launch, with no output while it runs. The locked filename and the exact byte size are still checked every time, because they are free and they are what a truncated or interrupted download fails. The SHA-256 is recomputed unless a cached receipt records the same absolute path, size, modification time, and expected digest; any difference, and a missing, unreadable, or malformed receipt, forces the full hash. The receipt lives under the cache root because it is regenerable and losing it costs only time, and writing it is best-effort: a cache that cannot be created or written is not an error and never fails a launch. Section 5.8 no longer describes model resolution as strictly write-free. This keeps the checks that were written for corruption, interrupted downloads, and a wrong file under the locked name; it does not defend against an attacker holding write access to both the artifact and the user's cache root, who could forge the receipt as easily as the file, and it changes nothing about download verification. |
| D-077 | On 27 July 2026 the maintainer authorizes `0.2.4` as the release that distributes D-074, D-075, and D-076, including the commit, the push to `tommasonovelli/bora-workbench`, the tag `v0.2.4`, and the GitHub Release created from that tag's green release workflow. The engine, model, command contract, `command_contract_sha256`, record format, reserves, and the packaged policy and schemas are unchanged, so an existing `calibration-record/v6` stays valid and no local candidate is activated. Distribution remains GitHub Releases only (D-070); no registry upload is authorized. The manual Ubuntu and Windows runs for this version are waived rather than performed, and no Gate claim is authorized. The same commit adds `TUI.md`, an explicitly non-normative design proposal for an interactive front end. It is a decision input only: nothing in it is approved, scheduled, or implemented. Its closing table poses open questions to the maintainer and numbers them `Q1`–`Q6`, deliberately carrying no `D-0xx` identifier: a decision number is assigned by this table when something is actually decided, so a proposal that hands itself one either collides with the decisions taken meanwhile or reserves a block it does not own. Answering one of those questions is what creates its entry here. Folding the file into section 8 as a backlog entry, or deleting it, remains a later decision. |

| D-078 | On 27 July 2026 the maintainer decides that the launcher owns the pinned model instead of only reading it. A managed store under `data/models` becomes the first place launch resolution looks; the pinned Hugging Face snapshot stays a read-only fallback, so weights acquired before this store existed keep launching and are never downloaded twice. `bora pull` fetches the locked artifacts from the pinned revision over HTTPS, verifies each against its locked size and SHA-256, publishes them by atomic rename, and writes the D-076 receipt so the first launch afterwards does not hash 22 GiB again. `bora engine install` performs that same acquisition unless `--no-model` declines it, because an engine with no weights cannot serve anything and the second command was the largest part of first setup. This does not make the project a model manager: the artifacts still exist only as the repository, revision, filenames, sizes, and digests that `engine.lock` pins, and adding a second model remains a future decision with its own evidence. |
| D-079 | On 27 July 2026 the maintainer decides that removal must actually free the disk. `bora rm` deletes the pinned artifacts from the managed store, and then asks a second, separate question about the copies that live in the shared Hugging Face cache; `uninstall` takes the store with the data root it already owns and asks that same separate question afterwards. Consenting to the first never implies consenting to the second, both default to no, and `--keep-hf` and `--dry-run` exist for the cases where neither is wanted. Cache deletion is confined by construction rather than by care: only a file directly inside the pinned `snapshots/<revision>/` of a locked repository, only as far as that repository's own `blobs/` when the entry is a symlink, only once no other snapshot of that repository still references the blob, never through a symlinked cache directory, and directories are pruned with `rmdir`, which cannot remove a directory that still holds something. Writing into that cache stays forbidden: fabricating snapshots or refs is what would corrupt the tools that share it. `0.3.1` extends the last rule: when a removal takes the repository's last snapshot, the repository directory goes with it, `refs` included, because refs naming a revision whose files no longer exist is a stub rather than content; a surviving snapshot or blob stops the prune, and another tool's repository is still never examined. |
| D-080 | On 27 July 2026 the maintainer decides that the API reports the model as `Qwen 3.6` rather than as its artifact identity. The pinned `b10011` `--help` lists `--alias`, so the flag joins `verified_flags`, and the alias is declared in a new top-level `model_alias_contract`. It is deliberately outside `command_contract`: `command_contract_sha256` binds every published and local `calibration-record/v6` to those exact bytes, and a name that changes what `/v1/models` reports while changing no measured behavior must not supersede a single record. The digest is therefore unchanged and existing records stay valid. |
| D-081 | On 27 July 2026 the maintainer decides that the launcher can connect the pi coding agent to a running service. pi is bring-your-own-key and speaks the OpenAI completions API, so `bora pi` writes one provider named `bora` into pi's own `models.json`: the loopback base URL from the configured port, a placeholder key the managed server ignores, and the D-080 alias as the model id, with the context window taken from the same local record the launcher would use rather than invented. The write shows the entry, asks once, keeps a backup, and replaces the file atomically; `--print` never writes at all. `--install` delegates to `npm install -g --ignore-scripts`, which is the vendor's own instruction: this project pins no digest for pi, says so, and does not install it implicitly. No other agent, editor, or provider is supported by this decision. |
| D-082 | On 28 July 2026 the maintainer decides that the pi handoff must report the context window this machine actually serves, and that both of its writes must be reversible. The window is resolved in one order and the command always names which source answered: a managed service already listening on the configured port reports the window it was launched with; otherwise the active `coding` record supplies its calibrated context; otherwise the verified baseline does, together with the diagnostics that explain why the record was not used. The live service comes first because record reuse also weighs free memory that this very service is holding, so consulting the record during a session would report `ctx=8192` for a machine serving far more. A calibration run that activates a `coding` record ends by naming the command that applies the new window — nothing rewrites a number stored in somebody else's configuration file — and offers `bora pi --install` when pi is absent; `--no-activate` prints no such hand-off, because a candidate steers no launch. `bora pi remove` deletes only the `bora` provider from `models.json`, whether or not pi is still installed, and keeps every other provider and the backup; `bora pi uninstall` hands the package back to `npm uninstall -g` after showing the command, reports an executable still on PATH instead of claiming a removal npm did not make, and then asks separately about the entry. Neither consent implies the other, and an installation made by the vendor's own script is not npm's to remove. No other agent, editor, or provider is added, and the engine, model, calibration, and record behavior are unchanged. |
| D-083 | On 29 July 2026 the maintainer selects the reduced `0.4.0` scope in `TUI_PLAN.md`: keep every current CLI name and the flat package tree, keep bare `bora` as help, keep settings read-only, and add the explicit `bora tui` dashboard, command composer, and teaching surface. The TUI owns no launch, calibration, setup, pi, update, removal, or confirmation rule. Clipboard integration, editor launching, configuration writes, command aliases, generic model management, package reorganization, and Open WebUI integration remain outside this milestone. This authorizes local implementation and the step-scoped local commits, but no push, tag, release, upload, remote setting, candidate activation, or Gate claim. |
| D-084 | The TUI opening and refresh are non-mutating: no network, model hashing, receipt write, state cleanup or quarantine, directory creation, configuration write, managed-service start, or background polling. They may perform the same bounded read-only hardware and engine subprocess probes as `doctor`, from one presentation worker, because calling the current diagnostics process-free would be false. A shared synchronous snapshot reports corrupt state as unreadable, model artifacts as receipt-verified only when the D-076 identity matches, and configuration provenance without changing existing callers. |
| D-085 | Every selected command is displayed exactly and runs only after the UI runtime has ended and restored the terminal. Dispatch invokes the existing Click/Typer command in the same bora process rather than leaving a TUI parent waiting in `subprocess.run`; returning actions reopen only after exit 0, while failures, invalid input, and interruption propagate `1`, `2`, and `130`. The project may review and add Textual before the first interaction loop; if accepted, Textual alone owns the UI event loop and one presentation worker, while core APIs remain synchronous and no general concurrency facility is added. Motion is optional for `0.4.0` and is omitted if its measured budget fails. |
| D-086 | The TUI dependency gate is `GO` with Textual `8.2.8`, resolved exactly by `uv.lock`. Its MIT licence, Python 3.12 support, documented Linux and Windows support, maintained release history, Worker API, and headless Pilot tests meet the milestone's needs. The 29 July 2026 review found no published PyPI or GitHub advisory for Textual and the frozen dependency audit found no known vulnerability; upstream's lack of a published security policy remains a recorded limitation. Textual owns only the presentation event loop and one thread worker for the synchronous snapshot collector. Core modules gain no async API, scheduler, executor, or other concurrency. |
| D-087 | On 29 July 2026 the maintainer accepts the available Ubuntu-only E8 motion check and directs implementation to continue through E9 while the Windows motion measurement is recorded as unavailable. This is scoped to optional TUI motion and does not turn any other unavailable Windows acceptance check into a pass. The final local 120x40 pseudo-terminal observation used three alternating static/automatic pairs at 8 fps: automatic motion added 2.666 percentage points of median one-core CPU during its three-second active window, both modes measured 0.0% median in the two-second settled window, and every run exited 0. Motion therefore ships with the 12 fps ceiling, finite settlement, and all kill switches from D-085; the raw observation and its limits live in `evidence/tui/ubuntu-motion.json`. This authorizes neither `0.4.0` finalization nor a push, tag, release, upload, remote change, candidate activation, or Gate claim. |
| D-088 | On 29 July 2026, after E9 and the available Ubuntu pseudo-terminal acceptance checks, the maintainer directs release of `0.4.0` if the TUI checks remain green. The 60x20 and 120x40 plain/full presentation runs, explicit refresh/navigation/quit sequence, returning `doctor` handoff, terminal `coding` preflight handoff, alternate-screen exit, zero isolated-root writes, and no-traceback checks passed; their raw observation is `evidence/tui/ubuntu-acceptance.json`. They are programmatic pseudo-terminal checks, not manual visual checks. A real foreground model process and its `Ctrl-C` restoration were unavailable because the isolated roots held no engine or model; Windows TUI checks were not performed under D-087. Neither is called passed. After the complete frozen local suite is green, this decision authorizes the `0.4.0` finalization commit, push to `main`, and tag `v0.4.0`; the GitHub Release is authorized only after that tag's release workflow is green and only from its exact bundle. GitHub Releases remains the only distribution channel; no registry upload, remote-setting change, candidate activation, Open WebUI work, or Gate claim is authorized. |

| D-089 | On 30 July 2026 the maintainer rejects the shipped `0.4.0` presentation and directs its redesign and release as `0.4.1`. The dashboard painted its own background inside the terminal, split movement between arrows for screens and `Tab` for a screen's actions, and enumerated one menu row per flag combination, so `Setup` listed twenty rows for four operations and the explanatory text stopped being read. The workbench therefore requests the terminal's default background and spends colour only on the brand, the marker, and the composed command; it opens on one central menu whose rows each carry a snapshot-derived summary, with `Run` first; `Enter` opens an entry as a full window and `Esc` returns, so one marker moves at a time and `Tab` is unbound; and each section lists its actions once while switching the marked action's flags in place. This is a presentation decision only: the read-only boundary, the non-mutating snapshot, the post-teardown same-process handoff, the dispositions, the calibration wizard's valid-only combinations, and the motion budget of D-084–D-087 are unchanged, and the flag toggles keep every reachable argv available under the same recursive parser check. The TUI composes `bora pull` and `bora rm` without the optional `qwen` handle because this distribution pins one model; the CLI still accepts it. After the complete frozen local suite is green, this decision authorizes the `0.4.1` finalization commit, push to `main`, and tag `v0.4.1`; the GitHub Release is authorized only after that tag's release workflow is green and only from its exact bundle. The local pseudo-terminal runs are programmatic, not manual visual checks, no Windows terminal check was performed, and neither is called passed. GitHub Releases remains the only distribution channel; no registry upload, remote-setting change, candidate activation, Open WebUI work, or Gate claim is authorized. |
| D-090 | On 30 July 2026 the maintainer requests one direct agent shortcut and a richer home identity. `bora pi launch` invokes the pi executable already on PATH with its documented `--provider bora --model <id>` flags, where `<id>` is always `model_alias_contract.alias` from `engine.lock` (`Qwen 3.6` in the current lock). It uses no shell, inherits the current working directory and terminal I/O, starts no bora service, installs nothing, and changes neither `models.json` nor any managed root; the operator first connects with `bora pi` and runs `bora coding` separately. An absent pi or ordinary child failure is operational exit 1 and interruption is 130. The same request supersedes only D-087/D-089's current finite, low-colour decoration: the focused central menu now carries three continuously travelling Unicode wind rows and a three-row sea made from fractional, shaded, and full block cells, both with multiple foreground colours at 6 fps under the existing 12 fps ceiling. The timer stops and the bands disappear on every existing section, focus, size, plain, colour, environment, and unmount kill switch; colour and motion still carry no status or action information. D-087's Ubuntu evidence measures the superseded finite 8 fps implementation, so it is retained as history and is not claimed as a CPU measurement of this continuous effect; a new Ubuntu observation and every Windows visual/CPU check remain open. This authorizes local implementation only, not a version, commit, push, tag, release, upload, remote change, candidate activation, Open WebUI work, or Gate claim. |
| D-091 | On 30 July 2026 the maintainer directs release of `0.4.2` for D-090. After the complete frozen local suite, packaged-content validation, build, isolated wheel verification, complete uv-tool uninstall, and diff inspection pass, this authorizes the `0.4.2` finalization commit, push to `main`, and tag `v0.4.2`. The GitHub Release is authorized only after that tag's Ubuntu/Windows release workflow is green and only from its exact `bora-workbench-release-bundle`; GitHub Releases remains the sole distribution channel. A real `bora pi launch`, a new Ubuntu visual/one-core CPU observation for the continuous effect, and all Windows visual/CPU observations are explicitly waived for this release and remain follow-up checks, not passed checks or a Gate. No registry upload, remote-setting change, candidate activation, Open WebUI work, engine/model/calibration/record change, or Gate claim is authorized. |
| D-092 | On 30 July 2026 the maintainer directs a unified workbench presentation and release as `0.4.3`. Bare `bora` becomes the only TUI entry; the `tui` command is removed, `bora --plain` replaces its presentation flag, and explicit subcommands remain the complete scriptable CLI. Every screen retains the close-set `Bora Workbench` title, entirely blue, and the wind/sea graphic: motion remains 6 fps only on the focused home, while sections and `BORA_TUI_MOTION=off` retain a static frame with no timer; plain, encoding, size, focus, and unmount kill switches remain. Sections are centred at a wider responsive measure than home, with bordered action/command/detail panels, concise action guidance, blue commands and labels, and high-contrast white prose; shared Rich CLI status output follows the same blue/white identity while warnings and errors remain text-labelled. After any successful returning action, the restored terminal waits for Enter before Textual reopens, so print-only output cannot disappear immediately; non-zero results and terminal actions still never reopen. This changes no snapshot, callback, prompt, network, write, service, engine, model, calibration, record, or same-process dispatch contract. After the complete frozen suite, validation, build, isolated wheel/uninstall checks, and diff inspection pass, the maintainer authorizes the `0.4.3` finalization commit, push to `main`, and tag `v0.4.3`; the GitHub Release is authorized only after the tagged Ubuntu/Windows workflow is green and only from its exact bundle. Existing manual visual/CPU, real foreground, and Windows terminal observations remain unavailable follow-up checks, not passed checks or a Gate. GitHub Releases remains the only distribution channel; no registry upload, remote setting, candidate activation, Open WebUI work, or Gate claim is authorized. |
| D-093 | On 30 July 2026 the maintainer directs the optional wind/sea graphic to keep moving on every workbench page and releases that change as `0.4.4`. `0.4.3` animated only the focused central menu and froze the frame as soon as a section opened, so the identity D-092 gives every page stopped moving on six of its seven pages. One 6 fps timer, still under the 12 fps ceiling, now serves whichever page is visible; opening or leaving a section keeps that same timer instead of freezing, restarting, or duplicating it, and elapsed animation time still excludes every stopped period so the graphic resumes rather than jumping. The frame functions remain pure in time, dimensions, and seed, decoration still carries no state, and the plain, `NO_COLOR`, `TERM=dumb`, encoding, 80x24 size, focus, `BORA_TUI_MOTION=off`, and unmount switches keep their exact behaviour as the only routes to a static frame or no timer. This changes no snapshot, callback, prompt, network, write, service, engine, model, calibration, record, dispatch, or exit-code contract, so existing `calibration-record/v6` files remain valid. Motion now runs while a section is read, so its cost is no longer bounded by staying on the central menu and the manual Ubuntu and Windows visual/one-core CPU observation remains an unavailable follow-up check rather than a passed check or a Gate. After the complete frozen suite, validation, build, isolated wheel/uninstall verification, and diff inspection pass, this authorizes the `0.4.4` finalization commit, push to `main`, and tag `v0.4.4`; the GitHub Release is authorized only after the tagged Ubuntu/Windows workflow is green and only from its exact bundle. GitHub Releases remains the only distribution channel; no registry upload, remote setting, candidate activation, Open WebUI work, or Gate claim is authorized. |
| D-094 | On 30 July 2026 the maintainer answers the ten open questions of `WEBUI_PLAN.md`, so Backlog B stops being a proposal and becomes a scoped plan. A managed Open WebUI is wanted (`W1`): the upstream interface is judged materially better kept than the integrated llama.cpp one, and both `studio` and `vstudio` open it while `coding` keeps `services.ui` false. That answer is about value, not cost, so the spike still measures the resolved installation size; the number becomes a declared cost in `docs/installation.md` instead of a go/no-go gate, and it is paid partly for a dependency closure that pulls torch for an embedding model this configuration never constructs. Authentication is disabled (`W2`): upstream creates its own fixed local account, which cannot be undone in the same data directory. Environment values seed the first boot and the user owns every setting afterwards (`W3`), rather than being accepted by the interface and discarded at restart. The embedding engine is non-empty (`W4`), so nothing is downloaded on a first start, and web search stays off and is the user's to enable. Title, tag, and follow-up generation are off (`W5`): three extra completions per turn on the single calibrated slot are a latency cost nobody asked for. Both the frontmatter dependency installation and every stored function are disabled (`W6`), because a managed installation is immutable or it is not, and no third-party Python executes inside a process bora starts. `WEBUI_NAME` stays unset (`W7`): the interface remains `Open WebUI` everywhere, no branding clause is engaged and no user-count exemption is invoked, bora's own output names the program it opens, and the upstream licence joins `resources/notices/`. The Backlog A router stays deferred now that upstream ships skills (`W8`). The multi-service work is its own step and comes first (`W9`), because the browser opens only once both services report READY. No provisioning command, no packaged Open WebUI content, and no `sync` survive (`W10`): D-080 already makes `/v1/models` report `model_alias_contract.alias`, so the picker names the model without a database write, and bora therefore holds no credential into Open WebUI and never calls its API. This records the answers and replaces the Backlog B text. It authorizes no installation, spike run, process, measurement, push, tag, release, upload, remote setting, candidate activation, or Gate claim. |
| D-095 | On 30 July 2026 the maintainer judges the D-094 scope over-engineered for a single-operator desktop tool and directs the feature to be built and released as `0.5.0` without the spike that preceded it. Four pieces of D-094 are therefore dropped rather than postponed. **The spike and its evidence chain**: no `E1`-`E9` deliverables, no `evidence/` manifest; the installed size, the first-start duration and the resident memory stay unmeasured and are stated as figures nowhere, and the open-work list says so. **The lock**: no `resources/open-webui.lock` and no `open-webui-lock/v1` schema. `open-webui==0.11.0` is a pinned constant in `webui.py`, installed with `uv pip install`; two machines running the same bora get the same release, and `latest` stays forbidden, but the resolved closure is not digest-verified. This is weaker than the engine's contract and is accepted knowingly, because the alternative is regenerating a 119-package hash set on every upstream bump. **Immutable versioned installations**: one environment at `data_dir()/open-webui/venv`, whose recorded version is written last, so an interrupted install reports as absent and is rebuilt; no staging, no atomic `current.json`, no cleanup of inactive environments. **The mode-document field naming the interface**: every UI mode opens the same one, so the field would have had a single value across every document and would have been an unused extension point; `services.ui` keeps meaning "this mode opens a chat interface", and which one is decided by whether `bora webui install` has been run. Installation is an explicit command rather than a step of `bora studio`, because a closure that pins torch costs gigabytes and a launcher must not spend them unasked; until it is run, the UI modes keep opening the integrated llama.cpp interface, which is also the fallback when the interface fails. Everything else D-094 settled is built as recorded: the one-place environment with both immutability switches, the generated session key that no output shows, `WEBUI_NAME` never set and an inherited one removed, `/ready` and not `/health`, the service role with an ordered stop, the browser opened only once both roles report READY, and no call into Open WebUI's API. |

| D-096 | On 30 July 2026 the maintainer reads the shipped `0.5.0` and makes two corrections. **Where the interface is acquired**: D-095 made `bora webui install` an explicit command so a launcher would not spend gigabytes unasked, but the step that already spends them is `bora engine install`, which downloads 22 GB of weights and is where a first setup waits. The interface therefore installs there by default, with `--no-webui` declining it exactly as `--no-model` declines the weights; neither flag removes anything already present. After a setup, `bora studio` opens a finished chat interface rather than an interface the user has yet to discover a command for. **Where it is visible and how it is removed**: `0.5.0` reached the snapshot and `doctor` but nothing in the workbench, so the Setup screen now names which interface a UI mode would open and carries the install and removal actions, and `compose_engine_install` gains the third flag. `bora webui remove` asks two separate questions in the shape D-079 established: the environment, which is reinstallable bytes and whose freed size is reported, and the interface data, which is the user's chats, notes, uploads and settings and is not backed up anywhere. Both default to no, declining the second keeps the content for a later install, removal refuses while a managed service is running, and neither removal follows a symlink out of the managed root. `bora uninstall` deletes both without a third question, because it deletes the whole data root; its preview now says so before the confirmation instead of leaving the user to infer it. No engine, model, calibration protocol, record format, command contract, reserve, or candidate is touched. |


A new durable decision updates this table in the same step that authorizes it.

---

## 4. Architecture

### 4.1 Module responsibilities

| Module | Responsibility |
|---|---|
| `cli.py` / `_cli_*` | input, presentation, and exit codes; no platform logic |
| `paths.py` | per-OS directories; no creation |
| `config.py` | TOML, environment, precedence, and validation |
| `hardware.py` | CPU, RAM, NVIDIA, and GPU selection |
| `profiles.py` | modes, seeds, gates, and `LaunchPlan` |
| `benchmark.py` | the reusable `benchmark/v1` protocol |
| `calibration.py` / `_calibration_*` | local search, records, bundles, and evidence |
| `engine.py` / `_engine_*` | lock, model, assets, command, installation, and activation |
| `process.py` / `_process_*` | processes, readiness, state, lock, status, and stop, for both service roles |
| `uninstall.py` | confined removal of the four public roots |
| `update.py` | published release lookup, verified wheel, and uv installation |
| `_tool_handoff.py` / `_tool_helper.py` | uv installation identity and one deferred uv command |
| `validation.py` / `_validation_*` | schemas and semantic checks |
| `snapshot.py` (0.4) | synchronous, structured, non-mutating local diagnostics for CLI and TUI |
| `tui/` (0.4) | terminal presentation, navigation, composition, and post-UI dispatch only |
| `resources/__init__.py` | `importlib.resources` access |
| `routing.py` (future) | pure skill normalization and scoring |
| `webui.py` (0.5) | the managed Open WebUI: installation, environment, command, and readiness |

Only `paths.py`, `process.py`, `hardware.py`, and `engine.py` may branch on the operating system.

### 4.2 Repository territories

- `src/bora_workbench/resources/schemas/`: versioned contracts;
- `src/bora_workbench/resources/content/`: contributed content;
- `src/bora_workbench/resources/*.lock`: pinned external compatibility;
- the rest of `src/bora_workbench/`: core maintained by the owner;
- `docs/`: current behavior for users and contributors;
- `evidence/`: measured output and manifests, not manuals;
- `IMPLEMENTATION_SPEC.md`: roadmap and normative constraints;
- `tests/`: offline behavioral evidence.

A PR changes core or declarative content, never both.

### 4.3 Resources and imports

The wheel's resources are `Traversable`. Use `read_text()`/`read_bytes()`; `as_file()` only inside
its context manager. Do not assume a physical `Path`.

Importing `bora_workbench` uses no network, creates no directories, writes no files, and starts no
processes.

---

## 5. Current cross-cutting contracts

The full operational explanation is in `docs/`; this section keeps the invariants future work must
not break.

### 5.1 Stack, packaging, and dependencies

- Python package `>=3.12,<3.13`; development/CI `3.12.13`.
- uv `0.11.28`; backend `uv_build>=0.11.28,<0.12`.
- `src/` layout; development dependencies in `[dependency-groups]`.
- `uv.lock` committed; CI with `uv sync --frozen` and `uv run --frozen`.
- The wheel carries every resource; the sdist carries the installers, documentation, plan, and
  evidence.
- Third-party GitHub Actions pinned to a full SHA.
- Textual `8.2.8` is the approved TUI framework and is resolved exactly by `uv.lock` (D-086).
  Its event loop and one snapshot presentation worker are the only 0.4 concurrency exception.
- Bare `bora` opens the workbench; `bora --plain` selects reduced presentation and no `tui`
  subcommand exists (D-092). Explicit commands retain their existing CLI behavior.
- A successful returning TUI handoff waits for terminal acknowledgement before recollection and
  reopening; terminal actions and every non-zero result still end the workbench invocation.

### 5.2 Configuration and paths

Precedence: environment > TOML > defaults. The whole TOML is validated before the overrides. Unknown
keys and malformed values are errors; the launcher does not modify the file.

| Key | Environment | Default |
|---|---|---|
| `model` | `BORA_MODEL` | the pinned model |
| `model_path` | `BORA_MODEL_PATH` | `None` |
| `llama_port` | `BORA_LLAMA_PORT` | `8080` |
| `webui_port` | `BORA_WEBUI_PORT` | `8081` |
| `engine_path` | `BORA_ENGINE_PATH` | `None` |
| `open_browser` | `BORA_OPEN_BROWSER` | `true` |

Ports 1–65535, and the two ports must differ, which is checked on the resolved configuration before
any process starts. Environment booleans: `true/false`, `1/0`, `yes/no`, `on/off`. Only the two path
variables may be empty to mean `None`.

| Root | Linux | Windows |
|---|---|---|
| config | `${XDG_CONFIG_HOME:-~/.config}/bora-workbench` | `%APPDATA%\bora-workbench` |
| data | `${XDG_DATA_HOME:-~/.local/share}/bora-workbench` | `%LOCALAPPDATA%\bora-workbench\data` |
| cache | `${XDG_CACHE_HOME:-~/.cache}/bora-workbench` | `%LOCALAPPDATA%\bora-workbench\cache` |
| state | `${XDG_STATE_HOME:-~/.local/state}/bora-workbench` | `%LOCALAPPDATA%\bora-workbench\state` |

Base variables that are missing, empty, or relative use the fallback. The path helpers create no
directories.

### 5.3 Declarative contracts

Every document uses JSON Schema 2020-12, `additionalProperties: false`, and `^[a-z0-9-]+$`
identifiers.

Packaged schemas: `engine-lock/v1`, `mode/v1` and `/v2`, `profile/v1`,
`calibration-policy/v1` and `/v2`, `calibration-report/v1` and `/v2`, and
`calibration-record/v6`.

- Runtime modes use `mode/v2`: description, services, full sampling, and reasoning. The v1 schema
  remains packaged only to diagnose declarative content precisely; the runtime loader requires v2.
- A v1 profile is compatibility/evidence only; no production profile is distributed.
- The v2 policy/report pair is privacy-safe reference evidence and never supplies another host's
  launch envelope.
- v6 records are private, contain one selected preference cell per mode, and are bound to full
  model, engine, mode-policy, hardware, memory, and calibration identity. A v2–v5 record is
  diagnosed as superseded; an unknown future schema is invalid. Neither is migrated.
- Filenames, references, and SHA-256 digests are checked semantically.

A new incompatible field requires a new schema version.

### 5.4 Hardware and units

GiB = bytes / `1024³`; NVIDIA MiB / `1024`. Memory names end in `_gib`.

`nvidia-smi` runs without a shell with a 5-second timeout. Absence, an error, or malformed output
produces the CPU backend with a warning. If several GPUs exist, selection is by highest total VRAM
and then lowest index, but CUDA startup stays blocked.

The CUDA child process receives `CUDA_VISIBLE_DEVICES`; the parent process is not modified.

### 5.5 Plan, records, and baseline

Only an active `calibration-record/v6` can supply a calibrated cell. The model/digest,
engine/commit/contract, mode-policy digest, mode, OS, backend, hardware, driver, and headroom must
all match. Total RAM tolerates at most 1 MiB of drift; available RAM and free VRAM remain separate
comparisons.

Reuse:

- available RAM ≥ the record's measured requirement plus its 2.0 GiB reserve;
- CUDA free VRAM ≥ the record's measured requirement plus its 0.5 GiB reserve.

Fallback: `ctx=8192`; CUDA `n_cpu_moe=48`; CPU without `n_cpu_moe`. It is always non-optimized.
`--force` bypasses only the default model's 28/22 GiB gate.

### 5.6 Calibration

One local, explicit, user-confirmed protocol exists (D-067/D-069). It performs no upload, commit, or
configuration change and writes only `calibration-record/v6`.

Constants:

- approved context scale: `131072 → 98304 → 65536 → 49152 → 32768 → 16384 → 8192`, of which only
  the steps at or above `32768` are measurable and therefore searched or accepted as an explicit
  target (D-071);
- CUDA domain `[0, block_count]`, exactly `[0, 41]` for the pinned model;
- RAM/VRAM polling every 250 ms;
- reserves: 2.0 GiB RAM, 0.5 GiB VRAM, 0.125 GiB release tolerance;
- shared probe budgets: 28 for `coding`+`studio`, 20 for `vstudio`, including retries;
- finalists for the requested preference compared in `A→B→B→A` order, with the optional third
  round only under its declared dispersion and margin rules;
- one final smoke and multi-turn gate for the requested cell, plus the vision check for `vstudio`.

A confirmation round measures the warm-up and the three short requests only. It compares median
short end-to-end latency and the dispersion of that same triple, and the long request contributes to
neither, so measuring it there would decide nothing (D-074). The confirmed cell remains the sample
the search measured, so the recorded `prefill_tps` still comes from a full quick-bench.

An infeasible context costs one prudent probe, so the ladder continues downward. A `max_context`
search stops at the first context that measures a sample, because the scale descends and that
preference compares rivals only within its own context (D-075); `fast` and `balanced` walk the whole
ladder. On CPU the automatic run confirms the smallest measurable context, while an explicit
approved target confirms that target; `n_cpu_moe` stays null and no CPU offload axis is invented.
`--mode all` applies one preference to every selected mode; separate invocations may retain
different preferences. Each completed group
persists its own candidate records even if a later group produces none.

Records are `<mode>.candidate.json`, active `<mode>.json`, and rollback
`<mode>.previous.json`. Promotion is atomic; `--no-activate` keeps candidates and `--activate`
promotes existing candidates without new trials or preference changes. Recalibration touches only
the selected modes' lifecycle files. No calibration candidate is activated on the maintainer's
behalf.

### 5.7 Engine command

The builder expands only the `command_contract` of `engine.lock`. Every option token must belong to
`verified_flags`; unknown placeholders are invalid.

The command explicitly represents the physical model, context, sampling, host/port, metrics,
MTP/cache/mmap, UI, vision, and backend. `LaunchPlan.speculative` is `mtp2` or `disabled`, and
vision requires `disabled`; `coding` and `studio` keep the previous argv, `vstudio` keeps `--mmproj`
without MTP flags. Runtime `mode/v2` emits the validated extended sampling and reasoning values.
CPU receives no CUDA arguments. No flag originates from semantic hardcoding absent from the lock.

### 5.8 Engine and model

Engine order: `engine_path`, `PATH`, managed manifest. Every candidate passes the exact version and
help probes.

The default model is resolved from the managed store at `data/models` first, then at the lock's
revision according to the observed cache precedence (D-078). The filename, size, and SHA-256 must
match in either location. The filename and size are checked on every resolution; the SHA-256 is
recomputed unless a cached receipt under the cache root records the same path, size, modification
time, and expected digest, and writing that receipt is best-effort, so resolution is no longer
strictly write-free (D-076). A different model requires `model_path` and inherits no data from the
default, and is managed by neither `pull` nor `rm`. Do not use `--hf-repo`.

`pull` acquires every artifact the model needs — weights and vision projector — and nothing else:
MTP is a property of these weights, enabled by engine flags, not a separate download. It accepts
the `default_model_handle` of the lock as an optional argument and refuses any other name. It
writes only into the store, over HTTPS against the pinned revision, through a `.part` file
published by atomic rename, and writes the D-076 receipt on success. `engine install` performs the
same acquisition unless `--no-model` declines it. `rm` takes back exactly what `pull` wrote — the artifact, its
receipt, and the store directory once empty — and then, behind a separately asked confirmation, the
pinned artifacts in the Hugging Face cache under the confinement rules of D-079. That second group
is the one deliberate asymmetry: it may remove copies this tool did not download, which is why it is
never included in another confirmation. Nothing is ever written into that cache.

`model_alias_contract` declares the name `/v1/models` reports and is expanded after
`command_contract`, which leaves `command_contract_sha256` and every existing record valid (D-080).

Assets are selected per OS/backend, downloaded over HTTPS, verified, and activated only after the
probes complete. Ubuntu CUDA uses the pinned source until the lock verifies a prebuilt.

### 5.9 Processes, state, health, and logs

- state at `state_dir()/services.json`, version 1, plus the trial state of an unrotated calibration
  run, which `status` and `stop` sweep as well (D-071);
- process identity `pid + create_time`; a recorded PID this account cannot open is absent, never an
  error, because the launcher and its children share one account (D-071);
- atomic writes with a temporary file in the same directory, flush, and `replace`;
- corrupt state renamed to `services.corrupt-<timestamp>.json`;
- exclusive startup lock with a `pid + create_time` owner;
- a single managed service **per role**: one `engine`, and one optional `interface` in front of it
  (D-095). A record without a role is the engine role, so earlier state decodes unchanged. Only the
  engine role carries a model, engine release, context window, and backend;
- the port checked on `127.0.0.1`;
- `Popen` without a shell and a new Windows process group;
- stdout/stderr into the same timestamped UTF-8 log;
- 2 s health requests, 1 s polling; each role declares its own readiness contract and its own
  timeout, the engine's being the 15 minutes of the lock;
- READY = the exact status and JSON the role's contract declares. For the engine that is the lock;
  for Open WebUI it is `GET /ready` with `{"status": true}`, retrying 503, and never `GET /health`,
  which answers 200 before startup completes;
- a browser is opened only once every role a mode started has reported READY;
- stop: the interface before the engine, then terminate 10 s, then kill 5 s;
- `Ctrl-C` cleans up both and exits 130.

`status` and `stop` with no services exit 0.

### 5.10 Safe installation and uninstallation

`sudo`, elevation, automatic package managers, and `shell=True` are forbidden. Downloads into
`.part`, checksum before extraction, confined staging, immutable installations, and an atomic
manifest.

Extraction rejects absolute paths, drive letters, `..`, special files, and escaping links. Deletions
are limited to the managed data/cache after verification.

`uninstall` shows config/data/cache/state and the current Python installation, asks for a single
confirmation, refuses live services and symlinks, and does not remove uv. The model store lives
inside the data root, so the weights it holds are deleted with it. Weights that also exist in the
Hugging Face cache outlive that deletion and are offered afterwards as their own question, whose
refusal is the default and whose failure never turns a completed uninstall into an error (D-079). When the running command matches `uv tool dir/bora-workbench` exactly and owns the uv
receipt, a helper on the base Python waits for the process to exit and invokes
`uv tool uninstall bora-workbench` without a shell. A Python installation outside uv is not removed
on a guess and is reported explicitly as unchanged.

`update` reuses that identity check and that deferred helper to run `uv tool install --force` on a
wheel it has already verified against the release `SHA256SUMS` (D-073). It installs only a strictly
newer version, refuses a live managed service, and leaves the managed engine, the configuration,
and the calibration records exactly as they were; whether the new version requires
`bora engine install` is read from the downloaded wheel's own `engine.lock` and reported.

### 5.11 Errors and exit codes

| Case | Code |
|---|---:|
| success, empty state, warnings only | 0 |
| operational error or failed validation | 1 |
| invalid CLI input or configuration | 2 |
| `Ctrl-C` | 130 |

Expected errors go to stderr, actionable and without tracebacks. Operational exceptions are not
ignored.

### 5.12 Global prohibitions

- no `shell=True`, `eval`, `exec`, elevation, or `0.0.0.0` bind;
- no network in tests or at import;
- no side effects at import;
- no incompatible schema without a new version;
- no undocumented fallback;
- no changes to the user config, and no writes into the Hugging Face cache;
- no deletion from that cache outside the pinned artifacts of a locked repository, and never
  without a separately asked confirmation (D-079);
- no deletions outside the managed roots;
- no disabled TLS/checksums;
- no feature in code before its step is active; design documents may describe later ones;
- no plugins or speculative abstractions; no async except Textual's D-085 presentation boundary
  after its dependency review, and no async core API or general executor;
- no remote operations without explicit authorization.

---

## 6. Working protocol

### 6.1 Before changes

1. Read this document and `AGENTS.md` in full.
2. Read the relevant current documentation, locks, schemas, tests, and evidence.
3. Run `git status` and preserve pre-existing changes.
4. Run `uv sync --frozen`, Ruff, and pytest as a baseline.
5. If the starting point is not green, make the problem visible.
6. Scope one step and one area only: core or content.

### 6.2 During

- implement only the authorized perimeter;
- update the current documentation, do not create new side plans;
- record new durable decisions here;
- use offline fakes in tests;
- stop on contradictions the source hierarchy cannot resolve.

### 6.3 Before finishing

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
```

If packaging or resources change:

```bash
rm -rf dist
uv build
uv run --frozen python scripts/verify_wheel.py
uv run --frozen python scripts/verify_uninstall.py
```

Then `git diff --check`, inspection of the diff/staging area, and a report with the files, behavior,
tests, limits, and remaining manual verifications. A local commit is authorized only when requested;
pushes and publication are not.

---

## 7. Historical 0.1 stabilization

### 7.1 Historical registry recovery closed

Run `29739366272` attempted to publish distribution `qwen-launcher==0.1.0` and failed before any
PyPI project existed. On 26 July 2026 the maintainer closed that recovery rather than transferring
the old bytes to the renamed project. Versions `0.1.0`–`0.1.6`, their package `qwen_launcher`, their
command `qwen-launcher`, and their artifact names remain historical facts.

D-070 also closes the later `bora-workbench` registry path before any upload. Current distribution
is GitHub Releases only; no historical wheel or sdist is rebuilt, relabelled, or republished.

### 7.2 Release 0.1.1 completed

0.1.1 distributes D-051, D-052, the progress UX, and D-053. The maintainer attested the real Ubuntu
and Windows v4 Gates, including record reuse, and decided `RELEASE` on 23 July 2026. The authorized
publication is limited to the tag and the GitHub Release; the PyPI job stays disabled.

### 7.3 Release 0.1.2

Version `0.1.2` collects `calibration/v5`, the calibrated parameters in `doctor`, the shared
terminal presentation with literal dynamic text, the Ubuntu CUDA build percentage, the Node 24
actions, and the automatic uninstall of the uv tool.

On 23 July 2026 the maintainer decided `RELEASE` and authorized the commit, push, tag, and GitHub
Release without first repeating a clean installation, the upgrade from `0.1.1`, v5 calibration, and
a complete uninstall on both platforms. The release workflow must still be green and remains the
only source of the artifacts. The omitted manual verifications become post-release work, not a
passed Gate. PyPI and the activation of the three local candidates stay excluded.

### 7.4 Release 0.1.3

Version `0.1.3` distributes D-058–D-061 while keeping `calibration/v5` as the default. On 24 July
2026 the maintainer authorized the commit, push, tag, and GitHub Release ahead of the local spike
runs. Those verifications stay post-release and are not a passed Gate. PyPI, candidate activation,
and Phase 2 stay excluded; the public artifacts come only from the green workflow.

### 7.5 Cross-context decision gate (historical)

A repository-only spike package once prepared a manual comparison over 131K/65K/32K to decide
whether the three-envelope protocol was worth implementing. The protocol now implements that
comparison itself, per context step and on the operator's own hardware, so the separate package was
removed with D-067. The decision it was meant to inform is settled; its thresholds survive in the
protocol as the `fast`/`balanced` deadband and ceiling.

### 7.6 Release 0.1.5

Version `0.1.5` distributes D-065: the fully English repository and the calibration evidence
republished with a regenerated digest chain. It is a content and documentation release — the Python
sources change only in the version fallbacks, and no contract, lock, schema, or measured value moves.

The release exists for a concrete reason, not for cosmetics: the translated evidence changed the
bytes the report and policy digests are computed over, so the artifacts published for `0.1.0`–`0.1.4`
no longer match the branch. `0.1.5` is the version that realigns them. Earlier artifacts stay
untouched, and PyPI stays excluded.

### 7.7 Release 0.1.6

Version `0.1.6` distributes D-067: one working calibration protocol. It is the first release whose
calibration engine has been observed to complete on real hardware; `0.1.4` and `0.1.5` shipped it as
code that never ran a full run (D-066).

It is a breaking change for local state and only for that. A record written by `0.1.5` or earlier
declares a schema this version no longer reads, so it is diagnosed as superseded and the operator
re-runs `calibrate`. No migration is attempted, because the removed formats recorded a different
protocol's evidence and inventing the missing fields would fabricate measurements. The engine, the
model, the mode content, and `command_contract_sha256` are unchanged, so an existing installation
keeps launching exactly as before while its records are re-measured.

Hardware validation covers Ubuntu only. Windows keeps the full offline suite in CI on every release
tag, and its hardware validation stays open work.

### 7.8 Heterogeneous evidence

When it becomes available, repeat calibration with `--no-activate` on materially different hardware,
review privacy, and update the report/policy in a declarative PR. The outcome is not reconstructed by hand
and does not retroactively turn the single current host into universal evidence.

---

## 8. Post-0.2 backlog

D-068 postpones the former 0.2 roadmap. Backlogs A–C are possible later milestones and still
require an explicit future decision. Backlog D is complete through D-092; its historical execution
steps remain below as the provenance of the current workbench.

### Backlog A — Skills and deterministic router

**Objective:** routable content without regular expressions or contributed code.

The `skill/v1` contract: Markdown with YAML frontmatter read with `yaml.safe_load`; a name equal to
the file; a description; `routing.phrases` as `[phrase, weight]` pairs; at least three positive
examples; at least one negative example; `co_activate`, possibly empty; a Markdown body as the
content.

Normalization:

1. truncate the input to 20,000 characters;
2. Unicode NFKD;
3. remove combining characters;
4. `casefold()`;
5. replace non-alphanumeric sequences with a space;
6. collapse spaces and trim.

A normalized phrase is a contiguous token sequence and contributes at most once.

Routing:

- sum the weights;
- apply a threshold;
- sort by descending score, then alphabetical name;
- `top_k` bounds the direct selections;
- valid co-activations are added afterwards, without duplicates or recursion, and may exceed
  `top_k`;
- a positive example must rank its own skill first;
- a negative one must not select it.

Activities:

1. add `pyyaml` and update the lock;
2. the schema, a safe parser, and the initial `epsilon-delta`, `math-solver`, `debug-systematic`,
   `linux-ops` skills;
3. a pure router and tests integrated into `validate`;
4. a new mode schema with `prompt` and `skills` (`auto` or a list);
5. declarative migration of the modes in a PR separate from the core when needed;
6. no regular expressions in the schema, parser, or documentation.

Tests: normalization, accents, case, punctuation, a phrase counted once, ties, threshold, top_k,
co-activations, missing references, positives/negatives, hostile frontmatter, and v1/v2
compatibility.

### Backlog B — Managed Open WebUI (complete)

**Objective:** an optional, upstream-owned browser interface in front of the managed engine, started
and configured by bora and modified by it in no way.

Shipped in `0.5.0`. D-094 answered the ten questions of the design record `WEBUI_PLAN.md`; D-095
dropped the spike, the digest lock, the immutable versioned installations, and the mode-document
interface field, and directed the rest to be built. Where that file and this document disagree, this
document wins.

`bora engine install` puts `open-webui==0.11.0` into `data_dir()/open-webui/venv` with `uv`, beside
the engine and the weights, recording the version last so an interrupted install is rebuilt rather
than trusted; `--no-webui` declines it and `bora webui install` adds it later (D-096). With it
installed, `studio` and `vstudio` start it as a second managed service and open it; without it they
keep opening the integrated llama.cpp interface, which is also the fallback when the interface fails
to start — the engine keeps serving in that case, and the mode does not exit.

`bora webui remove` frees the environment and asks separately about the interface data, which is
user content, in the shape D-079 established for weights. `bora uninstall` takes both with the data
root and says so in its preview. Neither removal follows a symlink out of the managed root.

bora configures it entirely through its child process environment and never calls its API: no
session, no credential, no database write, no packaged content, no `sync`. D-080 already makes the
engine report `model_alias_contract.alias` at `/v1/models`, so the picker names the model with no
provisioning step. Skills, the system prompt, and web search are the user's own, added through
upstream's own screens.

The environment is assembled in one place and shown by `doctor`: a dedicated data directory under
`data_dir()`, the loopback host passed as an argument and never read from configuration, a generated
session key held in the state root with owner-only permissions and printed nowhere, authentication
disabled, environment values seeding the first boot only, no embedding model, the version check off,
title/tags/follow-up off, Ollama off, the local OpenAI endpoint and a placeholder key. Both the
frontmatter `pip install` and every stored function are disabled, so no third-party Python runs
inside a bora-started process and nothing mutates the managed environment. `WEBUI_NAME` is never set
and an inherited one is removed: the interface keeps its own name everywhere, no branding clause is
engaged, no user-count exemption is invoked, and the upstream licence ships in
`resources/notices/open-webui-LICENSE`.

The account is upstream's: with authentication disabled it creates a fixed local administrator on the
first page load, with a publicly documented password. That is one-way inside the same data directory,
and re-enabling authentication later leaves that password in place. `docs/operations.md` states both,
and states that the loopback rule of section 5.12 is what keeps an unauthenticated administrator
console local.

READY is `GET /ready`, never `GET /health`, which answers 200 before startup completes. The browser
opens only once both roles report READY. Section 5.9 now admits one managed service per role, with an
ordered stop that takes the interface down first.

What was deliberately not built, and why, is D-095: no evidence chain, no `open-webui.lock`, no
staged activation, no interface field in the mode document. What remains unmeasured is in the open
work of section 0 and is claimed as a figure nowhere.

### Backlog C — Standalone benchmark and final doctor

`benchmark --mode <id>` requires a live server and reads the mode, model, engine, record or
fallback, context, and `n_cpu_moe` from the state. It reuses `benchmark/v1` exactly: warm-up
excluded, five 256-token measurements, no concurrent client, min/median/max, and full metadata.

With a local record it shows the difference from the recorded median without modifying it. Without a
record it creates no calibration and points to `calibrate`.

Also complete:

- `doctor` with ✅/⚠️/❌ status and a remedy for every non-green row;
- documentation distinguishing benchmark, calibration, and regression;
- a repeatable regression check without an invented universal threshold;
- PR templates for evidence and skills.

Tests: missing/incompatible server, warm-up, five measurements, median, record present/absent,
comparison, no content changes, no real network, and metadata from the state.

### Backlog D — Interactive front end

**Objective:** an optional, read-mostly terminal dashboard and exact command composer over the
existing CLI, never a second launcher runtime.

The execution plan that carried this milestone (`TUI_PLAN.md`) and its design record (`TUI.md`) were
completed and then removed from the repository; their decision answers are D-083 through D-085 in
the table above, and the shipped result is documented in [`docs/tui.md`](docs/tui.md). The implementation keeps
current command names and the flat package tree; extracts configuration provenance, non-mutating
service/model inspection, shared pi context selection, and doctor/workbench snapshots; reviews
Textual before any interaction loop; the completed plan added seven read-only screens,
deterministic advice, recursively parser-checked command composition, and same-process dispatch
after UI teardown. D-092 subsequently makes bare `bora` their only entry and removes `bora tui`.

Opening and refresh perform no network, hashing, writes, cleanup, directory creation, service start,
or polling. Bounded diagnostic subprocess probes are allowed in one presentation worker. Every real
prompt and operational rule remains in its existing CLI callback. Motion is optional and must be
plain-mode-safe and measured before it ships. Open WebUI was absent from the snapshot, screens,
actions, and process-state shape throughout this milestone; `0.5.0` added it to the snapshot and the
state under D-095, and D-096 then gave the Setup screen the interface facts and its install and
removal actions. The read-only screens still start no service, install nothing, and open no browser:
every acquisition and confirmation remains in its existing CLI callback.

Tests are offline and cover side-effect refusal, first-frame responsiveness, serialized refresh,
canonical record labels, parser acceptance of every reachable argv, terminal restoration, and exact
exit propagation. Manual Ubuntu and Windows terminal, signal, update, and uninstall checks remain
release criteria and are never reported as a calibration Gate.

### Local 0.2.0 finalization

D-068 authorizes the final `0.2.0` version for the repository/package refactor without claiming a
passed Human Gate. The local audit, suite, build, isolated wheel/uninstall checks, and feasible
Ubuntu manual checks must be reported exactly. Push, tag, GitHub Release, PyPI, remote settings, and
candidate activation remain individually authorized operations.

### Local 0.2.1 finalization

D-070 authorizes the `0.2.1` commit, push, and tag after the local suite succeeds, and the GitHub
Release only after the tag's release CI succeeds. The release uses the exact checksum-manifested
bundle produced by CI. Manual platform and hardware runs are waived and remain explicit limitations, not a passed Gate. Registry upload,
remote-setting changes, and candidate activation are not authorized.

---

## 9. Open acceptance criteria

### 0.1 stabilization

- [x] The maintainer closed the failed `qwen-launcher==0.1.0` PyPI recovery; historical artifacts
  remain under their original identity and are not republished.
- [x] Registry verification for 0.1 is explicitly not pursued; D-070 keeps current distribution on
  GitHub Releases only.
- [x] Post-release fixes distributed only with the newly authorized version `0.1.1`.
- [x] `calibration/v4` really verified on Ubuntu and Windows before 0.1.1.
- [x] The `RELEASE` decision for `0.1.2` is explicit and records that the manual Gate was not
  repeated.
- [x] The `0.1.2` publication uses only the artifacts of the authorized green workflow.
- [ ] Complete the `0.1.2` post-release manual verifications on Ubuntu and Windows.
- [x] The `RELEASE` decision for `0.1.3` records that the real spike is post-release and is not
  presented as a passed Gate; PyPI and Phase 2 stay excluded.
- [x] The repository is fully English and the regenerated evidence digest chain verifies from the
  checkout; the published `0.1.5` artifacts embed the new digests.
- [~] Heterogeneous evidence added when available, without transferring envelopes between hosts.
- [x] D-067 superseded the cross-context spike and removed its runner without inventing a
  `GO`/`NO-GO` verdict or a passed Gate.

### Milestone 0.2

- [x] Distribution/package/command/repository identity is `bora-workbench` / `bora_workbench` /
  `bora` / `tommasonovelli/bora-workbench`.
- [x] The maintainer selected the refactor as final `0.2.0` without claiming a passed Gate.
- [x] Router, Open WebUI, sync, and standalone benchmark are explicitly postponed beyond 0.2.
- [x] Local `0.2.1` suite, build, and isolated install/uninstall checks are complete; manual
  platform and hardware runs are waived and are not a passed Gate.
- [ ] Cross-platform CI confirms the tested `0.2.1` release commit and produces the exact bundle.
- [x] D-070 authorizes the `0.2.1` commit, push, tag, and GitHub Release in this session while
  excluding registry upload, remote-setting changes, candidate activation, and a Gate claim.
- [x] The release workflow and installers expose no package-registry publication or install path.

### Milestone 0.4

- [x] D-083–D-088 authorize the reduced TUI boundary, implementation, scoped acceptance, local
  finalization/tag after green local checks, and GitHub-only release after green tag checks.
- [x] `TUI_PLAN.md` A2–E9 and the automated F1 acceptance checks are complete.
- [~] Ubuntu pseudo-terminal presentation and handoff checks are recorded, but the manual visual,
  real foreground `Ctrl-C`, and all Windows TUI checks were unavailable and are not called passed.
- [x] `0.4.0` finalization follows automated acceptance; D-088 authorizes the push, tag, and GitHub
  Release from the exact green workflow bundle.
- [x] `0.4.1` redesigns the front end's presentation only — terminal background, central menu,
  full-window sections, per-action flag toggles — leaving the read-only boundary, snapshot, handoff,
  and motion budget of D-084–D-087 unchanged (D-089).
- [x] D-090 adds `bora pi launch` and the continuous multicolour Unicode home decoration without
  changing service launch, snapshot collection, or core runtime contracts.
- [x] D-091 authorizes `0.4.2` finalization, tag, and GitHub-only release after green local and tagged
  automation, while explicitly waiving rather than passing the new manual observations.
- [x] D-092 makes bare `bora` the only workbench entry, unifies every screen under the blue/white
  identity and shared wind/sea graphics, preserves returning output until acknowledgement, and
  authorizes `0.4.3` through the same exact green GitHub-only release path.
- [x] D-093 keeps that shared graphic animating on every page from one 6 fps timer, leaves every kill
  switch and core contract untouched, and authorizes `0.4.4` through the same release path while the
  manual visual/CPU observation stays open.
- [~] The `0.4.1` presentation checks are programmatic pseudo-terminal runs at 60x20, 80x24, and
  100x32; manual visual and Windows terminal checks were not performed and are not called passed.
- [x] Backlog B was deferred throughout this milestone and shipped separately in `0.5.0` under
  D-094 and D-095, without the spike D-094 had made its precondition.

---

## 10. Process references

- Python 3.12 `importlib.resources`:
  <https://docs.python.org/3.12/library/importlib.resources.html>
- CPython 3.12.13: <https://www.python.org/downloads/release/python-31213/>
- uv 0.11.28: <https://github.com/astral-sh/uv/releases/tag/0.11.28>
- uv build backend: <https://docs.astral.sh/uv/concepts/build-backend/>
- GitHub Actions security: <https://docs.github.com/en/actions/reference/security/secure-use>
- Open WebUI environment: <https://docs.openwebui.com/reference/env-configuration/>

For `llama.cpp`, the lock and evidence of the pinned release prevail, not moving links to the
current branch. For Open WebUI there is a pinned version but no digest lock (D-095), so rule 6 of
section 2 applies: the source read at the tag that version names outranks that documentation page,
and a citation whose quoted code no longer matches means the reading is stale, not that the code is
wrong.

---

## 11. Closing rule

A piece of work is finished only when the code, tests, current documentation, locks, and evidence
agree. A local result does not replace CI or declared manual gates. Doubts and limits stay visible;
they do not become silent fallbacks or claims.
