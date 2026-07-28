# bora — command surface and interactive front end: execution plan

> **Status: execution plan.** Part A is ready to execute, and **step A1 is what authorizes it**:
> until A1 lands, this file has no normative anchor and no other step should be committed.
> Part B is accepted in principle and **unscheduled**; do not begin it without a maintainer
> decision recorded in the decision table of `IMPLEMENTATION_SPEC.md`.
>
> `IMPLEMENTATION_SPEC.md` stays the only normative plan: it holds the authority, this file holds
> the steps, and `TUI.md` holds the design rationale, the screen mockups, and the visual identity.
> Nothing here duplicates `TUI.md`; where the front end needs a picture, this file points at it.
>
> Written against `0.3.2` at commit `4088997`, and every `file:line` below was verified at that
> commit. **Match by content, not by number**: a reference whose quoted code still matches is
> still correct wherever it moved, and a reference that no longer matches means this plan is
> stale, not the code.

---

## 0. Why this file exists

The CLI grew by accretion. `0.2.x` added calibration and the run modes, `0.3.0` gave the launcher
ownership of the model (D-078…D-081), `0.3.2` finished the pi handoff (D-082). Every one of those
steps was coherent on its own and none of them revisited the whole. The surface today is correct
and completely documented — and it has five defects, a flag vocabulary that says the same thing
four different ways, and no structured way to read the machine's state.

`TUI.md` already found the one thing that matters: the honest cost of any interactive front end is
a single core change, a structured snapshot that `doctor` renders instead of computing while it
prints. But `TUI.md` is written against `0.2.1`, it is stale in three measurable ways, and its six
open questions leave it unexecutable. This file is the executable form of that judgment, extended
to the command surface the front end would sit on.

The order matters, and it is the opposite of the one `TUI.md` proposed. **Part A first**, because
every change it makes is worth making whether or not a front end is ever built. Part B second, and
only behind a gate.

## 1. The contract every step follows

Each step below declares six things, and a step missing any of them is not ready to execute:

| Field | Meaning |
|---|---|
| **Goal** | the one outcome; if it needs an "and", it is two steps |
| **Files** | every file the step may touch, and no others |
| **Change** | what to do, precisely enough not to require a design decision |
| **Decision** | the `D-0xx` entry it records, or `—` when it restores an existing contract |
| **Verify** | the check that would fail if the step were wrong |
| **Done when** | the observable condition that ends the step |

Beyond that, the rules already in force (`AGENTS.md:200-219`, `CONTRIBUTING.md:34`):

- one step per commit, Conventional Commits with a body that names the constraints and the checks;
- documentation travels with its own area in the same commit; core and packaged content never mix;
- **no step in Part A touches `src/bora_workbench/resources/`**;
- after every step, the frozen suite of `AGENTS.md:176-198` (Appendix C);
- a new durable decision updates `IMPLEMENTATION_SPEC.md` section 3 in the same step that
  authorizes it, and the changelog entry is written when the version that ships the step is
  prepared, following `docs/releasing.md`. Do not invent a version heading.

The decision numbers below (`D-083` … `D-086`) are **indicative**. Take the next free number in the
table at the moment the step actually lands, exactly as `TUI.md:784-785` argues: a plan that
reserves a block it does not own collides with whatever was decided meanwhile.

---

# Part A — The command surface

## A.0 What is there today

Entry point `bora = "bora_workbench.cli:app"` (`pyproject.toml:22-23`), Typer. Every command is
declared in `src/bora_workbench/cli.py` — 240 lines, zero logic — and each body delegates to a
`run_*` function in one of eight `_cli_*` modules. **Seventeen invocable paths**, plus `--version`
on the root:

| Path | Options | Mutates | Prompts | Long |
|---|---|---|---|---|
| `bora validate` | — | no | no | no |
| `bora doctor` | — | no | no | no |
| `bora engine status` | — | no | no | no |
| `bora engine install` | `--force`, `--no-model` | yes | no | **yes** — download, and a CMake build on Ubuntu CUDA |
| `bora pull [MODEL]` | — | yes | no | **yes** — about 22 GiB |
| `bora rm [MODEL]` | `--keep-hf`, `--dry-run` | yes | 1–2 | no |
| `bora pi` | `--print`, `--install` | pi's `models.json` | 1–2 | no |
| `bora pi remove` | — | pi's `models.json` | 1 | no |
| `bora pi uninstall` | — | npm and `models.json` | 2 | no |
| `bora coding` / `studio` / `vstudio` | `--force` | state and logs | no | **yes** — foreground until `Ctrl-C` |
| `bora calibrate` | `--mode` (required), `--preference`, **and three undeclared** | yes | 1 | **yes — hours** |
| `bora status` | — | prunes stale state | no | no |
| `bora stop` | — | yes | no | no |
| `bora update` | `--check` | the Python tool | no | moderate |
| `bora uninstall` | — | yes, including itself | 2 | no |

