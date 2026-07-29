# bora TUI — revised decision and execution plan for a proposed 0.4.0

> **Status: authorized execution detail.** D-083–D-085 in `IMPLEMENTATION_SPEC.md` approve the
> reduced boundary and local step-scoped implementation. That specification remains normative; this
> file defines the sequence and cannot authorize a push, tag, release, remote operation, candidate
> activation, Open WebUI work, or Gate claim.
>
> This revision was checked against `bora-workbench 0.3.2`. `TUI.md` is the aligned design record;
> match implementation references by content rather than by historical line number.

---

## 0. Verdict and proposed scope

The useful product is smaller than the previous plan:

> **`bora tui` is a read-mostly dashboard, command composer, and teaching surface for the existing
> CLI. It exits its UI runtime before a real command runs. It is not a second launcher runtime.**

A proposed `0.4.0` contains only what that product needs:

1. correctness fixes to the existing CLI surface that a composer must be able to trust;
2. a shared, structured, read-only view of local state;
3. one deliberate interaction-stack decision;
4. `bora tui`, its navigation, command composition, post-UI handoff, and optional motion;
5. documentation, packaging, offline tests, and explicit manual terminal checks.

The following are **not prerequisites and are removed from this plan**:

- renaming `pull`, `rm`, `update`, `uninstall`, or the bare `pi` action;
- adding `model`, `self`, or `pi connect` command groups;
- reorganizing all source and test modules into packages;
- relaxing the file-length or function-length limits;
- changing bare `bora` from `no_args_is_help`;
- writing `config.toml`;
- clipboard integration, `$EDITOR` launching, or a generic command runner.

Those ideas may be considered independently later. Coupling them to the TUI would enlarge the
review surface, break command habits, and create import and packaging risk without making the TUI
more truthful.

The version remains `0.3.2` until the complete release scope passes Part F. This file proposes
`0.4.0`; it does not authorize a version bump, commit, push, tag, or release.

---

## 1. Findings this revision corrects

The execution steps below are built around facts verified in the current source.

### 1.1 Command facts

- The installed console script already prints `Usage: bora ...`. The `name="bora-workbench"`
  discrepancy is visible mainly through direct `CliRunner` use, so it is not a release-driving user
  defect.
- `--no-activate`, `--activate`, and `--target-ctx` are documented but absent from generated
  `calibrate --help`; the current hand parser exists because the three-parameter quality limit is
  absolute.
- `bora pi --install remove` accepts and ignores `--install`.
- `bora pi --print --install` accepts two contradictory requests and lets `--print` silently win.
- `run_validate` and part of `run_doctor` can let an operational exception escape as a traceback.
- The engine-status difference list can be split between stdout and stderr.

These are corrected without renaming commands.

### 1.2 Read-model facts

- `doctor` computes while it renders; there is no structured snapshot for a second front end.
- `status_services()` is not read-only: it locks, quarantines corrupt state, and removes stale
  entries. Opening a side-effect-free dashboard cannot call it.
- `detect_hardware()` and engine verification execute bounded subprocess probes. Therefore
  "opening starts no process" is not a truthful contract. The correct rule is that opening starts
  no managed service or persistent process and performs no mutation.
- Engine version and help probes each have a 60-second timeout. GPU queries have their own 5-second
  timeout and may occur more than once. A 5-second total worst-case snapshot budget is false.
- `locate_copies()` reports files, not complete verified model readiness.
- `Config` retains resolved values but not whether each came from the environment, TOML, or a
  default.
- The pi context-window source is assembled in the CLI presentation module instead of a shared
  structured service.
- A passive "published version" field would require network access. It is therefore not part of
  the opening snapshot; `bora update --check` remains the explicit network action.

### 1.3 Interaction facts

- Rich supplies rendering, not a cross-platform input loop. A Rich-only phase with `q`, `r`, resize,
  animation, and raw input has already made the hard dependency decision by reimplementing a TUI
  framework.
- A dependency decision after two interactive Rich phases is too late. It happens before the first
  interactive screen.
- A parent TUI waiting in `subprocess.run()` remains inside the uv tool environment. That is unsafe
  for deferred `update` and `uninstall` on Windows and makes the claim that the TUI is already gone
  false.
- The current uv handoff is correct when the process that schedules it is the process that exits.
  The revised design therefore ends the UI runtime and dispatches the selected CLI callback in the
  **same bora process**, instead of creating another Python parent/child layer.
- Root-only Click parsing does not prove that nested command options are valid. Composer tests must
  recursively parse through every selected command and group to the leaf without executing it.

### 1.4 Plan and packaging facts

- The former target listed seven help panels while repeatedly calling them six.
- Five command paths, not four, were proposed for renaming.
- The proposed package tree had nine top-level directories before `tui/` and ten after it, not eight.
- Moving `_model_verification.py` below `models/` would cause package initialization to cross the
  existing `engine`/`models` dependency and was not a mechanical move.
- Several post-move test paths in the old plan referred to locations that the move itself removed.
- The former version-bump list omitted `uv.lock`.
- The current sdist includes `IMPLEMENTATION_SPEC.md` but not `TUI.md` or `TUI_PLAN.md`. If the
  normative plan points to these design records, the sdist must carry them.
- `TUI.md` still contains pre-D-078/D-079 statements that bora never downloads weights and that
  uninstall never offers Hugging Face cache removal. A partial errata table is insufficient.

