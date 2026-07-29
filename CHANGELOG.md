# Changelog

Relevant changes are recorded here by version. Future plans do not belong in the changelog: they
live in `IMPLEMENTATION_SPEC.md`.

## [0.4.0] - 2026-07-29

### Added

- `bora tui`, an optional seven-screen terminal workbench for Overview, Modes, Calibration, Setup,
  Pi, Settings, and This installation (D-083–D-088). Opening and explicit refresh collect one
  structured local snapshot without network, model hashing, writes, cleanup, directory creation, or
  managed-service startup. Static chrome renders first, one Textual thread worker owns the
  synchronous collector, input stays responsive during bounded probes, and repeated refreshes never
  overlap.
- Exact text-visible composition of every supported TUI action. Textual ends and restores the
  terminal before the existing Click/Typer leaf callback runs in the same process, so real
  preflights, confirmations, subprocesses, network, writes, and exit codes remain unchanged.
  Successful returning actions reopen with a concise snapshot comparison; foreground modes,
  calibration, update, and uninstall are terminal. Uninstall adds typed `remove` friction without
  answering either real removal question.
- A staged calibration composer that can produce only valid current mode, preference, activation,
  and measurable-context combinations. Candidate activation is a separate route and the exact
  command receives final review before the real CLI confirmation.
- Optional deterministic wind/sea decoration at 8 fps. It settles after about three active seconds
  and is disabled by plain presentation, `NO_COLOR`, `TERM=dumb`, limited encoding, small terminals,
  another screen, focus loss, or `BORA_TUI_MOTION=off`; malformed values exit 2. Static text and all
  actions remain complete without colour or motion.

### Changed

- Shared diagnostics now expose immutable `DoctorSnapshot` and `WorkbenchSnapshot` read models,
  receipt-aware model inspection, non-cleaning service inspection, configuration provenance, and
  one shared pi context-window selection. The CLI, snapshots, and TUI use one canonical calibration
  record vocabulary.
- `calibrate` declares its full public option surface through Typer; contradictory pi options are
  input errors; expected validation resource I/O failures no longer leak tracebacks; and
  `engine status` keeps its difference report on one redirectable stream.
- Textual `8.2.8` and its frozen MIT-licensed dependency graph join the runtime under the narrow
  presentation-only concurrency boundary (D-086).

### Verification limits

- Automated tests and scoped Ubuntu pseudo-terminal checks cover sizes, plain/full presentation,
  refresh/navigation/quit, returning `doctor`, terminal `coding` preflight, alternate-screen exit,
  static settlement, and isolated package uninstall. The checks were not manual visual checks; a
  real foreground model process and its `Ctrl-C` restoration were unavailable, and Windows TUI
  checks were not performed. None is described as passed or as a calibration Gate.
- The engine, model, calibration protocol, record format, command contract, reserves, and candidate
  lifecycle are unchanged; no candidate is activated and coverage remains `GATE-PARTIAL`.

## [0.3.2] - 2026-07-28

### Added

- `bora pi remove` deletes the provider entry that `bora pi` writes, leaving pi installed and every
  other provider in `models.json` untouched (D-082). It works with pi absent too: an entry written
  earlier outlives the package, and that is exactly when removing it has to remain possible.
- `bora pi uninstall` removes pi itself. It shows `npm uninstall -g @earendil-works/pi-coding-agent`,
  asks, runs it, and then looks at PATH again — an installation made another way, such as the
  vendor's Windows script, is reported as still present instead of being described as removed.
  Afterwards it asks separately about the provider entry, because the package belongs to npm and
  the entry belongs to a file that belongs to pi.

### Changed

- `bora pi` hands over the context window this machine actually serves, and says where the number
  came from (D-082): a managed service already listening on the configured port, otherwise the
  active `coding` calibration record, otherwise the verified baseline with the diagnostic that
  explains it. Connecting while a service was running always wrote `8192`, because reuse of the
  record re-checks free memory that this very service is holding.
- A calibration run that activates a `coding` record ends by naming the window that record now
  carries and the command that hands it to pi — `bora pi`, or `bora pi --install` when pi is not
  installed. The entry is a copy: nothing rewrites it when a new record is activated. `--no-activate`
  prints no such line, because a candidate steers no launch.

## [0.3.1] - 2026-07-28

### Changed