Module sizes, for the record: `_cli_calibration.py` 504, `_cli_diagnostics.py` 470,
`_cli_services.py` 369, `_cli_pi.py` 286, `cli.py` 240, `_cli_theme.py` 220, `_cli_models.py` 184,
`_cli_update.py` 112. Exit codes are `0 / 1 / 2 / 130` (spec 5.11, `docs/commands.md:446-457`).

## A.1 What must not change

**The command tree.** Grouping the flat commands (`bora model pull`, `bora service status`) would
add typing without removing a single concept, would break a public contract documented in
`docs/commands.md`, `README.md`, and `evidence/`, and — the part that decides it — **would give
the front end nothing**. A front end composes argv itself; the depth of the tree is invisible to
it. Seventeen commands is a small surface, and it is already the right shape.

**Backward compatibility.** No step in Part A removes a command, renames one, removes a flag, or
changes what a flag means. Exactly two things a user could notice change at all: A5 turns an input
that is silently discarded today into one that is refused, and A4 changes the wording — not the
exit code — of the errors for a malformed `calibrate` option. Nothing else.

**The flag vocabulary, as spellings.** Four ways of saying "show me and stop" (`rm --dry-run`,
`pi --print`, `update --check`, `engine install --no-model`), two meanings of `--force`, and the
abbreviated `--keep-hf` are all real incoherences — and adding synonyms would buy uniformity at
the price of permanent duplication. A7 documents them in one table instead. That is the whole fix.

## A.2 The five defects

| | Defect | Verified at |
|---|---|---|
| **D1** | Help and every usage line print `Usage: bora-workbench …`, while the executable on PATH is `bora`. The tool names a command that does not exist. | `cli.py:33` |
| **D2** | `--no-activate`, `--activate`, and `--target-ctx` are real options that are not declared: absent from the generated `--help` table, no shell completion, and **no `--target-ctx=N` form**, because the hand-written parser reads `arguments[index + 1]`. | `cli.py:187-208`, `_cli_calibration.py:86-123` |
| **D3** | `bora pi --install remove` parses and **silently discards** `--install`; `bora pi --print --install` discards it too. | `cli.py:141-142`, `_cli_pi.py:181-184` |
| **D4** | `run_validate` guards nothing, and inside `run_doctor` four calls sit outside the `try`: `validate_resources()`, `load_catalog()`, `_record_lines()`, `engine_status()`. A failure in any of them escapes as a traceback, instead of the exit 1 that `docs/commands.md:68-69` promises and the tracebackless failure that specification 5.11 requires. | `_cli_diagnostics.py:317-322`, `:452-459` |
| **D5** | `print_warning` writes to stdout at twelve call sites and to stderr at seven, with no stated rule; `_print_status` splits *one* list of engine differences across both streams inside a single loop. | `_cli_diagnostics.py:237-242` |

### Why D2 exists

It is not an oversight. `tests/test_code_quality.py:69-78` caps every function in `src/` at three
parameters, with no exception, and `calibrate(context, mode, preference)` is already at three. The
three missing options were pushed into a hand-written parser **to stay under the ceiling**. So did
`remove_model_command` and the `pi` callback, both sitting exactly at three.

Applied mechanically, the limit produced the opposite of its purpose: it hid a published interface
in order to protect an internal one. A2 fixes the rule, A4 then fixes the command.

## A.3 The seam the front end needs

Half of it already exists. `run_doctor` builds a frozen `DoctorData` (`_cli_diagnostics.py:325-333`)
and `_record_line` (`:397-427`) renders from a `RecordEvaluation` that is already a structured
object. What is missing is the public directories, the validation result, and the records **as
data** rather than as pre-rendered strings. A6 closes it, and closing it also fixes D4 by
construction, because every one of those unguarded calls moves inside one collector with one
`try`.

`TUI.md:221-223` set the condition: if this extraction turns out to be large, that is the signal to
stop and reconsider the front end. It is not large.