---

## 2. Non-negotiable contracts

Every implementation review checks these rules.

1. `IMPLEMENTATION_SPEC.md` remains the only normative source.
2. Bare `bora` continues to show help; the front end is explicit `bora tui`.
3. Existing command names and meanings stay unchanged in this milestone.
4. The TUI owns no launch, calibration, removal, or update rule.
5. Every action displays the exact `bora ...` command before dispatch.
6. The UI runtime is fully stopped and the terminal restored before dispatch.
7. A successful returning action may reopen the TUI; a non-zero or interrupted action exits with
   that exact `0 / 1 / 2 / 130` result.
8. Opening and refresh perform no network access, hashing of model payloads, directory creation,
   receipt write, state cleanup, configuration write, or managed-service start.
9. Opening may run the same bounded, read-only hardware and engine probes that `doctor` runs. They
   execute in one presentation worker so the first frame and key handling remain responsive.
10. No two snapshot collections run concurrently.
11. Settings remain read-only. Configuration provenance is shown from shared configuration data,
    not reconstructed in the screen.
12. Model readiness never calls a file "verified" merely because its name exists.
13. Service inspection never calls stale or corrupt state "empty" and never repairs it while the
    TUI is open.
14. No candidate is activated without the user's explicit selection followed by the real CLI
    confirmation path.
15. No TUI feature is the only way to perform an operation.
16. No OS branching is scattered across screens. Any terminal-specific branch lives in the one
    module named by specification section 4.1.
17. The TUI is imported only by the `tui` command, never by package import or `bora --version`.
18. Tests remain offline and use no real network, GPU, model, server, npm, uv replacement, or
    administrative operation.

### 2.1 Precise meaning of read-only opening

The front end may read files, inspect process identities, and run bounded diagnostic subprocesses.
It must not:

- create or acquire a lifecycle lock;
- quarantine, prune, or rewrite service state;
- create a hash receipt or hash 22 GiB of weights;
- query GitHub or Hugging Face;
- launch `llama-server`;
- change pi's files, the user's config, or a managed root.

Tests assert the prohibited effects. They do not make the untrue assertion that no subprocess ever
exists.

---

## 3. Recorded decisions

On 29 July 2026 the maintainer approved implementation of this TUI plan and deferred Open WebUI.
D-083–D-085 record the answers:

- the reduced `0.4.0` scope is approved;
- current command names and the flat package tree stay unchanged;
- handoff is same-process dispatch after complete UI teardown;
- Textual may be reviewed and added before E1, with only its UI event loop and one presentation
  worker allowed;
- bare `bora` remains help and settings remain read-only;
- motion is optional and ships only if its measured budget passes;
- bounded read-only hardware and engine probes are allowed during snapshot collection;
- Open WebUI remains absent and its available future spike machine is not used in this milestone.

---

## 4. Step format and working rule

Every step below declares:

- **Goal** — one observable outcome;
- **Files** — the allowed files for that step;
- **Change** — the implementation boundary;
- **Decision** — the normative decision it applies, or `—` when restoring an existing rule;
- **Verify** — checks specific to the step, followed by Appendix B;
- **Done when** — the condition that ends the step.

One step is one commit. If implementation reveals a new design decision, stop and update the
normative specification before continuing. Do not silently amend this plan through code.

---

# Part A — Establish authority and align the design record

## A1 — Record the approved boundary

- **Goal.** Make the TUI an authorized backlog item with an exact, reduced perimeter.
- **Files.** `IMPLEMENTATION_SPEC.md`, `TUI.md`, `TUI_PLAN.md`.
- **Change.**
  1. Add the maintainer's answers from section 3 to the next free decision entries.
  2. Add `Backlog D — Interactive front end` to specification section 8.
  3. State the proposed `0.4` boundary without marking it complete or authorizing release actions.
  4. Keep the engine, model, calibration protocol, `calibration-record/v6`,
     `command_contract_sha256`, reserves, roots, and candidate lifecycle unchanged.
  5. Change this file's status from decision input to the execution detail named by the
     specification.
  6. Rewrite the stale parts of `TUI.md` as a design record, not as another roadmap:
     - current D-078 model acquisition and D-079 two-question removal;
     - current D-081/D-082 pi behavior;
     - current command names;
     - no package-tree prerequisite;
     - same-process post-UI dispatch;
     - the dependency decision before interactivity;
     - the canonical record labels of C7;
     - clipboard and `$EDITOR` explicitly deferred;
     - all prose in English.
- **Decision.** D-083–D-085.
- **Verify.** Search both TUI documents for obsolete `0.2.1`, "never downloads weights",
  `bora self`, `bora model`, `pi connect`, and subprocess handoff claims; none remain except clearly
  labelled rejected alternatives.
- **Done when.** The specification names this file, and `TUI.md` describes the same product this
  plan will implement.

## A2 — Ship the design records in the sdist

- **Goal.** Keep every document referenced by the normative plan available in the source
  distribution.
- **Files.** `pyproject.toml`, `scripts/verify_wheel.py`.
- **Change.** Add `TUI.md` and `TUI_PLAN.md` to
  `tool.uv.build-backend.source-include` and the sdist verifier; preserve the already included
  `IMPLEMENTATION_SPEC.md` and deferred `WEBUI_PLAN.md`. Change no wheel resource and no packaged
  declarative content.