- Removal takes the cached repository with its last snapshot, `refs` included (D-079). Deleting the
  pinned artifacts used to leave a stub whose `refs/main` still named a revision whose files no
  longer existed. A repository that still holds another revision keeps everything, and repositories
  belonging to other tools are still never examined.
- `rm` now takes back everything `pull` wrote, and only that: the artifact, its verification
  receipt, and the store directory once it is empty. A receipt naming a file that no longer exists
  claimed a verification nobody could check, and an empty directory is a leftover.
- `pull` and `rm` accept the pinned model by name: `bora pull qwen` and `bora pull` are the same
  request. The name is declared as `default_model_handle` in `engine.lock`, and any other name
  fails immediately instead of being read as the default. `command_contract_sha256` is unchanged.

### Fixed

- The test suite no longer appends temporary paths to the verification receipt of the machine
  running it. The model store fixture redirects the receipt root, as the engine tests already did.

## [0.3.0] - 2026-07-27

### Added

- `bora pull` downloads the pinned model (D-078). The artifacts named by `engine.lock` are fetched
  over HTTPS from the pinned revision — so a moved branch or a re-uploaded file cannot change what
  arrives — into a managed store at `<data root>/models`, and are accepted only when name, size, and
  SHA-256 all match. On a terminal each artifact shows transferred bytes against the total, the
  measured rate, and a computed ETA. Bytes go through a partial file and are published by atomic
  rename, so an interrupted download never leaves something that looks complete, and rerunning
  resumes at file granularity. A completed download also writes the D-076 receipt, so the first
  launch afterwards does not rehash about 21 GiB.
- `bora engine install` performs that same acquisition once the engine is active, unless
  `--no-model` declines it. A first setup is now one command instead of three.
- `bora rm` deletes the pinned model and reports the space freed (D-079). It asks up to two
  questions, both defaulting to no: the copies in the managed store, and then — separately — the
  copies in the shared Hugging Face cache. `--keep-hf` skips the second entirely and `--dry-run`
  lists every file and byte count without asking or deleting anything.