## A.4 The steps

### A1 — Anchor this plan and answer the six open questions

- **Goal.** Give Backlog D a normative entry, so that this file is the detail of an authorized
  perimeter rather than a side plan (`IMPLEMENTATION_SPEC.md:579-585` forbids side plans).
- **Files.** `IMPLEMENTATION_SPEC.md`, `TUI.md`.
- **Change.**
  1. Section 3: add **D-083** after D-082 (`:274`), before the closing line at `:276`. It accepts
     an interactive front end as post-`0.2` Backlog D without scheduling it, records the six
     answers of Appendix A, names `TUI_PLAN.md` as Backlog D's execution plan and `TUI.md` as its
     design record, and states that Part A is authorized while Part B is not. Match the density of
     the existing entries: one paragraph, reasons included.
  2. Section 8: add `### Backlog D — Interactive front end` after Backlog C ends (`:794`) and
     before `### Local 0.2.0 finalization` (`:796`). Keep it to a few paragraphs — what it is, the
     handoff constraint, the phases by name, and the two file pointers. **Do not copy Part B here**;
     two roadmaps that must agree eventually stop agreeing.
  3. Amend D-077 (`:268`), which left the disposition of `TUI.md` open, with one sentence recording
     that the question is now answered and the file stays as the design record.
  4. Apply the `TUI.md` errata of Appendix B.
- **Decision.** D-083. **A decision entry states what the maintainer decided, so the six answers in
  Appendix A need the maintainer's assent before this step is written.** They are recommendations
  until then, and this whole file waits on them.
- **Verify.** `pytest`; `bora validate`; `TUI.md`'s status block no longer claims `0.2.1`; its
  screen→command table and the summary table of `docs/commands.md` name the same commands.
- **Done when.** The specification names this file, and `TUI.md` describes the surface that exists.

### A2 — Make the readability limits deliberate defaults

- **Goal.** Stop a mechanical ceiling from forcing designs that are worse than the code it rejects,
  without losing the signal that the ceiling exists.
- **Files.** `tests/test_code_quality.py`, `AGENTS.md`, `docs/development.md`.
- **Change.**
  - Add three module-level maps to `tests/test_code_quality.py`, each from a location to the reason
    it is accepted:

    ```python
    _ACCEPTED_FILE_LENGTH: dict[str, str] = {}       # "src/pkg/module.py"
    _ACCEPTED_FUNCTION_LENGTH: dict[str, str] = {}   # "src/pkg/module.py::name"
    _ACCEPTED_PARAMETERS: dict[str, str] = {}        # "src/pkg/module.py::name"
    ```

    Each of the three size tests then fails on **unregistered** breaches only — and also fails on an
    entry that no longer corresponds to a real breach, so the list cannot rot into a permanent
    exemption. Use forward slashes in keys so the tests behave identically on both platforms.
  - **Nesting stays a hard maximum**, and the docstring test stays a hard requirement. Nesting is
    the one limit that always has a mechanical fix — extract a helper, invert a condition — so
    exceeding it is never the honest answer. A docstring is not a design trade-off.
  - `AGENTS.md:73-85`: the first three limits become defaults rather than walls. State the test:
    exceed one deliberately when splitting would scatter an area of competence or hide a published
    interface, and register the exception with its reason. The existing exemptions for fixtures and
    declarative content stay as they are.
  - `docs/development.md:100-102`: mirror the same wording.
  - **No change under `src/`.** The limits widen; nothing needs to move.
- **Decision.** D-084.
- **Verify.** Add a throwaway four-parameter function: the test fails. Register it: the test
  passes. Delete the function but keep the entry: the test fails again.
- **Done when.** The three maps are empty, the suite is green, and the three documents agree.

### A3 — Name the program `bora`

- **Goal.** Stop printing a command name that is not installed.
- **Files.** `cli.py`.
- **Change.** `cli.py:33`, `name="bora-workbench"` → `name="bora"`. Leave every other occurrence
  alone: the `doctor` table title and the four public directories name the *distribution*, which is
  correct, and `tests/test_cli.py:100` asserts on that title.
- **Decision.** — (restores the contract of `pyproject.toml:22-23`).
- **Verify.** `bora --help` and an unknown command both print `bora` in the usage line. No test
  asserts on the old program name in usage output; confirmed.
- **Done when.** No usage or error line names `bora-workbench`.