- **Decision.** D-083.
- **Verify.** Build an sdist in a temporary output directory and assert that it contains
  `IMPLEMENTATION_SPEC.md`, `TUI.md`, `TUI_PLAN.md`, and `WEBUI_PLAN.md`.
- **Done when.** A consumer of the sdist can follow every plan reference without the Git checkout.

---

# Part B — Make the existing CLI composable

## B1 — Permit one published callback to exceed the parameter default

- **Goal.** Let a Typer callback declare its real public option surface without weakening unrelated
  readability limits.
- **Files.** `AGENTS.md`, `docs/development.md`, `tests/test_code_quality.py`.
- **Change.**
  - Keep 600 lines per file, 40 lines per function, nesting depth, and docstrings absolute.
  - Change only the production-parameter rule to allow a narrowly registered exception map keyed by
    `path::qualified_name`, with a mandatory reason.
  - Make the test fail when an unregistered function exceeds three parameters.
  - Make it also fail when a registered function no longer exceeds the limit, so stale exceptions
    cannot accumulate.
  - Add no exception in this step.
- **Decision.** D-083.
- **Verify.** A temporary four-parameter production function fails; registering it passes; removing
  the function while retaining the registration fails.
- **Done when.** The exception map is empty and all existing source remains unchanged.

## B2 — Declare the complete calibration surface

- **Goal.** Make every supported calibration option visible to help, completion, and the TUI
  composer.
- **Files.** `src/bora_workbench/cli.py`, `src/bora_workbench/_cli_calibration.py`,
  `tests/test_cli_calibration.py`, `tests/test_code_quality.py`, `docs/commands.md`.
- **Change.**
  - Declare `--no-activate`, `--activate`, and `--target-ctx` as ordinary Typer options beside
    `--mode` and `--preference`.
  - Remove `allow_extra_args`, `ignore_unknown_options`, `_CALIBRATION_EPILOG`, `_target_ctx()`, and
    `parse_calibration_input()`.
  - Construct `CalibrationCliInput` with keywords.
  - Register only `cli.py::calibrate` in the parameter exception map, with the reason that its
    parameters are the published interface.
  - Keep `_validate()` as the owner of mutual exclusion and target-domain rules before any process
    starts.
  - Accept Click's standard last-occurrence behavior for repeated singleton options as an explicit
    CLI behavior change. The real preflight still prints the selected value and asks for
    confirmation. Do not claim byte-for-byte parser compatibility with the removed hand parser.
- **Decision.** D-083.
- **Verify.** Generated help lists all five options; `--target-ctx=65536` works;
  `--activate --target-ctx 65536`, `--activate --preference fast`, unknown options, malformed
  integers, and unmeasurable targets exit 2 before a process starts.
- **Done when.** No accepted calibration option is hidden from generated help.

## B3 — Reject contradictory pi options

- **Goal.** Ensure no accepted pi option is silently discarded.
- **Files.** `src/bora_workbench/cli.py`, `src/bora_workbench/_cli_pi.py`,
  `tests/test_pi_link.py`, `tests/test_cli.py`, `docs/commands.md`.
- **Change.**
  - Keep the current `bora pi`, `bora pi remove`, and `bora pi uninstall` names.
  - Reject `--print --install` as invalid input with exit 2: print-only promises no write, while
    install requests an npm mutation.
  - Reject `--print` or `--install` when a `pi` subcommand is selected instead of discarding it.
  - Perform these checks before inspecting pi, files, hardware, or services.
- **Decision.** —; this restores specification section 5.11's invalid-input rule.
- **Verify.** The three contradictory forms exit 2 with no mocked service call, file read, npm call,
  or prompt; each valid existing form behaves as before.
- **Done when.** Every accepted pi option affects the selected action.

## B4 — Guard validation failures

- **Goal.** Prevent expected validation I/O or resource failures from escaping as tracebacks.
- **Files.** `src/bora_workbench/_cli_diagnostics.py`, `tests/test_cli.py`.
- **Change.** Wrap `run_validate()` at its presentation boundary, map the actual operational
  exception types to an actionable stderr message and exit 1, and retain validation-content errors
  as the existing structured result.
- **Decision.** —; specification section 5.11 already requires this behavior.
- **Verify.** A fake resource access failure exits 1, writes only the actionable error to stderr,
  and emits no traceback.
- **Done when.** `validate` has no expected failure path outside CLI exit mapping.

## B5 — Keep one engine-status difference list on one stream

- **Goal.** Make redirection of `engine status` deterministic.
- **Files.** `src/bora_workbench/_cli_diagnostics.py`, `tests/test_cli_engine.py`,
  `docs/commands.md`.
- **Change.** Choose the stream once for the complete difference list: informational absence stays
  in the stdout report; differences that cause exit 1 all go to stderr. Do not reclassify unrelated
  warning call sites without a demonstrated problem.
- **Decision.** —; this clarifies the existing exit/report contract.
- **Verify.** Redirected missing-engine output remains complete; an incompatible engine leaves the
  table on stdout and every blocking difference on stderr.
- **Done when.** One status loop never alternates output streams.

---

# Part C — Build one shared, non-mutating read model

## C1 — Preserve configuration provenance