- `bora pi` connects the [pi](https://pi.dev/) coding agent to the local service (D-081). It writes
  one provider named `bora` into pi's own `models.json`: the loopback base URL from the configured
  port, a placeholder key the managed server ignores, and the model id `Qwen 3.6`, with the context
  window taken from this machine's local record when one applies. The entry is shown first, the
  confirmation defaults to no, the previous file is kept as `models.json.bak`, the replacement is
  atomic, and every other provider is preserved. `--print` writes nothing; `--install` delegates to
  `npm install -g --ignore-scripts` after showing the command, and pins no digest for pi.

### Changed

- Model resolution prefers the managed store and falls back, read-only, to the pinned Hugging Face
  snapshot (D-078). Weights acquired before this version, or by any other tool, keep launching from
  where they already are and are never downloaded twice.
- The API reports the model as `Qwen 3.6` (D-080). The pinned `b10011` `--help` lists `--alias`, so
  the flag joins `verified_flags` and the name is declared in a new top-level
  `model_alias_contract`. It is deliberately outside `command_contract`: `command_contract_sha256`
  binds every calibration record to those exact bytes, and a name that changes no measured behavior
  must not supersede a single record. **The digest is unchanged and existing records stay valid.**
- `uninstall` takes the model store with the data root it already owns, and then asks separately
  about weights that survive in the Hugging Face cache. That question defaults to no, and neither
  refusing it nor failing it turns a completed uninstall into an error.
- Deleting from the Hugging Face cache is now possible, confined by construction (D-079): only a
  file directly inside the pinned `snapshots/<revision>/` of the locked repository, following a
  symlinked entry no further than that repository's own `blobs/`, keeping a blob another snapshot
  still references, refusing a symlinked cache directory, and pruning only already-empty
  directories. Repositories belonging to other tools are never examined. **Writing into that cache
  stays forbidden.**

## [0.2.4] - 2026-07-27

### Changed

- A paired confirmation round measures the short series only (D-074). It compares median short
  end-to-end latency and the dispersion of that same triple, both of which come from the three short
  requests, so the pinned 23180-token long request was measured four to six times per confirmation
  and never read. The same number of fresh processes still run, in the same `A→B`/`B→A` order, under
  the same third-round rule, and the confirmed cell is still the sample the search measured — so the
  recorded `prefill_tps` still comes from a full quick-bench.
- A `max-context` search stops at the first context that yields a sample (D-075). The approved scale
  descends and that preference compares rivals only inside its own context, so no smaller step can
  change the selected cell, the finalist, or the gate rival. `fast` and `balanced` compare latency
  across contexts and still walk the whole ladder. An infeasible context still costs one prudent
  probe and the ladder still continues past it.
- The model's SHA-256 is verified against a cached receipt instead of being recomputed on every
  `calibrate` and every mode launch (D-076). Verifying the pinned artifacts reads 21.11 GiB, plus
  0.84 GiB of projector for a vision mode, which ran silently before any output appeared. The locked
  filename and the exact byte size are still checked every time; only the digest is skipped, and only
  while the path, size, modification time, and the digest `engine.lock` expects all still match. The
  receipt lives under the cache root and writing it is best-effort, so an unwritable cache costs the
  next run a rehash rather than the launch. Model resolution is therefore no longer strictly
  write-free.

### Added

- A progress bar for a full model verification, on `calibrate` and on the mode launches. It appears
  only when the digest is actually recomputed, so a run covered by a receipt prints nothing.

## [0.2.3] - 2026-07-27

### Added

- `bora update` installs the newest published GitHub Release. It prints the installed and the
  published version, refuses anything that is not strictly newer, downloads that release's
  `SHA256SUMS` and wheel over HTTPS while rejecting any hop that leaves HTTPS, verifies the wheel's
  SHA-256 against the manifest, and installs it with
  `uv tool install --force --python 3.12.13`. This is the same trust chain as the documented manual
  installation; the release manifest is a checksum list, not a signature. `--check` reports without
  downloading anything.
- **The managed engine is deliberately left installed.** It lives under the data root, so replacing
  the Python tool does not touch it, and an update neither redownloads nor reactivates it. Instead
  the command reads `engine.lock` out of the downloaded wheel and reports whether the new version
  keeps the active `llama.cpp` release or whether `bora engine install` is now required.
  Configuration, calibration records, and the model are equally untouched.
- `update` refuses a live managed service, because the running launcher still holds the environment
  uv has to replace, and refuses an installation `uv tool` does not own, naming the documented
  installer instead of guessing.

### Changed

- The deferred uv handoff introduced for `uninstall` now runs any uv command and moved to
  `_tool_handoff.py` with its child in `_tool_helper.py`. Both `uninstall` and `update` need uv to
  run after the process exits, because Windows cannot delete or replace the environment of the
  process that is still executing. Exit code 0 from `update` therefore reports a *scheduled*
  installation; uv prints its own result on the same terminal a moment later, and `bora --version`
  in a new shell is the confirmation.

## [0.2.2] - 2026-07-26

### Fixed

- Stop a redirected calibration from dying on its own progress line. The line carried `≤` and `≈`,
  which a legacy Windows code page cannot encode, and the resulting `UnicodeEncodeError` reached
  the trial and ended the whole run. Progress is now ASCII and, more importantly, a console that
  cannot accept an event stops receiving them instead of raising, which is what the module already
  promised.
- Classify a non-success HTTP status by what it means. Every status was retryable, so the permanent
  `400` a too-small context returns was retried once and then reported as
  `remained retryable after one retry`; only server-side and wait-and-retry statuses are retryable
  now, matching the rule already applied to health responses.
- Search only the context steps the pinned quick-bench long request fits in. That request measures
  23180 prompt tokens, so `16384` and `8192` could never produce a sample and CPU calibration,
  which used the `8192` baseline, could never succeed at all. The ladder and the CPU confirmation
  now stop at `32768`, and an explicit `--target-ctx` below it is refused as input before any
  process starts. The byte-pinned payload is unchanged.
- Let calibration run on a Windows desktop. The GPU compute-context population was required to be
  immutable per run, which no WDDM host can offer: one unreadable PID refused the run before its
  first trial, and ordinary desktop churn discarded hours of completed work. The exclusive-GPU rule
  is kept off WDDM, where a foreign context is visible and attributable, and becomes counted
  evidence on WDDM, where the aggregate reserve and release checks already carry the verdict.
- Make `status` and `stop` reach a server left behind by a calibration that was killed. Trial
  servers register outside the state root, so an orphan held VRAM invisibly while `start` advised
  running `bora stop`, which could not see it. Both commands now sweep the trial roots of an
  unfinished run.
- Treat a recorded PID this account cannot open as absent rather than as an error. On Windows,
  where PIDs are recycled quickly, a stale record could otherwise wedge `calibrate`, `status`, and
  `stop` alike with no way to clear it.

### Removed

- Remove the executable-file identity of GPU compute processes, which only the withdrawn WDDM
  immutability rule consumed. No launcher hashes another process's binary.

## [0.2.1] - 2026-07-26

### Changed

- Distribute `bora-workbench` exclusively through immutable, checksum-manifested GitHub Release
  bundles until the maintainer makes a new explicit distribution decision.
- Document copy-ready Ubuntu and Windows installation from the `v0.2.1` wheel and `SHA256SUMS`.

### Removed

- Remove the manual registry dispatch, publication job, OIDC permission, protected-environment
  dependency, and separate distributions artifact from the release workflow.
- Remove the registry-version source from both installers; they now accept only a verified local
  wheel or a full Git commit.

## [0.2.0] - 2026-07-26

### Changed

- Rename the distribution, package, command, managed roots, and repository identity from
  `qwen-launcher` / `qwen_launcher` / `qwen-launcher` to
  `bora-workbench` / `bora_workbench` / `bora`. Historical `0.1.0`–`0.1.6` artifacts keep their
  original identity.
- Prepare `bora-workbench==0.2.0` as the first PyPI publication. Publishing required a confirmed
  manual workflow dispatch and a protected OIDC environment; no upload occurred. D-070 and `0.2.1`
  subsequently remove this publication path.
- Calibrate and store one requested `fast`, `balanced`, or `max-context` cell per selected mode.
  `--mode all` applies one preference to all modes, while separate runs can retain different
  preferences. The incompatible `calibration-record/v6` supersedes v5 without migration.

### Fixed

- Harden calibration boundaries, shared budgets, retry accounting, A-B-B-A execution, record
  semantics, reuse identity, process cleanup, state locking, and expected CLI error rendering.
- Refuse unsafe engine roots, cache roots, manifests, redirects, archives, staging cleanup, probes,
  and unsupported OS versions before managed installation can trust or write them.
- Validate `engine.lock` against a closed packaged schema and verify wheels offline with the exact
  frozen runtime dependency set.

## [0.1.6] - 2026-07-25

Calibration becomes a single protocol. `0.1.5` recorded that the three-envelope search did not work
(D-066); this change finds and fixes the reasons, then removes the redundant protocols it was
competing with. `qwen-launcher calibrate` is now one command with no `--protocol` option (D-067).

### Fixed

- **A dying server leaked its transport error out of the readiness wait.** `wait_for_health` caught
  only `ConnectError` and `TimeoutException`, so the `ReadError` a server produces while it is dying
  escaped and bypassed `start_service`'s cleanup entirely: the child was never terminated and its
  service record stayed in the state file. The next start then refused to run with "a managed
  service is already running". Every transport failure is now read as "not ready yet", and the
  readiness loop keeps deciding on process death or the deadline. This also affected normal `run`.
- **A failed start now always cleans up.** `start_service` performed its cleanup only for a listed
  set of exception classes; any other failure left both a live child and a registered service.
- **Exhausted VRAM is classified instead of aborting the run.** The engine reports it only by dying
  during model load — the driver rejects the allocation, so free VRAM never crosses the monitored
  reserve and no monitor class can see it. `start_service` now raises `ServerStartupError` carrying
  the process log, and the trial classifies it as `MEMORY_INFEASIBLE` when the log names an
  out-of-memory failure and as retryable otherwise. Previously the bisection died on its first
  infeasible probe with `unsupported trial error: ProcessError`, which is why no run completed.
- **The final gate sized its smoke prompt in words instead of tokens.** Each generated word costs
  about three tokens, so the "80% of the context" prompt was roughly 2.3x the window and the server
  rejected it (`request (152614 tokens) exceeds the available context size (65536 tokens)`). The
  prompt is now sized from a measured tokens-per-word ratio, so the gate exercises what it claims.
- **A group whose memory boundary moved discarded every mode that had already finished.** Records
  were written only after all groups completed, so a failure in the last group threw away hours of
  valid, gated measurements from the earlier ones. Groups share hardware, not a decision: each one
  now persists its own records, the summary names the groups that produced nothing, and the exit
  code still reports the run as incomplete.
- **Confirmation failed the whole mode when a finalist stopped fitting the reserves.** A point the
  search had accepted can violate the VRAM reserve when ABBA re-measures it. Such a point cannot
  become a launch envelope, so the comparison is now abandoned and the surviving finalist is
  confirmed with no recorded rounds, instead of ending the mode. The same point reached at the
  final gate counts as a gate it cannot pass, which triggers the existing fallback to its rival.
- **Two phases reported a position above their own total.** The search cap was the probe budget,
  which bounds probes only, so a real run displayed `41/≤28` once the quick-bench measurements of
  each feasible step were counted too. The pairing cap described the rounds of a single preference,
  while confirmation pairs each preference separately, so a real run displayed `7/≤6`. Both caps now
  cover every trial their phase can start, and a test asserts that for all three phases.
- An unclassifiable trial failure reported only the exception class name and discarded its message,
  and a search failure reached the CLI unmapped and printed a traceback instead of exiting 1.

### Removed

- **The `--protocol` option and the two redundant protocols.** The gate-only laboratory and the
  paired-search protocol are gone, together with `--candidate`, `--settings`, the draft bundles they
  produced, and `validate --path`. `calibrate` measures three envelopes and nothing else.
- **The older record formats.** Only the current record format is written and read; a record written
  by an older launcher is diagnosed as superseded, with the same actionable message as before, and
  the superseded schemas are no longer packaged.
- **The repository-only cross-context spike package** and the public ordering seeds, which the
  current search never consulted. The packaged reference report and its digests are unchanged; only
  the runtime catalog stops exposing a field nothing read.

### Added

- Calibration supports the CPU backend end to end: it confirms the baseline context without
  inventing an offload axis, and records a null `n_cpu_moe`.
- Trials use the immutable run-scoped GPU context population that D-046 requires, instead of the
  per-trial legacy contract.
- The run reports live progress and prints the three measured envelopes, their gate outcomes, and
  the measured memory margins when it ends. Previously it printed nothing for 40-60 processes.

### Changed

- The automatic context scale is the full `131072 → 98304 → 65536 → 49152 → 32768 → 16384 → 8192`
  ladder, so hardware that cannot afford 32768 still produces a usable envelope. The previous
  three-step scale left `98304`/`49152` reachable only as explicit targets and had no floor below
  `32768`. The shared probe budget grows to 28 (text) and 20 (vision): an infeasible step still
  costs a single prudent probe.
- The VRAM-side bisection is written directly instead of reusing the old screening routine with
  placeholder arguments. That routine's peak model, interpolation, and monotonicity check were
  inert under those arguments, so the behavior is unchanged and the reasoning is now visible.
- Documentation describes one calibration protocol and stops naming protocol versions. `CALIBRATION.md`
  is removed; `docs/calibration.md` is the guide.

## [0.1.5] - 2026-07-25

Translates the whole repository into English and republishes the calibration evidence with a
regenerated digest chain. No runtime behavior changes: `calibration/v5` remains the default,
`calibration/v6-lite` remains opt-in, and the engine, model, and command contracts are untouched.

### Changed

- The whole repository is now written in English: user and contributor documentation, the normative
  plan, this changelog, the measured-evidence prose, the pull request template, and the
  cross-context spike protocol. Decision ids, constants, versions, protocol names, measured values,
  and gate wording are unchanged. The Python sources, CLI output, and docstrings were already
  English.
- The byte-pinned benchmark payloads (`benchmark-v1`, `benchmark-quick`, `calibration-v1`) and the
  mirroring prompt constant in `scripts/spike_ctx/quick.py` deliberately keep their original text:
  they are measurement inputs, and changing them would change what is measured.
- Translating the checksum-bound calibration evidence changed its bytes, so the whole reference
  chain was regenerated: `gate.md`/`protocol.md` digests, the report's `source_references`, the
  report digest inside the policy, and `SHA256SUMS`.

### Known limitations

- **`calibrate --protocol v6` does not work.** `calibration/v6-lite` ships as code, but its real
  trial adapter has never been validated on hardware; only the search, selection, confirmation,
  gate, and record logic is exercised, by offline tests with fakes. The `0.1.4` entry below, and the
  matching statements in D-063 and the documentation, claimed the adapter was validated on hardware:
  that claim was premature and is withdrawn here (D-066). `calibration/v5` stays the default and is
  the only protocol to use for a real calibration.
- The artifacts published for `0.1.0`–`0.1.4` embed the previous evidence digests and therefore no
  longer match this branch. No published artifact was rebuilt or replaced; the alignment travels
  with this version.

## [0.1.4] - 2026-07-24

Implements `calibration/v6-lite` as an **opt-in** experimental protocol. Under a recorded maintainer
decision (D-063) the engine was built before the GO verdict of the cross-context spike;
`calibration/v5` remains the default and promoting v6 to the default remains a human decision. The
logic is tested offline with fakes; the real trial adapter is validated on hardware.

> **Correction (0.1.5, D-066):** the last sentence was wrong. The real trial adapter was never
> validated on hardware and `--protocol v6` does not work. The text above is kept as the record of
> what this release claimed.

### Added

- `--protocol v6` with `--preference fast|balanced|max-context`: measures and records three envelopes
  per mode (`fast`, `balanced`, `max_context`) in the new `calibration-record/v5` record.
- The `_calibration_v6_*` engine: a shared `coding`+`studio` search bisecting the VRAM side only,
  a production quick-bench (`benchmark_quick.py`), Pareto-free selection, ABBA confirmation with a
  conditional third round, and a final per-envelope gate (smoke, multi-turn, vision).
- v6 trial reserves (0.5/2.0/0.125 GiB) written into the record; reuse and `doctor` evaluate the
  `active_preference` envelope and fall back to the baseline when headroom is insufficient.

### Changed

- Hard migration to `mode/v2`: the three modes now also emit `--min-p`, `--presence-penalty`,
  `--repeat-penalty`, and `--reasoning` (coding `on`; studio and vstudio `off`). Temperature, top-p,
  and top-k are unchanged and `command_contract_sha256` does not change. The loader accepts only
  `mode/v2`.

## [0.1.3] - 2026-07-24

A correctness release that prepares measurable input for the human gate of `calibration/v6-lite`;
protocol v5 remains the default and v6 is not implemented yet.

### Added

- A repository-only `scripts/spike_ctx/` package prepares the human cross-context spike with a
  non-cached quick-bench, bisection with typed outcomes, MTP/reasoning appendices, an offline
  dry-run, and evidence templates. It neither performs the real run nor decides GO/NO-GO.

### Fixed

- RAM/VRAM monitoring errors discovered during cleanup now take precedence over workload failures
  and correctly invalidate the whole run.
- VRAM reserve violations and failure to release memory after stop have distinct classes, so
  experimental protocols no longer confuse a monotonic limit with a retryable error.

### Changed

- The engine contract makes MTP explicit in the launch plan: `coding` and `studio` keep the same
  argv, while `vstudio` conservatively uses `speculative=disabled` together with `--mmproj`.
- The contract prepares — without enabling them in `mode/v1` modes — the verified extended sampling
  and reasoning flags needed by a possible `calibration/v6-lite`.
- The new contract digest makes earlier local records ineligible for reuse; the files remain
  readable and the remedy is to re-run `calibrate`.

## [0.1.2] - 2026-07-23

A stabilization release with `calibration/v5`, uniform terminal UX, Ubuntu CUDA build progress, and
complete removal of uv-managed installations.

### Fixed

- Dynamic CLI values are rendered as literal text: square brackets and sequences resembling Rich
  markup are no longer hidden, reinterpreted, or turned into unhandled errors.

### Changed

- `calibration/v5` adds 96K (`98304`) and 48K (`49152`) to the automatic scale, raises the cap to 14
  probes, and produces `calibration-record/v4`; historical v2/v3 records remain readable.
- `doctor` shows the calibrated parameters of the valid active record (`ctx` and, on CUDA,
  `--n-cpu-moe`) instead of just the "valid" label.
- The CLI uses a shared Rich presentation for states, tables, errors, and progress, keeping textual
  labels readable even without color.
- The Ubuntu CUDA build shows the real percentage read from the CMake output instead of an
  indeterminate indicator.
- `uninstall` uses a single confirmation to remove the managed roots and its own `uv tool`
  installation, without removing uv or the Hugging Face cache.
- The CI and release workflows use Node 24 releases of the actions, always pinned to a full SHA.

### Known limitations

- Calibration coverage remains `GATE-PARTIAL` while materially different hardware is missing.
- The maintainer authorized the GitHub publication of `0.1.2` without repeating a manual
  cross-platform Gate; PyPI remains unavailable and excluded.

## [0.1.1] - 2026-07-23

A stabilization release with `calibration/v4`, trial port isolation, and visible progress during
calibration and engine installation.

### Added

- `calibration-record/v3` records `calibration/v4` and its reserve explicitly, while still loading
  and semantically reconstructing historical v2 records.

### Fixed

- Engine installation shows the current phase and, on terminals, byte progress bars with speed and
  ETA during download and extraction; probes stay bounded but raise the allowance for the slow first
  start of the Windows CUDA asset from 10 to 60 seconds.
- Temporary calibration servers use a system-assigned loopback port when `llama_port` is busy;
  normal startups still require the configured port.
- Record reuse tolerates at most 1 MiB of variation in the reported total RAM, leaving component
  identity and RAM/VRAM headroom checks unchanged.

### Changed

- `calibration/v4` replaces the v3 execution while keeping its scale, search, and ABBA confirmation,
  but uses a 0.3 GiB VRAM reserve; on reuse each record keeps its own original reserve.
- v4 calibration shows the running trial, live progress, and per-phase ETA on terminals, keeps
  linear output when redirected, and summarizes the selection rationale and measured headroom.
- The documentation was rewritten as a linear path for new users and describes only current
  behavior.
- Measured evidence was separated from the manuals under `evidence/`; superseded audits and designs
  were removed.
- `IMPLEMENTATION_SPEC.md` keeps the summarized status and only the work still to be done, without
  the detailed plans of completed milestones.

### Known limitations

- The real Ubuntu and Windows Gates were attested by the maintainer, but coverage remains
  `GATE-PARTIAL` while materially different hardware is missing; the Ubuntu Gate does not make
  `n_cpu_moe=36` safe.
- `0.1.1` is published on GitHub Releases only; PyPI is out of scope for this publication.

## [0.1.0] - 2026-07-20

First public release of `qwen-launcher`.

### Added

- Explicit tool installation on Ubuntu and Windows with uv `0.11.28`, CPython `3.12.13`, and SHA-256
  verification of the wheel.
- The Qwen model and vision projector pinned by revision, filename, size, and digest, read without
  modifying the Hugging Face cache.
- A `llama.cpp b10011` contract with verified flags, API, health check, and CPU/CUDA assets.
- Safe engine installation with HTTPS download, confined extraction, immutable directories, and
  atomic manifest-based activation.
- The `coding`, `studio`, and `vstudio` modes, with UI and vision applied explicitly.
- Foreground lifecycle, loopback port, logs, health polling, atomic state, startup lock, and
  `status` and `stop` based on `pid + create_time`.
- Strict TOML configuration with environment > file > default precedence and defined Linux/Windows
  directories.
- CPU, RAM, and NVIDIA detection; deterministic GPU selection and a CUDA environment confined to the
  child process.
- Local v3 calibration with adaptive search, RAM/VRAM monitoring, ABBA confirmation, `benchmark/v1`,
  candidate/active/previous records, and reuse diagnostics.
- Public v2 policy and reports used only as evidence and ordering seeds, never as a remote envelope.
- JSON Schema and semantic validation of locks, modes, policies, reports, and bundles.
- `doctor`, `validate`, `engine install`, `engine status`, `uninstall`, and installers without
  elevation.
- Cross-platform CI and release workflows with full-SHA-pinned actions and OIDC PyPI publication.

### Changed

- The available-RAM gate for the default model is set to 22 GiB, keeping 28 GiB total and a dynamic
  2 GiB calibration reserve.
- The expert context target `98304` is available through `--target-ctx`, separate from the automatic
  scale.
- The `q8_0` K/V cache is pinned on the CUDA branch with mmap; the CPU branch is unchanged.

### Known limitations

- The calibration evidence is `GATE-PARTIAL`: a repetition on materially different hardware is
  missing.
- CUDA is blocked on multi-GPU hosts.
- The weights are neither distributed nor downloaded by the launcher.
- PyPI awaits Trusted Publisher configuration; the GitHub artifacts are public.
- The 0.1 series guarantees no stability of the CLI, configuration, records, procedures,
  performance, or future compatibility.