### A4 — Declare the three calibrate options

- **Goal.** Make the whole of `calibrate` visible to `--help`, to shell completion, and to any
  program that composes a command line.
- **Files.** `cli.py`, `_cli_calibration.py`, `docs/commands.md`, `tests/test_cli_calibration.py`,
  `tests/test_code_quality.py`.
- **Change.**
  - `cli.py`: delete `_CALIBRATION_EPILOG` (`:50-55`); drop `context: typer.Context`,
    `context_settings={"allow_extra_args": ..., "ignore_unknown_options": ...}` and `epilog=`
    from the decorator (`:187-208`); declare `no_activate`, `activate`, and `target_ctx` as
    ordinary Typer options; construct `CalibrationCliInput` directly and hand it to
    `run_calibrate`.
  - The `try`/`except CalibrationError` around parsing (`:203-207`) **disappears entirely**, and
    with it the imports of `parse_calibration_input` (`:10`) and `CalibrationError` (`:30`). This
    is safe because validation never happened at parse time: `_validate` runs inside `_run`
    (`_cli_calibration.py:462`) and `run_calibrate` already maps `CalibrationError` to exit 2
    (`:499-501`).
  - `_cli_calibration.py`: delete `_target_ctx` (`:86-93`) and `parse_calibration_input`
    (`:96-123`). `CalibrationCliInput`, `_preference`, `_validate_target_ctx`, and `_validate` all
    stay untouched — the mutual-exclusion rules do not change.
  - `tests/test_code_quality.py`: one entry in `_ACCEPTED_PARAMETERS` for `cli.py::calibrate`,
    reading roughly *a Typer command's parameters are the published CLI surface, not an internal
    interface*.
  - `docs/commands.md`: delete `:373-375`, the paragraph explaining why three options live in the
    epilog. The option table at `:343-349` already documents all five and needs no change.
  - `tests/test_cli_calibration.py`: six references pass the extras as raw arguments; pass them as
    ordinary options instead. Nothing else in the suite is affected — the seventh grep hit,
    `tests/test_cli_doctor.py:47`, asserts on the text `doctor` prints about a pending candidate
    and has nothing to do with parsing.
- **Decision.** D-085.
- **Verify.** `calibrate --help` lists five options in the generated table and has no epilog;
  `--target-ctx=65536` is accepted; `--activate --target-ctx 65536` exits **2**; `--pippo` exits
  **2**; `--target-ctx abc` exits **2**.
- **Done when.** No option of `calibrate` is reachable that `--help` does not name.

> The exit-code contract holds across this change, which is the reason it is safe. Every input that
> exits 2 today still exits 2; only the wording moves from a bespoke message to Typer's. That is the
> trade: a slightly less specific error for an option surface that is discoverable, completable,
> and composable. `docs/commands.md:373-375` exists precisely to apologize for the current state.

### A5 — Refuse pi flags that a subcommand would discard

- **Goal.** Never accept an input and then ignore it.
- **Files.** `cli.py`, `_cli_pi.py`, `docs/commands.md`.
- **Change.**
  - `cli.py:130-142`: when `context.invoked_subcommand is not None` and either `--print` or
    `--install` was given, report the conflict on stderr and exit **2**.
  - `_cli_pi.py:174-184`: `--print` with `--install` is the same class of error — `--print` writes
    nothing, so installing pi cannot affect the result. Refuse it before `_context_window` runs.
  - Note both refusals in the `pi` section of `docs/commands.md`.

  The alternative — honour `--install` first and then print — was considered and rejected:
  `--print` exists to produce the entry with no side effect anywhere, and installing a global npm
  package is a large side effect. A flag that promises to write nothing must not install software.
- **Decision.** — (an invalid input reported as invalid; spec 5.11 already classifies it).
- **Verify.** `bora pi --install remove` exits 2; `bora pi --print --install` exits 2; `bora pi`,
  `bora pi --print`, `bora pi --install`, `bora pi remove`, `bora pi uninstall` are unchanged.
- **Done when.** No flag combination is accepted and then dropped.

### A6 — Render `doctor` from a structured snapshot

- **Goal.** Separate collecting the machine's state from printing it, so the state can be read by
  something that is not a console — and so that every failure inside the collection maps to its
  contractual exit code.
- **Files.** new `src/bora_workbench/_cli_snapshot.py`, `_cli_diagnostics.py`, new
  `tests/test_cli_snapshot.py`.