- **Goal.** Report each resolved setting and the layer that supplied it without changing
  `load_config()` callers.
- **Files.** `src/bora_workbench/config.py`, `tests/test_config.py`,
  `docs/configuration.md`.
- **Change.**
  - Add frozen, slotted models for a resolved configuration and per-field source.
  - Add one loader that returns the existing `Config`, the config-file path, and sources
    `environment`, `config.toml`, or `default` for every field.
  - Implement `load_config()` through that loader and return only `.config`, preserving its public
    result and precedence.
  - Validate the whole TOML before environment overrides exactly as today.
  - Perform no path creation or file write.
- **Decision.** D-083/D-084.
- **Verify.** Existing config tests remain unchanged and green; new table tests cover every source,
  including an empty optional path environment override.
- **Done when.** CLI and TUI can consume the same resolved values, and only the TUI asks for their
  provenance.

## C2 — Add read-only service inspection

- **Goal.** Inspect live, stale, and unreadable service records without cleaning or quarantining
  them.
- **Files.** `src/bora_workbench/_process_state.py`, `src/bora_workbench/process.py`,
  `tests/test_process_state.py`, `tests/test_process_lifecycle.py`.
- **Change.**
  - Keep `status_services()` and `stop_services()` behavior unchanged.
  - Add a separate inspection path that does not acquire the startup lock, create a root, quarantine
    corrupt JSON, prune stale entries, or write state.
  - Return structured live services, stale identities, and warnings/errors; corrupt state is
    `unreadable`, never silently `empty`.
  - Continue verifying `pid + create_time`; an unopenable PID follows the existing D-071 identity
    rule.
- **Decision.** D-084.
- **Verify.** Snapshot the temporary filesystem before and after live, stale, corrupt, absent, and
  trial-root inspections; bytes and paths remain identical.
- **Done when.** The TUI can report service state without performing `status` cleanup.

## C3 — Add receipt-aware model inspection

- **Goal.** Describe model readiness without hashing payloads, writing receipts, or confusing
  presence with verification.
- **Files.** `src/bora_workbench/models.py`, `src/bora_workbench/_model_verification.py`,
  `tests/test_model_store.py`.
- **Change.**
  - Add frozen, slotted inspection models for each locked artifact and location.
  - Distinguish `absent`, `wrong-size`, `receipt-verified`, and `present-unverified`.
  - Reuse the D-076 receipt identity read-only; do not call `remember()`, compute SHA-256, download,
    or create the store.
  - Inspect both the managed store and pinned cache fallback without writing into either.
  - Represent an explicit custom `model_path` as user-managed and never recommend `bora pull` for
    that path.
- **Decision.** D-084.
- **Verify.** Tests cover every state, both locations, a malformed receipt, and a custom model; mock
  hashing and writes to fail if called.
- **Done when.** The dashboard can say exactly what it knows and direct an unverified default
  artifact to the real `bora pull` verification path.

## C4 — Move pi context selection into shared data

- **Goal.** Let the CLI and TUI report the same D-082 context-window source without one importing
  the other's presentation module.
- **Files.** `src/bora_workbench/pi_link.py`, `src/bora_workbench/_cli_pi.py`,
  `tests/test_pi_link.py`.
- **Change.**
  - Move `ContextWindow` and the source-selection rule into `pi_link.py` behind a narrow query model.
  - Preserve the order: live service on the configured port, compatible active `coding` record,
    verified baseline with diagnostics.
  - Let the caller supply already collected hardware, service, and record data so the TUI does not
    rerun probes.
  - Make `_cli_pi.py` render the shared result exactly as before.
- **Decision.** —; D-082 already owns the selection rule.
- **Verify.** Existing D-082 tests remain green; add a test proving CLI and snapshot receive the
  same `ContextWindow` object for all three sources.
- **Done when.** No TUI code imports `_cli_pi.py` and no pi rule is duplicated.

## C5 — Render doctor from a structured snapshot

- **Goal.** Separate the state `doctor` collects from how Rich prints it.
- **Files.** new `src/bora_workbench/snapshot.py`,
  `src/bora_workbench/_cli_diagnostics.py`, new `tests/test_snapshot.py`,
  `tests/test_cli_doctor.py`.
- **Change.**
  - Add a frozen, slotted `DoctorSnapshot` containing version, resolved config, hardware, content
    validation, compatible-profile count, record evaluations, engine status, and the four paths.
  - Preserve the current collection order, including resolving public roots last.
  - Move the four formerly unguarded operations into collection and map their real domain failures
    at `run_doctor()` to exit 1 or 2 as required.
  - Make `run_doctor()` collect, render, and map the result; it computes nothing while printing.
  - Keep successful redirected output byte-identical in this step.
- **Decision.** D-084.
- **Verify.** Capture redirected `doctor` output before and after on the same fakes and compare bytes;
  separately fake each formerly unguarded operation and require an actionable exit without a
  traceback.
- **Done when.** `DoctorSnapshot` is fully testable without a console and `doctor` renders only its
  data.

## C6 — Compose the workbench snapshot

- **Goal.** Build the complete data needed by read-only screens without adding side effects to
  `doctor`.
