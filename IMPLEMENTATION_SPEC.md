# bora-workbench — Implementation specification and roadmap

This is the only normative plan in the repository. It describes the constraints future work must
preserve and the activities not implemented yet. The behavior available today is documented in
[`docs/`](docs/README.md); the measured provenance of the locks and reports is kept in
[`evidence/`](evidence/README.md).

## 0. Actual status and tracker

Updated on 26 July 2026.

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

### Open work

- [ ] Perform, as `0.1.2` post-release verification, the real upgrade from `0.1.1`, calibration
  without activation, and a complete uninstall on Ubuntu and Windows.
- [ ] Validate the trial adapter on Windows: server startup, monitoring with the 0.5/2.0/0.125
  reserves, quick-bench, and gate. The logic is covered by offline tests on both platforms.
- [~] Repeat `calibrate --no-activate` on materially different hardware; coverage remains
  `GATE-PARTIAL` and no envelope is transferred between hosts.
- [ ] Complete the `0.2.1` automated suite, cross-platform release CI, exact artifact verification,
  and documented manual limitations without calling them a Gate.
- [ ] Router, managed Open WebUI, sync, and standalone benchmark remain post-0.2 backlog.

No local candidate is activated and no post-0.2 backlog item is started without an explicit
request. Pushes, tags, releases, uploads, and remote settings always require authorization in the
current session.

---

## 1. Product and perimeter

### 1.1 Current product

`bora-workbench` is a specialized local distribution built around
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`. It detects the hardware, verifies the model and
engine, builds a plan, governs `llama-server`, exposes three modes, and measures one envelope
locally for each machine.

It is not a generic model manager, a plugin framework, or a multi-backend orchestrator.

### 1.2 Platforms

- Ubuntu 22.04+ x86-64;
- Windows 11 x86-64;
- CPU, or a single NVIDIA CUDA GPU;
- services exclusively on `127.0.0.1`.

Out of perimeter: macOS, ARM, Vulkan, ROCm, distributed multi-GPU, auto-update, native GUI, Python
plugins, deleting the Hugging Face cache, and arbitrary user modes.

### 1.3 The 0.2 boundary

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
| `process.py` / `_process_*` | process, health, state, lock, status, and stop |
| `uninstall.py` / `_tool_uninstall_helper.py` | confined removal of the roots and handoff to the current uv installation |
| `validation.py` / `_validation_*` | schemas and semantic checks |
| `resources/__init__.py` | `importlib.resources` access |
| `routing.py` (future) | pure skill normalization and scoring |
| `webui.py` (future) | Open WebUI lock, environment, installation, and process |

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

### 5.2 Configuration and paths

Precedence: environment > TOML > defaults. The whole TOML is validated before the overrides. Unknown
keys and malformed values are errors; the launcher does not modify the file.

| Key | Environment | Default |
|---|---|---|
| `model` | `BORA_MODEL` | the pinned model |
| `model_path` | `BORA_MODEL_PATH` | `None` |
| `llama_port` | `BORA_LLAMA_PORT` | `8080` |
| `engine_path` | `BORA_ENGINE_PATH` | `None` |
| `open_browser` | `BORA_OPEN_BROWSER` | `true` |

Ports 1–65535. Environment booleans: `true/false`, `1/0`, `yes/no`, `on/off`. Only the two path
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

An infeasible context costs one prudent probe, so the ladder continues downward. On CPU the
automatic run confirms the smallest measurable context, while an explicit approved target confirms
that target; `n_cpu_moe` stays null and no CPU offload axis is invented. `--mode all` applies one preference to
every selected mode; separate invocations may retain different preferences. Each completed group
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

The default model is resolved read-only at the lock's revision according to the observed cache
precedence. The filename, size, and SHA-256 must match. A different model requires `model_path` and
inherits no data from the default. Do not use `--hf-repo`.

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
- a single managed service;
- the port checked on `127.0.0.1`;
- `Popen` without a shell and a new Windows process group;
- stdout/stderr into the same timestamped UTF-8 log;
- 2 s health requests, 1 s polling, 15-minute total timeout;
- READY = the exact status and JSON from the lock;
- stop: terminate 10 s, then kill 5 s;
- `Ctrl-C` cleans up and exits 130.

`status` and `stop` with no services exit 0.

### 5.10 Safe installation and uninstallation

`sudo`, elevation, automatic package managers, and `shell=True` are forbidden. Downloads into
`.part`, checksum before extraction, confined staging, immutable installations, and an atomic
manifest.

Extraction rejects absolute paths, drive letters, `..`, special files, and escaping links. Deletions
are limited to the managed data/cache after verification.

`uninstall` shows config/data/cache/state and the current Python installation, asks for a single
confirmation, refuses live services and symlinks, never touches the Hugging Face cache, and does not
remove uv. When the running command matches `uv tool dir/bora-workbench` exactly and owns the uv
receipt, a helper on the base Python waits for the process to exit and invokes
`uv tool uninstall bora-workbench` without a shell. A Python installation outside uv is not removed
on a guess and is reported explicitly as unchanged.

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
- no changes to the user config or the Hugging Face cache;
- no deletions outside the managed roots;
- no disabled TLS/checksums;
- no anticipated future features;
- no plugins, async, or speculative abstractions;
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

D-068 postpones the former 0.2 roadmap. The items below are possible later milestones, not
requirements or promises for `0.2.0`. Every item still requires an explicit future decision.

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

### Backlog B — Managed Open WebUI and sync

**Precondition:** the maintainer approves a precise version after a real spike on Python, CPU-only
dependencies, command, health, Functions, prompts, and environment variables. The spike produces
`resources/open-webui.lock` and separate evidence.

Installation:

- immutable venvs in `data_dir()/open-webui/installations/`;
- staging on the same filesystem;
- verification of the version, imports, and executable;
- `installed.json` inside the installation;
- an atomic `current.json` with a confined relative path;
- a failure leaves the previous manifest and version intact;
- cleanup of inactive managed environments only.

Future configuration: `webui_port=8081` and `BORA_WEBUI_PORT`; port 1–65535 and different from
`llama_port`.

A minimal environment, only after the lock has been verified: a dedicated data dir, host
`127.0.0.1`, persistent config disabled, authentication disabled for the local service only, Ollama
off, the local OpenAI endpoint, and a placeholder key. The user is told that UI changes do not
persist.

Fallback: if llama-server is READY but the WebUI fails, keep it running, show the log, and open the
built-in UI when allowed. If the mode requires a UI and none is available, stop the services and
exit 1.

`sync` generates the function, prompts, and import instructions under `data_dir()/sync-out/`. A
static Python template; rules and content serialized as JSON data, never interpolated as code. No
API writes in this step.

Tests: valid/partial/failed installation, manifest, port configuration, environment, health,
fallback, multi-service state, hostile content, and reproducible output.

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
current branch.

---

## 11. Closing rule

A piece of work is finished only when the code, tests, current documentation, locks, and evidence
agree. A local result does not replace CI or declared manual gates. Doubts and limits stay visible;
they do not become silent fallbacks or claims.