- **Change.**
  - `_cli_snapshot.py` holds one frozen, slotted dataclass and one collector:

    ```python
    @dataclass(frozen=True, slots=True)
    class Snapshot:
        version: str
        config: Config
        hardware: HardwareInfo
        engine: EngineStatus
        content: ValidationResult
        compatible_profiles: int
        records: tuple[tuple[str, RecordEvaluation], ...]
        locations: tuple[tuple[str, Path], ...]   # config, data, cache, state

    def collect_snapshot(version: str) -> Snapshot: ...
    ```

    Dataclass fields are not function parameters, so the A2 limits are untouched here:
    `collect_snapshot` takes one argument and `run_doctor` keeps its three.
  - `collect_snapshot` absorbs everything `run_doctor` computes inline today, **including the four
    unguarded calls of D4**. `run_doctor` keeps its signature and becomes collect, render, map exit
    code, with one `try` around the collection. `_doctor_table` and `_record_line` take the
    snapshot.
  - **Keep the order of collection**: configuration, hardware, content validation, records, engine
    status, and the four public directories **last**. Today the directories are resolved during
    rendering (`_cli_diagnostics.py:354-355`), and the comment directly above them (`:351-353`)
    says why: resolving a public directory is the only step there that can fail, and *which error a
    reader sees first is part of the behavior* (specification 5.11). Collecting them earlier would
    silently reorder the first failure a user meets. This is the one trap in the step.
  - `run_validate` (`_cli_diagnostics.py:317-322`) gets the guard it never had.
  - `docs/architecture.md:38-63` and the normative table of specification 4.1 need no change: their
    `cli.py`, `_cli_*` row already covers a new `_cli_*` module.
  - `tests/test_cli_snapshot.py` tests the collector **with no console at all**, which is half the
    value of the refactor.
- **Decision.** D-086.
- **Verify.** Capture `bora doctor`'s stdout before and after; it must be **byte-identical**. Then
  a fake that raises `EngineError` from `engine_status()` must produce exit 1 with a message on
  stderr, not a traceback.
- **Done when.** `doctor` prints what it printed before, and nothing it needs is computed while it
  prints.

> **Scope guard.** The snapshot covers *exactly* what `doctor` renders today. Not services, not the
> presence of the model, not anything a screen might want later — `AGENTS.md:23-24` forbids code that
> anticipates a later milestone, and a front end can compose this snapshot with the
> `across_service_roots` sweep that `status` already uses, without a line of new code.

### A7 — Give the vocabulary one table and the streams one rule

- **Goal.** Make the incoherences legible, and stop them from growing silently.
- **Files.** `docs/commands.md`, `_cli_diagnostics.py`, new `tests/test_docs_commands.py`.
- **Change.**
  - Summary table (`docs/commands.md:12-31`): add rows for `pi remove` and `pi uninstall`, which
    exist only in the body today.
  - New **Flag vocabulary** section after the summary: one table of flag, command, and meaning,
    stating plainly that `--force` means *reinstall anyway* on `engine install` and *bypass the RAM
    gate* on the three run modes, and that `--dry-run`, `--print`, `--check`, and `--no-model` are
    four spellings of one idea. Add one sentence on why deletion is spelled three ways: `rm` takes
    the model, `pi remove` takes an entry from somebody else's configuration file, and `uninstall`
    takes this installation. Those are three different objects, and that is an explanation rather
    than an apology.
  - One sentence on the stream rule: **stdout carries the report, stderr carries whatever explains
    a non-zero exit or a degradation.**
  - `_cli_diagnostics.py:237-242`: `_print_status` picks one stream per call instead of splitting a
    single list across both.
  - `tests/test_docs_commands.py`: walk `typer.main.get_command(app)`, collect every command path
    and every option string, and assert each appears somewhere in `docs/commands.md`. Search by
    presence rather than by heading, because `coding`, `studio`, and `vstudio` share one "Run
    modes" section. Exclude `--help`, which is on every command and documented once at
    `docs/commands.md:9`; `--install-completion` and `--show-completion` are already documented at
    `:9-10` and need no exclusion. Offline, deterministic, hardware-independent.
- **Decision.** —
- **Verify.** Delete any command row from `docs/commands.md`: the new test fails. Add a flag to any
  command without documenting it: the new test fails.
- **Done when.** The documented surface and the parsed surface cannot drift apart unnoticed.

## A.5 What Part A must not become