- **Files.** `src/bora_workbench/snapshot.py`, `tests/test_snapshot.py`.
- **Change.**
  - Add a frozen, slotted `WorkbenchSnapshot` that contains `DoctorSnapshot`, configuration
    provenance, read-only service inspection across current service roots, model inspection, and
    the shared pi context source.
  - Keep the collector synchronous and independent of any UI framework; E1 decides where it runs.
  - Collect no published release version and perform no network request.
  - Expose a structured collection failure with category and actionable detail so the first frame
    can remain usable even when config, hardware, resources, or paths are broken.
- **Decision.** D-084.
- **Verify.** Patch network, hashing, writes, directory creation, lifecycle locks, state cleanup, and
  service starts to fail if called; every valid snapshot shape still collects.
- **Done when.** Every read-only screen can be rendered from one object and no screen performs core
  discovery itself.

## C7 — Use one canonical record vocabulary

- **Goal.** Stop the CLI and TUI from assigning different words to the same record state.
- **Files.** `src/bora_workbench/_cli_diagnostics.py`, `tests/test_cli_doctor.py`,
  `docs/commands.md`, `TUI.md`.
- **Change.** Map the actual `RecordEvaluation` states to these display labels:

  | Core status | Display label |
  |---|---|
  | `valid` | `active` |
  | `missing` | `absent` |
  | `candidate` | `candidate` |
  | `superseded` | `superseded` |
  | `invalid` | `invalid` |
  | `incompatible` | `incompatible` |
  | `insufficient-headroom` | `insufficient headroom` |

  A valid or invalid pending candidate remains a secondary fact beside the active-record label.
  The word `stale` remains available for process state; it is not a calibration-record status.
- **Decision.** D-083/D-084.
- **Verify.** Table-driven tests cover every primary status and every candidate-status combination.
- **Done when.** `doctor`, docs, and the future screens use the same seven labels.

---

# Part D — Choose the interaction stack before writing an interaction loop

## D1 — Review and lock the TUI framework

- **Goal.** Make one evidence-based build-versus-dependency decision before E1.
- **Files.** `IMPLEMENTATION_SPEC.md`, `AGENTS.md`, `pyproject.toml`, `uv.lock`,
  `docs/development.md`.
- **Change.**
  1. Review the current official Textual release for Python 3.12 and the required Windows/Ubuntu
     terminal support.
  2. Record its exact version through `uv.lock`; never commit `latest`.
  3. Record maintenance activity, licence, known security concerns, and the complete added
     transitive dependency set in the commit body and development documentation.
  4. Add Textual to the approved runtime dependencies only if the review passes.
  5. State the narrow concurrency boundary: Textual owns its UI event loop and one presentation
     worker may run the synchronous snapshot collector; core modules gain no async API, background
     scheduler, or general executor.
  6. If the review fails, record `NO-GO` and stop Part E. Do not replace it with hand-written
     `termios`/`msvcrt` input.
- **Decision.** D-085 plus the new exact dependency decision recorded by this step.
- **Verify.** `uv lock --check`, frozen sync, dependency-tree review, licence review, and the full
  offline suite on both release CI platforms.
- **Done when.** The interaction stack is approved and frozen, or the interactive front end is
  explicitly stopped.

---

# Part E — Implement the front end in vertical slices

## E1 — Add a read-only TUI shell

- **Goal.** Paint a usable first frame, collect one snapshot responsively, refresh, and quit.
- **Files.** `src/bora_workbench/cli.py`, new `src/bora_workbench/tui/__init__.py`, new
  `src/bora_workbench/tui/app.py`, new `src/bora_workbench/tui/terminal.py`, new
  `src/bora_workbench/tui/palette.py`, new `tests/test_cli_tui.py`, `tests/test_import.py`.
- **Change.**
  - Add `bora tui [--plain]`; bare `bora` remains unchanged.
  - Refuse a non-TTY with one actionable stderr line and exit 2 before importing Textual.
  - Import `tui/` only inside the command callback.
  - Paint static chrome before starting collection.
  - Run only `collect_workbench_snapshot()` in one framework worker; coalesce repeated `r` presses so
    two collections never overlap.
  - Keep `q`, `Ctrl-Q`, and `Esc` available while collection runs.
  - Render collection failures in the detail pane without a traceback.
  - `--plain`, `TERM=dumb`, and unsupported encoding select a plain, motion-free rendering. Do not
    promise automatic raster-font detection; `--plain` is the deterministic escape hatch.
- **Decision.** D-083–D-085 and D1's exact dependency decision.
- **Verify.** Headless UI tests prove first render precedes collector invocation, keys work while a
  fake collector blocks, refresh is serialized, non-TTY imports no Textual module, and package
  import remains side-effect-free.
- **Done when.** `bora tui` is a useful read-only overview even if every later phase is declined.

## E2 — Add deterministic advice and overview detail

- **Goal.** Show one honest next step derived only from the snapshot.
- **Files.** new `src/bora_workbench/tui/advice.py`, new
  `src/bora_workbench/tui/screens/__init__.py`, new
  `src/bora_workbench/tui/screens/overview.py`, `src/bora_workbench/tui/app.py`, new
  `tests/test_tui_advice.py`, `tests/test_cli_tui.py`.