Not a rename pass, not a regrouping, not a chance to "improve" an API, and not a place to add the
front end's data path ahead of the front end. `compose(state) -> argv` is **not** written in Part
A: it would have no caller, and `AGENTS.md:95` forbids unused extension points. What makes the CLI
composable is A4, not a helper waiting for a user.

---

# Part B — The interactive front end

Accepted as Backlog D, unscheduled. Everything below is design, not authorization.

## B.0 The gate

Do not start B1 until all three hold:

1. Part A is complete and released;
2. the open `0.2` items in specification section 0 are closed — cross-platform release CI, the real
   `update` / `pull` / `rm` / `pi` runs, the Windows trial adapter;
3. a maintainer decision schedules the phase, recorded in section 3.

The second condition is the one that matters, and `TUI.md:723-728` states the objection it answers:
a new surface on an unstable base is the most expensive thing this project could build.

## B.1 The four seams

The whole architecture is four connections to code that already exists. Nothing else is new.

| Seam | What it is | State |
|---|---|---|
| **Snapshot** | the read-only picture, as data | **A6 builds it** |
| **Composer** | `compose(screen_state) -> tuple[str, ...]`, the exact argv the CLI would parse | phase 2 |
| **Handoff** | leave the alternate screen, print the command, run it as a child, exit with its code | phase 2 |
| **Progress** | the existing `RunOptions(progress=…)` port, if anything is ever hosted in-process | never, unless proven necessary |

**Handoff, not embedding**, is the decision the whole design rests on, and `TUI.md:259-295` argues
it in full. In one line: the run modes hold the foreground until `Ctrl-C`, calibration runs for
hours, `uninstall` deletes the installation that would be running the UI, and the exit codes are a
contract — every one of those problems disappears when the front end's last act is to run the
command it is showing and get out of the way. Use `subprocess.run` with inherited stdio on both
platforms; Windows has no real `exec`.

The composer is the only thing worth testing heavily, and it is pure: one table-driven test
enumerates every reachable screen state and asserts the argv, and a second feeds every produced
argv to the real parser and asserts it is accepted. After A4 that second test targets the Typer
app through `CliRunner`, because after A4 the Typer app *is* the parser.

**No new event system**, no plugin points, no adapters (`AGENTS.md:97`).

## B.2 The phases

| Phase | Content | Worth it if you stop here |
|---|---|---|
| **1** | `bora tui`: banner, gust, sea, a dashboard rendering the A6 snapshot, `r` to refresh, `q` to quit. Read-only. **Rich only** — a static screen and a keypress need no event loop. | the identity, and a genuinely useful overview |
| **2** | Navigation rail, the modes and calibration screens, the composer, the handoff. **The dependency decision happens here**, with phase 1 as evidence. | the whole concept |
| **3** | Onboarding checklist, records pane, danger zone. | the first-run experience |
| **4** | Polish: clipboard, `$EDITOR`, help overlay. | — |

Phase 1 acceptance, from `TUI.md:771-775`: starts with no side effects, exits restoring the
terminal, renders at 80×24, 120×40, and 60×20, degrades to ASCII without UTF-8 and to one plain
line without a TTY, idles under the CPU budget, and **does not slow `bora --version` down by
importing anything new**.

Phase 2's dependency decision (`textual`, or a hand-written reader on Rich) follows the procedure
of `AGENTS.md:163-174` and amends D-003 with its own entry. Deciding it after phase 1 rather than
before is the point: it is the difference between deciding with evidence and deciding by taste.

For screens, mockups, the keymap, the banner, the gust and sea, the palette, the motion budget, and
the terminal-degradation ladder, read `TUI.md` sections 4, 5, and 6. They are good and this file
does not restate them.

## B.3 The package reorganization — later, and optional

`TUI.md` Part I proposed moving `src/bora_workbench/` from a flat namespace into packages, and put
it **first**. Demote it to an optional prerequisite of phase 2. It changes no behavior, and putting
mechanical churn ahead of everything is part of why nothing moved.

Its inventory needs updating when it is reconsidered: the tree is now **45 files, 29 of them
`_`-prefixed satellites of seven areas** — not the 26 and 21 that `TUI.md:49-60` describes — and it
has since grown `models.py`, `pi_link.py`, `update.py`, `_model_*`, `_tool_*`, and three more
`_cli_*` modules. A `cli/` package would hold eight modules today, not five.