- **Change.** Add a pure `next_step(snapshot) -> Suggestion` with this priority:
  1. collection/config failure: show the remedy, and a command only when one is truthful;
  2. packaged-content errors: `bora validate`;
  3. absent or incompatible engine: `bora engine install`;
  4. missing, wrong-size, or unverified default artifacts: `bora pull`;
  5. a live service: show mode, port, UI availability, and `bora stop`;
  6. a valid pending candidate: explicit `bora calibrate --mode <id> --activate`;
  7. modes without active records: a calm calibration suggestion that states the baseline works;
  8. complete setup: `bora coding`.

  A custom external model never receives a `bora pull` suggestion. The suggestion is visible but
  cannot execute yet.
- **Decision.** D-083/D-084.
- **Verify.** A truth table covers every priority and tie in packaged mode order.
- **Done when.** The overview never infers a fact absent from the snapshot.

## E3 — Add all read-only screens and navigation

- **Goal.** Make the complete local picture navigable before any command can run.
- **Files.** new `src/bora_workbench/tui/screens/modes.py`, new
  `src/bora_workbench/tui/screens/calibration.py`, new
  `src/bora_workbench/tui/screens/setup.py`, new
  `src/bora_workbench/tui/screens/pi.py`, new
  `src/bora_workbench/tui/screens/settings.py`, new
  `src/bora_workbench/tui/screens/installation.py`, `src/bora_workbench/tui/app.py`,
  `tests/test_cli_tui.py`.
- **Change.** Use seven user-facing rail labels, independent of CLI help grouping:
  `Overview`, `Modes`, `Calibration`, `Setup`, `Pi`, `Settings`, `This installation`.
  Screens show:
  - modes and the active cell or baseline they would use;
  - canonical record and candidate states;
  - engine and receipt-aware model status;
  - pi installation/context source;
  - resolved settings, provenance, config path, and environment names;
  - installed version, four roots, and precise removal boundary.

  Services and diagnostics remain in Overview. There is no settings writer, model picker, arbitrary
  flag editor, published-version lookup, clipboard protocol, or editor launcher.
- **Decision.** D-083/D-084.
- **Verify.** Headless navigation at 60x20, 80x24, and 120x40 reaches every screen, preserves focus
  on refresh, and exposes every fact as text rather than colour alone.
- **Done when.** The front end is complete as a read-only dashboard.

## E4 — Compose and dispatch safe returning actions

- **Goal.** Prove post-UI same-process handoff on non-destructive read commands.
- **Files.** new `src/bora_workbench/tui/actions.py`,
  `src/bora_workbench/tui/app.py`, `src/bora_workbench/cli.py`,
  `src/bora_workbench/tui/screens/overview.py`, new `tests/test_tui_actions.py`,
  `tests/test_cli_tui.py`.
- **Change.**
  - Add a frozen `CommandSpec` containing display tokens, CLI argument tokens, and disposition
    `returning` or `terminal`.
  - Add pure composers for `doctor`, `validate`, `status`, and `engine status`.
  - Every actionable screen shows the exact display command before Enter can select it.
  - The Textual app exits completely and restores the terminal, then the existing root Click/Typer
    command is invoked in the same process with the composed arguments.
  - Parse composed argv recursively through every group to the leaf in tests without invoking the
    callback.
  - Reopen the TUI only after a returning command exits 0; re-collect and show a concise before/after
    difference. Exit immediately with any non-zero or 130 result.
- **Decision.** D-085.
- **Verify.** Fakes prove the UI teardown precedes dispatch, no subprocess is created, every argv is
  accepted by the real recursive parser, non-zero codes propagate, and terminal state restoration
  runs under every exception.
- **Done when.** A real `doctor` handoff returns to an intact TUI and a failing fake exits with its
  exact code.

## E5 — Add setup and pi actions

- **Goal.** Hand long and mutating setup operations to their existing CLI owners.
- **Files.** `src/bora_workbench/tui/actions.py`,
  `src/bora_workbench/tui/screens/overview.py`,
  `src/bora_workbench/tui/screens/setup.py`,
  `src/bora_workbench/tui/screens/pi.py`, `tests/test_tui_actions.py`,
  `tests/test_cli_tui.py`.
- **Change.** Compose the current command names only:
  - `bora engine install [--force] [--no-model]`;
  - `bora pull [qwen]`;
  - `bora rm [qwen] [--keep-hf] [--dry-run]`;
  - `bora stop`;
  - `bora pi [--print] [--install]`;
  - `bora pi remove`;
  - `bora pi uninstall`.

  Invalid pi combinations are unreachable. The UI disappears while the command owns inherited
  terminal I/O and real prompts. Exit 0 returns and refreshes; all other exits propagate.
- **Decision.** D-083/D-085.
- **Verify.** Table-driven composer tests plus recursive real-parser tests cover every reachable
  option state. Operational tests use fake callbacks only.
- **Done when.** No setup rule, prompt, npm action, deletion, or verification is duplicated in
  `tui/`.

## E6 — Add modes and the calibration wizard

- **Goal.** Compose the foreground and hours-long operations without hosting them in the UI.
- **Files.** `src/bora_workbench/tui/actions.py`,
  `src/bora_workbench/tui/screens/modes.py`,
  `src/bora_workbench/tui/screens/calibration.py`, `tests/test_tui_actions.py`,
  `tests/test_cli_tui.py`.