If it is ever done: `git mv` only, no edits inside the moved files beyond import lines, the public
import paths preserved through `__init__.py` re-exports, and the normative tables of specification
4.1 and 4.2, `docs/architecture.md`, and `docs/development.md` updated in the same commit.

## B.4 Contracts a front end must not break

A review checklist, not aspirations:

1. importing the package still performs no I/O; the front end module is imported only when its
   command runs;
2. exit codes stay `0 / 1 / 2 / 130`, produced by the same code as today — the front end adds none;
3. no TTY, no front end: `bora tui` without one prints a line and exits 2;
4. `config.toml` is never written; the settings screen is read-only;
5. no new network access, no telemetry, no port — the front end starts no server;
6. preflights and confirmations are never re-implemented, pre-answered, or suppressed;
7. everything reachable in the front end is reachable by typing; nothing is front-end-only;
8. opening it starts no process, creates no directory, writes no state;
9. platform branching stays in `paths`, `process`, `hardware`, and `engine`; terminal capability
   detection is one small named helper, not platform logic scattered through screens;
10. the A2 limits govern the new package from the moment it exists, exceptions registered as usual.

## B.5 The objections worth keeping

- **Opportunity cost is the strongest one.** A front end is a new surface on a base with open
  items. B0 exists to answer it, and the honest answer may remain "not yet" for a long time.
- **A UI is the opposite of reproducible**, and reproducibility is this project's thesis. The
  answer is P2 from `TUI.md:166-169`: every screen that can act shows the exact command it will
  run, in a fixed place, before running it. A front end that teaches the CLI is defensible; one
  that replaces it is not.
- **Scope creep has a natural home here.** Model pickers, flag editors, profile builders — none of
  them become reachable because a screen has room. `README.md:37-43` draws that line already.

---

# Appendix A — The six open questions, answered

`TUI.md:787-794` left six questions to the maintainer. A1 records these answers.

| | Question | Answer |
|---|---|---|
| **Q1** | Is the package reorganization approved as an independent step? | **No, not now.** It becomes an optional prerequisite of phase 2 (B.3). It changes no behavior, and putting it first is what kept everything else waiting. |
| **Q2** | Is an interactive front end accepted at all? | **Yes, as Backlog D, unscheduled.** Behind the B0 gate. |
| **Q3** | Handoff or embedded execution? | **Handoff.** It keeps the CLI the single source of behavior, and hands the exit codes, the signal handling, and the process lifetime back to the code that already owns them. |
| **Q4** | Rich only, or is `textual` an approved dependency? | **Deferred to phase 2.** D-003 is unchanged. Phase 1 is Rich only, and it is the evidence the dependency decision needs. |
| **Q5** | Does bare `bora` stay `no_args_is_help`? | **Yes, permanently.** The front end ships as `bora tui`. Changing what a bare invocation does is a CLI contract change with no upside. |
| **Q6** | Is the settings pane read-only forever? | **Read-only.** It follows a rule that is already normative: the launcher never rewrites `config.toml` (`README.md:317`, `AGENTS.md:134`). |

# Appendix B — `TUI.md` errata, applied by A1

| Where | Now says | Should say |
|---|---|---|
| status block, `:1-14` | proposal written against `0.2.1`, disposition open | design record for Backlog D, written against `0.3.2`, with a pointer to this file |
| `:49-60` | 26 modules, 21 `_`-prefixed, five areas | 45 files, 29 `_`-prefixed, seven areas; `cli/` would hold eight modules |
| `:186-196` | screen→command table | add `pull`, `rm`, `pi`, `pi remove`, `pi uninstall`, `update`, and `engine install --no-model` |
| `:40-41` | a quotation in Italian | English, per `AGENTS.md:46-48` |
| Part I | "code layout first" | later and optional, per B.3 |

# Appendix C — Verification

After **every** step, the frozen suite (`AGENTS.md:176-198`):

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
```

No step in Part A touches `resources/`, so `uv build` and `scripts/verify_wheel.py` are not
required; running them once before the last step is cheap and closes the loop. If a tool or a
platform is unavailable, report that limitation — do not claim the check passed.

The per-step checks are in each step's **Verify** field. Two of them carry most of the weight:

- **A6**: `bora doctor`'s stdout must be byte-identical before and after. A refactor that changes
  output is not a refactor.
- **A7**: removing a documented command must fail the suite. Documentation kept in sync by
  discipline alone is documentation that will eventually be wrong.