- **Change.**
  - Modes compose `bora coding|studio|vstudio [--force]`; the screen states exactly what `--force`
    bypasses.
  - The wizard asks mode, preference, activation behavior, optional approved target, and review.
  - `--activate` removes preference and target choices by construction.
  - The review screen says that the real preflight and confirmation follow.
  - Modes and calibration are `terminal`: after UI teardown they do not reopen the TUI and their
    exact exit code becomes the `bora tui` exit code.
- **Decision.** D-083/D-085.
- **Verify.** Enumerate every reachable wizard state; every composed argv recursively parses, every
  forbidden combination is unreachable, and no fake command runs before final review.
- **Done when.** The TUI can teach every supported calibration form without owning calibration.

## E7 — Prove update and uninstall handoff

- **Goal.** Make the two self-replacing commands safe with no extra Python parent holding the tool
  environment open.
- **Files.** `src/bora_workbench/tui/actions.py`,
  `src/bora_workbench/tui/screens/installation.py`, `src/bora_workbench/cli.py`,
  `tests/test_tui_actions.py`, `tests/test_cli_tui.py`, `scripts/verify_uninstall.py`.
- **Change.**
  - `bora update --check` is returning; `bora update` is terminal.
  - `bora uninstall` is terminal and hidden behind typing `remove`; the real CLI still asks its own
    two independent questions.
  - Dispatch both in the same process after the UI runtime closes. The existing deferred uv helper
    therefore watches the one process that will actually exit.
  - Do not create a subprocess wrapper, suppress a confirmation, or infer uv ownership.
  - Extend isolated verification so the presence of the TUI command does not break complete
    uv-tool uninstall; no automated test performs a real update.
- **Decision.** D-085.
- **Verify.** Unit tests prove ordering and exact argv; isolated wheel uninstall passes; manual
  Windows checks confirm the environment is removed only after the command process exits.
- **Done when.** There is no live TUI parent during uv replacement/removal and no helper race is
  observed in the supported manual environments.

## E8 — Add optional bora motion

- **Goal.** Add identity without weakening input latency, accessibility, or static usefulness.
- **Files.** new `src/bora_workbench/tui/motion.py`,
  `src/bora_workbench/tui/app.py`, `src/bora_workbench/tui/palette.py`, new
  `tests/test_tui_motion.py`, `tests/test_cli_tui.py`, `docs/configuration.md`.
- **Change.**
  - Implement gust and sea as pure functions of time, dimensions, and seed.
  - Animate only the focused Overview, at no more than 12 fps, and settle after about three
    seconds instead of looping forever.
  - Stop on another screen, small terminal, lost focus where available, `--plain`, `NO_COLOR`,
    `TERM=dumb`, or `BORA_TUI_MOTION=off`.
  - Accept only the documented TUI-motion environment values; malformed values exit 2.
  - Keep static text and every action complete when motion is absent.
  - If measured idle CPU exceeds the accepted budget, do not ship motion in `0.4.0`; keep the
    functional TUI and record the limitation instead of weakening the budget.
- **Decision.** D-085.
- **Verify.** Frozen-time/seed tests, headless kill-switch tests, measured frame rate, and manual idle
  CPU measurements on the maintained Windows and Ubuntu machines.
- **Done when.** Motion is deterministic in tests, instantly interruptible, and optional in every
  environment.

## E9 — Document the shipped front end

- **Goal.** Describe the TUI as an optional path without making any operation TUI-only.
- **Files.** new `docs/tui.md`, `README.md`, `docs/README.md`, `docs/commands.md`,
  `docs/architecture.md`, `docs/development.md`, `docs/configuration.md`, `TUI.md`.
- **Change.**
  - Document invocation, screens, keymap, handoff, read-only opening, motion controls, and plain
    mode.
  - State that alternate-screen interfaces are not the accessible path for every user and that the
    complete CLI remains supported.
  - Document that read-only opening may run bounded probes but performs no mutation or network.
  - State that command selection closes the UI before the existing command owns the terminal.
  - Keep clipboard integration, editor launching, command aliases, arbitrary model selection, and
    config writes out of current docs.
- **Decision.** D-083–D-085.
- **Verify.** Every action table names a real current command; every command remains documented
  independently of the TUI.
- **Done when.** A reader can ignore `docs/tui.md` and still operate the complete product.

---

# Part F — Acceptance and proposed 0.4.0 release

## F1 — Automated definition of done

All of the following must pass from a clean checkout:

- [ ] every authorized step A1–E9 is one reviewed commit with its step-specific checks;
- [ ] `bora tui` imports no TUI framework before its command runs;
- [ ] non-TTY invocation exits 2 without side effects;
- [ ] first chrome renders before snapshot collection starts;
- [ ] key input remains responsive while a fake collector blocks;
- [ ] repeated refresh never overlaps collection;
- [ ] opening and refresh perform no network, hash, write, cleanup, directory creation, or service
      start;
- [ ] every composed argv reaches a real leaf parser without execution;
- [ ] every real preflight and confirmation remains owned by the existing CLI callback;
- [ ] returning success reopens and refreshes; non-zero and 130 propagate exactly;
- [ ] update/uninstall have no waiting TUI subprocess parent;
- [ ] rendering is usable at 60x20, 80x24, and 120x40 in plain and full modes;
- [ ] `bora --version` and package import do not import `bora_workbench.tui` or Textual;
- [ ] static mode consumes no periodic refresh; motion, if shipped, stays within its measured
      budget;
- [ ] the sdist carries `IMPLEMENTATION_SPEC.md`, `TUI.md`, `TUI_PLAN.md`, and deferred
      `WEBUI_PLAN.md`;
- [ ] existing engine, model, calibration, record, and command-contract tests remain unchanged in
      meaning.

There is no invented total snapshot timeout. The UI exposes collection in progress and remains
responsive while the existing bounded probes enforce their own limits.

## F2 — Required manual checks

Before a release, perform and report:

### Ubuntu

- one supported terminal at 60x20 and 120x40;
- plain mode and full mode;
- refresh during a deliberately slow fake or unavailable `nvidia-smi` probe;
- one returning command and one terminal foreground mode;
- `Ctrl-C` from the foreground mode leaves the terminal intact and exits 130.

### Windows 11

- Windows Terminal in PowerShell and cmd;
- legacy console only as far as the environment is actually available; use `--plain` rather than
  claiming undetectable raster-font support;
- one returning command and one terminal foreground mode;
- isolated `bora uninstall` through the TUI handoff;
- verify that no live TUI parent blocks uv deletion;
- resize, `Ctrl-C`, and terminal restoration.

If a check is unavailable, record it as a limitation. Do not call it passed and do not call this a
calibration Gate.

## F3 — Version finalization

Only after F1 and the available F2 checks:

1. search the checkout for every current `0.3.2` release-bearing value;
2. change only current-version fields to `0.4.0`, preserving historical prose;
3. update `pyproject.toml` **and `uv.lock` together**;
4. update version fallbacks, tests, install examples, current-status docs, changelog, and release
   documentation found by the search;
5. record exactly which manual checks ran and which did not;
6. keep GitHub Releases as the only distribution channel.

Do not rely on a fixed file count: the source hierarchy and search results are the authority.

## F4 — Release procedure

Run, in order:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
rm -rf dist
uv build
uv run --frozen python scripts/verify_wheel.py
uv run --frozen python scripts/verify_uninstall.py
git diff --check
```

Inspect the sdist contents for the specification and all three design/plan documents, and inspect the wheel for the TUI
Python modules and any non-Python UI assets. Any edit after the build invalidates `dist/` and requires
all checks and the build again.

A local version commit does not authorize a push, tag, GitHub Release, remote setting, candidate
activation, or registry publication. Each remote action still requires explicit authorization in
that session.

## F5 — Claims that remain forbidden

A `0.4.0` release is not:

- a passed calibration Gate;
- broader hardware evidence;
- a new engine, model, protocol, record format, or command contract;
- a generic model manager or settings editor;
- an accessibility replacement for the CLI;
- proof for a manual platform check that was not performed.

No local candidate is activated by implementation, testing, or release preparation.

---

# Appendix A — Action matrix

The exact existing CLI vocabulary is the source. UI labels do not rename it.

| Screen | Displayed command | Disposition |
|---|---|---|
| Overview | `bora doctor` | returning |
| Overview | `bora validate` | returning |
| Overview | `bora status` | returning |
| Overview | `bora stop` | returning |
| Modes | `bora coding [--force]` | terminal |
| Modes | `bora studio [--force]` | terminal |
| Modes | `bora vstudio [--force]` | terminal |
| Calibration | `bora calibrate ...` | terminal |
| Calibration | `bora calibrate --mode ID --activate` | terminal |
| Setup | `bora engine status` | returning |
| Setup | `bora engine install [--force] [--no-model]` | returning on 0 |
| Setup | `bora pull [qwen]` | returning on 0 |
| Setup | `bora rm [qwen] [--keep-hf] [--dry-run]` | returning on 0 |
| Pi | `bora pi [--print] [--install]` | returning on 0 |
| Pi | `bora pi remove` | returning on 0 |
| Pi | `bora pi uninstall` | returning on 0 |
| This installation | `bora update --check` | returning |
| This installation | `bora update` | terminal |
| This installation | `bora uninstall` | terminal |

"Returning on 0" means any non-zero or interrupted result exits the TUI command with that exact
code. The TUI never swallows a failed operation and later reports shell success.

---

# Appendix B — Verification after every implementation step

The repository checks are mandatory after every step once A1 authorizes implementation:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
git diff --check
```

When package metadata, dependencies, source inclusion, or TUI package files change, also run:

```bash
rm -rf dist
uv build
uv run --frozen python scripts/verify_wheel.py
uv run --frozen python scripts/verify_uninstall.py
```

Before each commit:

- inspect `git diff` and `git diff --check`;
- verify the staged set contains only the declared files;
- use a concrete Conventional Commit subject and a body naming constraints and checks;
- report unavailable platform checks instead of implying success.

---

# Appendix C — Explicitly deferred ideas

These are not hidden phases of `0.4.0`.

- command groups `model`, `self`, or `pi connect`;
- moved-name notices or aliases;
- full source/test package reorganization;
- splitting `engine.py` solely to create room for unrelated work;
- editable settings or generated TOML;
- `$EDITOR` process parsing;
- OSC 52 clipboard claims across SSH/tmux/screen;
- automatic legacy-console raster-font detection;
- passive release-network checks;
- background polling of GPU, model, service, or release state;
- embedded calibration, launch, update, uninstall, npm, or uv execution inside the UI event loop;
- model pickers, arbitrary flags, profiles, plugins, or additional integrations.

Each requires its own demonstrated need and normative decision.