# bora — command surface, code layout, and interactive front end: the plan for 0.4.0

> **Status: execution plan, not authorization.** `IMPLEMENTATION_SPEC.md` remains the only normative
> plan: it holds the authority, this file holds the steps, and `TUI.md` holds the visual design
> record. **Step A1 is what authorizes everything else**: until the specification names this file and
> records the decisions of Appendix A, nothing below should be committed, because specification 6.2
> forbids side plans.
>
> Written against `0.3.2` at commit `4088997`. Every `file:line` was verified at that commit.
> **Match by content, not by number**: a reference whose quoted code still matches is still correct
> wherever it moved; a reference that no longer matches means this plan is stale, not the code.

---

## 0. What 0.4.0 is

**`0.4.0` is the release that ships the reorganized command surface, the reorganized package tree,
and the interactive front end, together.** The version number is not taken until Part B is complete
and working against the acceptance criteria in Part C; until then the work lives on the branch and
`pyproject.toml` still says `0.3.2`.

Three things happen, in this order, and the order is the plan:

| | Part | Why it comes first |
|---|---|---|
| **A** | The commands and the tree | The front end is a *second reader* of the command surface. Reorganizing after it exists means reorganizing twice, and the second time with a UI in the way. |
| **B** | The front end | It sits on the vocabulary Part A defines, and adds exactly one command: `bora tui`. |
| **C** | The release | `0.4.0`, prepared exactly as `docs/releasing.md` describes. |

**What 0.4.0 does not change:** the engine release, the model, `command_contract`,
`command_contract_sha256`, the calibration protocol, `calibration-record/v6`, the reserves, the
packaged policy and schemas, the four managed roots, or the exit codes. Every existing record stays
valid, and no local candidate is activated. Part A touches **no file under
`src/bora_workbench/resources/`** — it is a core change end to end (`CONTRIBUTING.md:27-34`).

**What a user gains, in one line each:** commands whose names say what they act on; a `--help` that
is organized instead of alphabetical; a tree a reader can hold in their head; and a front end that
always knows what this machine should do next and shows the exact command before it runs it.

---

## 1. How to read a step

Every step below declares six fields. A step missing one is not ready to execute.

| Field | Meaning |
|---|---|
| **Goal** | the one outcome; if it needs an "and", it is two steps |
| **Files** | every file the step may touch, and no others |
| **Change** | precise enough that executing it requires no new design decision |
| **Decision** | the `D-0xx` entry it records, or `—` when it restores an existing contract |
| **Verify** | the check that would fail if the step were wrong |
| **Done when** | the observable condition that ends the step |

The standing rules apply unchanged (`AGENTS.md:200-219`, `CONTRIBUTING.md:27-34`): one step per
commit; Conventional Commits with a body naming the constraints and the checks performed;
documentation travels with its area in the same commit; core and packaged content never mix; and
after **every** step, the frozen suite of Appendix C.

Decision numbers `D-083`…`D-088` are **indicative**. Take the next free number in the table at the
moment the step actually lands: a plan that reserves a block it does not own collides with whatever
was decided meanwhile (`TUI.md:778-785`).

---

# Part A — Fix the commands and the tree

## A.0 The surface today

Entry point `bora = "bora_workbench.cli:app"` (`pyproject.toml:22-23`), Typer `0.26.8`, Rich
`15.0.0`. Every command is declared in `src/bora_workbench/cli.py` — 240 lines, no logic — and each
body delegates to a `run_*` function in one of eight `_cli_*` modules. **Seventeen invocable paths**
plus `--version`:

| Path | Options | Mutates | Prompts | Long |
|---|---|---|---|---|
| `bora validate` | — | no | no | no |
| `bora doctor` | — | no | no | no |
| `bora engine status` | — | no | no | no |
| `bora engine install` | `--force`, `--no-model` | yes | no | **yes** — download, plus a CMake build on Ubuntu CUDA |
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

Exit codes are `0 / 1 / 2 / 130` (specification 5.11, `docs/commands.md:446-457`).

The tree behind it is **45 hand-written modules, 11,799 lines, in one flat namespace**, of which
**29 are `_`-prefixed satellites of eight areas**:

```
cli.py          + 7 × _cli_*.py           calibration.py  + 11 × _calibration_*.py
engine.py       + 2 × _engine_*.py        validation.py   +  4 × _validation_*.py
models.py       + 2 × _model_*.py         process.py      +  1 × _process_state.py
benchmark.py, benchmark_quick.py          update.py, uninstall.py + 2 × _tool_*.py
config.py, hardware.py, paths.py, profiles.py, pi_link.py
```

The 600-line ceiling is doing its job — no file is a monolith — but its cost is paid in the file
listing: eleven sibling files that a reader has to reassemble into one area of competence, which is
the exact failure `AGENTS.md:78-80` warns about ("prefer one readable module per area over a
constellation of two-function files"). `engine.py` is at **592 of 600 lines**, so that area cannot
absorb another idea without a split it has been postponing.

## A.1 What is actually wrong

### Six defects

| | Defect | Verified at |
|---|---|---|
| **D1** | Help and every usage line print `Usage: bora-workbench …`, while the executable on `PATH` is `bora`. The tool names a command that does not exist. | `cli.py:33` |
| **D2** | `--no-activate`, `--activate`, and `--target-ctx` are real, documented options that are **not declared**: absent from the generated `--help` table, no shell completion, and no `--target-ctx=N` form, because the hand-written parser reads `arguments[index + 1]`. | `cli.py:187-208`, `_cli_calibration.py:86-123` |
| **D3** | `bora pi --install remove` parses and **silently discards** `--install`; `bora pi --print --install` discards it too. | `cli.py:130-142`, `_cli_pi.py:174-184` |
| **D4** | `run_validate` guards nothing, and four calls inside `run_doctor` sit outside every `try`: `validate_resources()`, `load_catalog()`, `_record_lines()`, `engine_status()`. A failure in any of them escapes as a **traceback**, instead of the exit 1 that `docs/commands.md:68-69` promises and the tracebackless failure specification 5.11 requires. | `_cli_diagnostics.py:317-322`, `:452-459` |
| **D5** | `print_warning` writes to stdout at eleven call sites and to stderr at seven, with three more going through a differently named console, and no rule is stated anywhere; `_print_status` splits *one* list of engine differences across both streams inside a single loop. | `_cli_diagnostics.py:237-242` |
| **D6** | There is no structured way to read this machine's state. `doctor` computes while it prints, so a second reader would have to scrape its stdout. | `_cli_diagnostics.py:440-470` |

**Why D2 exists, and why it matters beyond `calibrate`.** It is not an oversight.
`tests/test_code_quality.py:69-78` caps every function in `src/` at three parameters with no
exception, and `calibrate(context, mode, preference)` is already at three. The three missing options
were pushed into a hand-written parser **to stay under the ceiling**; `remove_model_command` and the
`pi` callback sit at exactly three for the same reason. Applied mechanically, a readability limit
produced the opposite of its purpose: it hid a *published* interface in order to protect an
*internal* one. A2 fixes the rule before A7 fixes the command.

### Four naming problems

**N1 — Removal is spelled four ways and only one of them names its object.** `bora rm` deletes
21.9 GiB of weights and does not say so. `bora uninstall` deletes this installation. `bora pi remove`
deletes an entry from a file belonging to another program. `bora pi uninstall` hands a package back
to npm. Those are four different objects, which is a good reason for four verbs — and a bad reason
for two of them to omit the object entirely.

**N2 — The root mixes two kinds of thing.** `coding`, `status`, `stop`, `doctor` are things you do
in a session. `pull`, `rm`, `update`, `uninstall` are things you do to an installed object. Typer
prints them as one alphabetical list of fourteen, so nothing in the output says which is which, and
nothing says that `pull` and `rm` are a pair.

**N3 — `bora pi` means three things.** It is a group, and a command, and a command with flags. That
overload *is* defect D3: `invoke_without_command=True` is what makes a discarded flag possible.

**N4 — Nothing tells the front end what to call a section.** A front end has to name its rail. If the
CLI has no vocabulary for "the model" or "this installation", the front end invents one, and an
invented taxonomy in the UI is exactly the drift that makes two front ends disagree.

### What is *not* wrong, and must survive

- **`coding`, `studio`, `vstudio` at the root.** They are the product ("one Qwen setup, three local
  experiences", `README.md:8-14`), they are the most typed commands, and they are packaged **mode
  ids** bound into every `calibration-record/v6`. Renaming them would invalidate records for
  cosmetics. They stay, spelled exactly as they are.
- **`doctor`, `validate`, `status`, `stop`, `calibrate`.** Each is a verb with one unambiguous
  object. Nothing is gained by moving them under a noun.
- **The command tree stays shallow.** Two levels, never three.
- **Backward compatibility of *behavior*.** No step changes what a command does. The only observable
  changes are: four paths are renamed (A.4), two flags are renamed along with the command they live
  on, three inputs that are silently discarded today become refused, and one input that produced a
  traceback now produces an actionable error.

## A.2 The organizing rule

> **The root holds verbs about *this session*. A group holds a *thing with a lifecycle* that you
> installed.**

Everything you install, inspect, and remove is a group: the **engine**, the **model**, the **pi**
connection, and **this installation** (`self`). Everything you do with the machine right now is a
root verb: run a mode, look at it, stop it, measure it, diagnose it.

That rule is checkable in one pass, it produces exactly the surface below, and — the reason it is
worth adopting — **it is also the front end's rail**. One vocabulary, three places: `--help` panels,
`docs/commands.md` headings, and the TUI sections. When a rule changes, all three change together
because they are the same words.

## A.3 The target surface

`bora [--version] <command> [options]`, with `--help` on the group and on every command. Panels are
Typer's `rich_help_panel`, so `bora --help` prints six titled sections instead of one alphabetical
list.

| Panel | Command | Options | Change |
|---|---|---|---|
| **Run a mode** | `bora coding` | `--force` | — |
| | `bora studio` | `--force` | — |
| | `bora vstudio` | `--force` | — |
| **Services** | `bora status` | — | — |
| | `bora stop` | — | — |
| **Tune** | `bora calibrate` | `--mode`, `--preference`, `--target-ctx`, `--no-activate`, `--activate` | all five **declared** |
| **Setup** | `bora engine install` | `--force`, `--no-model` | — |
| | `bora engine status` | — | — |
| | `bora model pull [MODEL]` | — | was `bora pull` |
| | `bora model rm [MODEL]` | `--keep-hf`, `--dry-run` | was `bora rm` |
| **Connect** | `bora pi connect` | `--dry-run`, `--install` | was `bora pi`; `--print` → `--dry-run` |
| | `bora pi remove` | — | — |
| | `bora pi uninstall` | — | — |
| **Inspect** | `bora doctor` | — | — |
| | `bora validate` | — | — |
| | `bora tui` | `--plain` | **new, Part B** |
| **This installation** | `bora self update` | `--dry-run` | was `bora update --check` |
| | `bora self uninstall` | — | was `bora uninstall` |

**Seventeen paths before `tui`, exactly as today.** Nothing was added, nothing merged, nothing
dropped. Appendix D records the regroupings that were considered and rejected.

Why each group name is the honest one:

- **`engine`** — unchanged, already correct.
- **`model`** — `pull` and `rm` are one pair acting on one object; the group is the object. `pull`
  keeps its name because it is the universal verb for weights, and `rm` keeps its name because it is
  the inverse of `pull` in every tool that has both. What changes is that the object is now written
  down.
- **`pi`** — `connect` replaces the bare invocation. It is a *verb for what it does* (it does not
  install pi, it points pi at this machine), and declaring it kills N3 and D3 by construction: a
  group with no `invoke_without_command` cannot swallow a flag.
- **`self`** — `uv self update` and `rustup self uninstall` established the word, and it answers the
  question `bora uninstall` never answered: *uninstall what?* It also puts the two commands that
  replace or delete the running program next to each other, where a reader can see that they are the
  same kind of dangerous.

## A.4 What moved, and what happens if you type the old name

| Old | New |
|---|---|
| `bora pull` | `bora model pull` |
| `bora rm` | `bora model rm` |
| `bora update` | `bora self update` |
| `bora update --check` | `bora self update --dry-run` |
| `bora uninstall` | `bora self uninstall` |
| `bora pi` | `bora pi connect` |
| `bora pi --print` | `bora pi connect --dry-run` |

**No aliases.** The old spellings become a **moved-name notice**: a `TyperGroup` subclass whose
`get_command` raises `click.UsageError` for a known old name, printing

```text
`bora rm` is now `bora model rm`.
```

and exiting **2** — the contractual code for invalid input, and *nothing runs*. The same notice
covers `--print` and `--install` on the `pi` group.

This is deliberate and it is not a fallback (`AGENTS.md:132-133`, specification 5.12: "no
undocumented fallback"). An alias that silently does the work would be a second spelling to keep
correct forever, and a second thing a front end could compose; a notice teaches the new name once
and costs about twelve lines. The notice itself is **removed in `0.5.0`**, and that removal is part
of the decision, not a later judgement call.

The licence for renaming at all is stated by the project itself: `README.md:58-62` — "The `0.3`
series is **not stable** … The CLI, configuration, record formats, procedures, and performance carry
no stability guarantee." A rename is exactly the change that boundary exists to permit, and
`0.4.0` is exactly when to spend it. **Verified: no command string appears in `evidence/` or in
`src/bora_workbench/resources/`**, so no checksum-bound byte moves and no digest chain is touched.

## A.5 The flag vocabulary

One rule, applied where it costs nothing:

> **`--dry-run` is the one spelling of "show me what you would do, and do nothing."**

| Flag | Command | Meaning | Change |
|---|---|---|---|
| `--dry-run` | `model rm` | list both groups and every path, delete nothing, ask nothing | — |
| `--dry-run` | `pi connect` | print the provider entry, write nothing | was `--print` |
| `--dry-run` | `self update` | report installed and published version, install nothing | was `--check` |
| `--force` | `engine install` | reinstall a target that is already active and compatible | — |
| `--force` | `coding`/`studio`/`vstudio` | bypass **only** the 28 GiB total / 22 GiB available gate of the default model | — |
| `--no-model` | `engine install` | install the engine without acquiring the weights | — |
| `--keep-hf` | `model rm` | skip the shared-cache question entirely | — |
| `--install` | `pi connect` | install pi with npm first, after showing the command and asking | — |

Both flag renames are **free**, because the command they live on is renamed in the same release:
`bora pi --print` and `bora update --check` are already unreachable spellings once `pi connect` and
`self update` exist. Renaming a flag whose command did not move would not have been worth it.

`--force` keeps two meanings, and that is a decision, not an omission. Renaming the launch one to
`--skip-memory-gate` was considered (Appendix D): it is more honest and it is more typing on the one
escape hatch people need under pressure. Instead, the two meanings get one row each in the table
above and the front end prints the memory-gate meaning inline next to the key that adds it.

## A.6 The package tree

The listing is what a reader meets first, so it should name the eight areas, not the forty-five
files.

```text
src/bora_workbench/
├── __init__.py                 no imports, no statements — the import-purity contract (4.3)
├── paths.py                    per-OS roots, no creation                      [may branch on OS]
├── config.py                   TOML, environment, precedence, validation
├── hardware.py                 CPU, RAM, NVIDIA, GPU selection                [may branch on OS]
├── profiles.py                 modes, gates, LaunchPlan
├── pi_link.py                  the one supported agent integration
├── snapshot.py                 the read-only picture of this machine, as data   ← new (A9)
├── resources/                  packaged schemas, content, locks — unchanged
├── cli/
│   ├── __init__.py             re-exports `app` for the console script
│   ├── __main__.py             `python -m bora_workbench.cli`                   ← new (A3)
│   ├── app.py                  was cli.py — Typer wiring, panels, exit codes
│   ├── theme.py                was _cli_theme.py — palette, tables, progress
│   ├── diagnostics.py          was _cli_diagnostics.py
│   ├── services.py             was _cli_services.py
│   ├── calibration.py          was _cli_calibration.py
│   ├── models.py               was _cli_models.py
│   ├── pi.py                   was _cli_pi.py
│   └── update.py               was _cli_update.py
├── engine/                                                                    [may branch on OS]
│   ├── __init__.py             re-exports today's public surface
│   ├── lock.py                 engine.lock loading, contracts, command building
│   ├── resolve.py              executable lookup, model resolution, receipts
│   ├── status.py               EngineStatus, engine_status(), install facade
│   ├── assets.py               was _engine_assets.py
│   └── install.py              was _engine_install.py
├── models/
│   ├── __init__.py             was models.py — store, artifacts, copies
│   ├── removal.py              was _model_removal.py — the confined cache rules
│   └── verification.py         was _model_verification.py
├── process/                                                                   [may branch on OS]
│   ├── __init__.py             was process.py
│   └── state.py                was _process_state.py
├── calibration/
│   ├── __init__.py             was calibration.py — the public facade
│   ├── types.py  run.py  runner.py  search.py  trial.py  trial_control.py
│   ├── memory.py  record.py  reuse.py  gguf.py  gpu_evidence.py
├── benchmark/
│   ├── __init__.py             was benchmark.py — the benchmark/v1 protocol
│   └── quick.py                was benchmark_quick.py
├── validation/
│   ├── __init__.py             was validation.py
│   └── calibration.py  calibration_v3.py  engine.py  profiles.py
├── tool/                       this installation of bora, as uv sees it
│   ├── __init__.py
│   ├── handoff.py              was _tool_handoff.py
│   ├── helper.py               was _tool_helper.py
│   ├── update.py               was update.py
│   └── uninstall.py            was uninstall.py
└── tui/                        Part B only                                     [terminal.py: OS]
```

Rules this move obeys:

1. **Public import paths do not change.** `calibration.py` → `calibration/__init__.py` keeps
   `from bora_workbench.calibration import …` working, and the same holds for `engine`, `models`,
   `process`, `benchmark`, and `validation`. The `_`-prefixed modules are private and their imports
   are rewritten in the same commit (the highest fan-in are `_calibration_types` at 17 sites and
   `_calibration_record` at 12).
2. **Every `__init__.py` is either the module it replaces or a re-export.** No package gets a
   `__init__.py` that is half facade and half implementation.
3. **`cli/__main__.py` is required, not optional.** `scripts/verify_wheel.py` runs
   `python -m bora_workbench.cli` four times; a package without `__main__.py` breaks wheel
   verification. It also becomes the front end's handoff target (B.5), which is a convergence worth
   noticing rather than a coincidence.
4. **Four modules stay flat**, and the reason is the same rule that motivates the move: `paths.py`,
   `config.py`, `hardware.py`, and `profiles.py` are single coherent modules with no satellites, and
   wrapping each in a one-file package would be ceremony.
5. **`pi_link.py` stays flat too, deliberately.** An `integrations/` package would be an extension
   point with one member, and D-081/D-082 state that no other agent is supported;
   `AGENTS.md:95-98` forbids exactly that kind of speculative structure.
6. **`tool/` is named for what it manages, not for how it is spelled at the CLI.** The area is about
   *the uv tool installation* — `inspect_tool_installation`, `uv tool uninstall` — while the command
   group is `self` because that is what reads best in a terminal. The mismatch is one sentence in
   specification 4.1, and it is a better outcome than a package literally named `self`.
7. **`git mv` only in A3.** No edits inside moved files beyond import lines and the module docstring
   where it names its own filename. The `engine/` split, which does move code between files, is a
   separate step (A4) precisely so that A3's diff can be read as pure motion.
8. **The normative tables move with the tree.** Specification 4.1 and 4.2, `docs/architecture.md`,
   and `docs/development.md` are updated in the same commit. A layout change that leaves the
   normative table describing the old tree is a specification violation, not a cosmetic lag.

**Honest cost:** the file count rises from 45 to about 51 (six `__init__.py`, `__main__.py`,
`snapshot.py`, and the `engine/` split, minus nothing). The number of *things a reader holds in their
head* falls from 45 to 8. That is the trade, and it is the right one — but it should be stated in the
commit body rather than discovered by whoever runs `ls`.

**Tests mirror the tree** in the same step, `tests/cli/`, `tests/calibration/`, `tests/engine/`, and
so on, with an `__init__.py` in each because `tests/` is already a package. `tests/fakes/` and the
five `*_fixtures.py` modules stay where they are: they are shared by every area.

## A.7 The steps

### A1 — Anchor this plan and answer the six open questions

- **Goal.** Give the work a normative entry, so this file is the detail of an authorized perimeter
  rather than a side plan (specification 6.2).
- **Files.** `IMPLEMENTATION_SPEC.md`, `TUI.md`.
- **Change.**
  1. Section 3: add the decisions of Appendix A after D-082 (`:274`), before the closing line
     (`:276`). Match the density of the existing entries — reasons included, one paragraph each.
  2. Section 8: add `### Backlog D — Interactive front end` after Backlog C ends (`:794`) and before
     `### Local 0.2.0 finalization` (`:796`). A few paragraphs: what it is, the handoff constraint,
     the phases by name, the two file pointers. **Do not copy Part B into it**; two roadmaps that
     must agree eventually stop agreeing.
  3. Section 0: add the `0.4.0` scope line to the tracker, and section 1.3 gains the `0.4`
     boundary paragraph.
  4. Amend D-077 (`:268`), which left the disposition of `TUI.md` open, with one sentence: the
     question is answered and the file stays as the design record.
  5. Apply the `TUI.md` errata of Appendix B.
- **Decision.** D-083…D-088 (Appendix A). **A decision entry records what the maintainer decided**,
  so Appendix A needs their assent before this step is written. Until then it is a recommendation and
  this whole file waits on it.
- **Verify.** `pytest`; `bora validate`; `TUI.md` no longer claims to be written against `0.2.1`;
  its screen→command table and the target surface of A.3 name the same commands.
- **Done when.** The specification names this file, and `TUI.md` describes a surface that exists.

### A2 — Make the readability limits deliberate defaults

- **Goal.** Stop a mechanical ceiling from forcing designs worse than the code it rejects, without
  losing the signal that the ceiling exists.
- **Files.** `tests/test_code_quality.py`, `AGENTS.md`, `docs/development.md`.
- **Change.**
  - Three module-level maps, each from a location to the reason it is accepted:

    ```python
    _ACCEPTED_FILE_LENGTH: dict[str, str] = {}       # "src/pkg/module.py"
    _ACCEPTED_FUNCTION_LENGTH: dict[str, str] = {}   # "src/pkg/module.py::name"
    _ACCEPTED_PARAMETERS: dict[str, str] = {}        # "src/pkg/module.py::name"
    ```

    Each size test then fails on **unregistered** breaches — and also fails on an entry that no
    longer corresponds to a real breach, so the list cannot rot into a permanent exemption. Keys use
    forward slashes so the tests behave identically on both platforms.
  - **Nesting stays a hard maximum** and the docstring rule stays absolute. Nesting always has a
    mechanical fix — extract a helper, invert a condition — so exceeding it is never the honest
    answer, and a docstring is not a design trade-off.
  - `AGENTS.md:73-85`: the first three limits become defaults. State the test: exceed one
    deliberately when splitting would scatter an area of competence or hide a published interface,
    and register it with its reason. The existing exemptions for fixtures and declarative content are
    unchanged.
  - `docs/development.md:99-101`: mirror the wording.
  - **No change under `src/`.** The limits widen; nothing moves.
- **Decision.** D-084.
- **Verify.** Add a throwaway four-parameter function → the test fails. Register it → it passes.
  Delete the function but keep the entry → it fails again.
- **Done when.** The three maps are empty, the suite is green, and the three documents agree.

### A3 — Move the tree into packages

- **Goal.** Turn a 45-file listing into eight named areas, changing no behavior.
- **Files.** every module under `src/bora_workbench/` except `resources/`; every test that imports a
  private module; `IMPLEMENTATION_SPEC.md` (4.1, 4.2), `docs/architecture.md`,
  `docs/development.md`.
- **Change.** The tree of A.6, by `git mv`, one area at a time inside the one commit. Then:
  - rewrite import lines only; `ruff check --fix` settles the ordering (`I` is enabled) and
    `ruff format` settles the layout;
  - add `cli/__init__.py` re-exporting `app`, and `cli/__main__.py` carrying the
    `if __name__ == "__main__": app()` that `cli.py:239-240` has today;
  - fix the module docstrings that name their own file or their siblings;
  - rewrite the module table of specification 4.1 to the new tree, keeping the responsibility column
    verbatim wherever the responsibility did not change, and extend the OS-branching sentence
    (`:303`) to name `paths.py`, `process/`, `hardware.py`, `engine/`;
  - update specification 4.2, `docs/architecture.md:38-63`, and the repository-structure section of
    `docs/development.md`;
  - mirror `tests/` onto the same tree.
- **Decision.** D-086.
- **Verify.** `pytest` green with no test edited except its import lines and its location;
  `uv build` plus `scripts/verify_wheel.py` green, which is what proves `__main__.py` and the wheel's
  resource layout; `git diff -M --stat` shows renames, not rewrites; `bora doctor` output
  byte-identical.
- **Done when.** `ls src/bora_workbench` prints eight directories and seven files, and every
  public import path is what it was.

> **The trap in this step.** `python -m bora_workbench.cli` is used four times by
> `scripts/verify_wheel.py:50-69` and stops working the moment `cli.py` becomes a package. Add
> `cli/__main__.py` in the same commit, and run the wheel verification *inside* this step rather
> than after it.

### A4 — Split `engine/` by responsibility

- **Goal.** Give the largest area room to be read and to grow. This is the one step of Part A that
  moves code between files.
- **Files.** `src/bora_workbench/engine/*`, plus the tests that import private helpers.
- **Change.** `engine.py` (592 of 600 lines) becomes `lock.py`, `resolve.py`, and `status.py` along
  the seams that already exist in its own imports: lock loading and command building; executable and
  model resolution with the D-076 receipt; status, differences, and the install facade.
  `engine/__init__.py` re-exports exactly the names imported elsewhere today — `Backend`,
  `EngineError`, `EngineStatus`, `InstallProgressEvent`, `InstallResult`, `JsonObject`,
  `ModelRequest`, `build_command`, `engine_status`, `install_engine`, `load_engine_lock`, `locate`,
  `resolve_model` — with `__all__`.
- **Decision.** — (it records no new rule; it applies `AGENTS.md:78-80`).
- **Verify.** `pytest`; no import outside `engine/` mentions a submodule; `bora engine status` and
  `bora doctor` byte-identical.
- **Done when.** No file in `engine/` is above 400 lines and the public surface is unchanged.
- **Skippable.** If the maintainer wants Part A strictly mechanical, drop this step: nothing else
  depends on it. The cost of dropping it is that the engine area stays eight lines from its ceiling.

### A5 — Name the program `bora`

- **Goal.** Stop printing a command name that is not installed.
- **Files.** `cli/app.py`.
- **Change.** `name="bora-workbench"` → `name="bora"` (`cli.py:33`). Leave every other occurrence
  alone: the `doctor` table title and the four public roots name the *distribution*, which is
  correct, and `tests/test_cli.py:100` asserts on that title.
- **Decision.** — (restores the contract of `pyproject.toml:22-23`).
- **Verify.** `bora --help` and an unknown command both print `bora` in the usage line.
- **Done when.** No usage or error line names `bora-workbench`.

### A6 — Reorganize the command surface

- **Goal.** Ship the surface of A.3: two groups added, four paths renamed, six help panels, one
  moved-name notice, and the `pi` overload removed.
- **Files.** `cli/app.py`, `cli/pi.py`, `cli/models.py`, `cli/update.py`, `docs/commands.md`,
  `README.md`, `docs/installation.md`, `docs/operations.md`, `tests/test_cli*.py`.
- **Change.**
  - two new `typer.Typer` groups, `model` and `self`, mounted with `add_typer`; the four command
    bodies move under them unchanged — they still call the same `run_*` functions with the same
    arguments;
  - `pi` loses `invoke_without_command=True`; `pi connect` becomes a real command carrying
    `--dry-run` and `--install`. `PiOptions.print_only` is renamed to `is_dry_run` for the same
    reason the flag was: the field is the flag (`_cli_pi.py:66-71`);
  - `update --check` → `self update --dry-run`; `UpdateOptions.is_check_only` follows;
  - `rich_help_panel` on every command and group, with the six titles of A.3 — **the same six words
    the front end's rail uses**;
  - the moved-name notice: a `TyperGroup` subclass on `app`, plus the two refused options on the
    `pi` group. Both carry the removal date in their docstring: **removed in `0.5.0`**;
  - `docs/commands.md` is reorganized under the same six headings, its summary table gains the rows
    for `pi remove` and `pi uninstall` that exist only in the body today, and it gains the two tables
    of A.4 and A.5 (what moved; the flag vocabulary);
  - the eleven command occurrences in `README.md`, the seven in `docs/installation.md`, and the
    fourteen in `docs/operations.md` are updated in this commit.
- **Decision.** D-085.
- **Verify.** `bora --help` prints six panels; `bora model pull --help`, `bora self update --help`,
  `bora pi connect --help` exist; `bora rm` exits **2** naming `bora model rm`; `bora pi --print`
  exits **2** naming `bora pi connect --dry-run`; `bora pi --install remove` exits **2** instead of
  discarding a flag (**D3 closed**); every unchanged command behaves exactly as before.
- **Done when.** No flag combination is accepted and then dropped, and no documented path is
  unreachable.

### A7 — Declare the three `calibrate` options

- **Goal.** Make the whole of `calibrate` visible to `--help`, to shell completion, and to anything
  that composes a command line — including the front end.
- **Files.** `cli/app.py`, `cli/calibration.py`, `docs/commands.md`,
  `tests/test_cli_calibration.py`, `tests/test_code_quality.py`.
- **Change.**
  - `cli/app.py`: delete `_CALIBRATION_EPILOG` (`cli.py:50-55`); drop `context: typer.Context`,
    `context_settings={"allow_extra_args": …, "ignore_unknown_options": …}`, and `epilog=`
    (`:187-208`); declare `no_activate`, `activate`, and `target_ctx` as ordinary Typer options;
    build `CalibrationCliInput` directly and hand it to `run_calibrate`.
  - The `try`/`except CalibrationError` around parsing (`:203-207`) disappears with the imports of
    `parse_calibration_input` and `CalibrationError`. This is safe because validation never happened
    at parse time: `_validate` runs inside `_run` (`_cli_calibration.py:462`) and `run_calibrate`
    already maps `CalibrationError` to exit 2 (`:499-501`).
  - `cli/calibration.py`: delete `_target_ctx` (`:86-93`) and `parse_calibration_input` (`:96-123`).
    `CalibrationCliInput`, `_preference`, `_validate_target_ctx`, and `_validate` are untouched — the
    mutual-exclusion rules do not change.
  - one `_ACCEPTED_PARAMETERS` entry for `cli/app.py::calibrate`, reading roughly *a Typer command's
    parameters are the published CLI surface, not an internal interface*.
  - `docs/commands.md:373-375` — the paragraph apologising for the epilog — is deleted. The option
    table at `:343-349` already documents all five.
  - `tests/test_cli_calibration.py`: six call sites pass the extras as raw arguments; they pass them
    as options instead.
- **Decision.** D-085 (same decision as A6; separate commit).
- **Verify.** `calibrate --help` lists five options in the generated table and has no epilog;
  `--target-ctx=65536` is accepted (**it is not, today**); `--activate --target-ctx 65536` exits 2;
  `--pippo` exits 2; `--target-ctx abc` exits 2.
- **Done when.** No option of `calibrate` is reachable that `--help` does not name.

> The exit-code contract holds across this change, which is why it is safe: every input that exits 2
> today still exits 2, and only the *wording* moves from a bespoke message to Typer's. That is the
> trade — a slightly less specific error, for an option surface that is discoverable, completable,
> and composable.

### A8 — One rule for the two streams

- **Goal.** Make the choice of stream predictable, so redirection means something.
- **Files.** `cli/diagnostics.py`, `docs/commands.md`.
- **Change.** State the rule in `docs/commands.md`: **stdout carries the report; stderr carries what
  explains a non-zero exit or a degradation.** Then fix `_print_status` (`_cli_diagnostics.py:237-242`),
  which splits one list of engine differences across both streams inside a single loop: the whole
  list goes to one stream, chosen once, by whether the status is blocking.
- **Decision.** —
- **Verify.** `bora engine status > out.txt` on a machine with no engine leaves a complete, readable
  report in the file; with an incompatible engine, the file holds the table and the terminal holds
  every difference.
- **Done when.** No single loop writes to two streams.

### A9 — Render `doctor` from a structured snapshot

- **Goal.** Separate collecting this machine's state from printing it — so the state can be read by
  something that is not a console, and so every failure inside the collection maps to its
  contractual exit code.
- **Files.** new `src/bora_workbench/snapshot.py`, `cli/diagnostics.py`, new
  `tests/test_snapshot.py`.
- **Change.**
  - `snapshot.py` holds one frozen, slotted dataclass and one collector:

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

    def collect(version: str) -> Snapshot: ...
    ```

    Dataclass fields are not function parameters, so the A2 limits are untouched: `collect` takes
    one argument and `run_doctor` keeps its three.
  - `collect` absorbs everything `run_doctor` computes inline today, **including the four unguarded
    calls of D4**. `run_doctor` keeps its signature and becomes collect → render → map exit code,
    with one `try` around the collection. `_doctor_table` and `_record_line` take the snapshot.
  - `run_validate` (`_cli_diagnostics.py:317-322`) gets the guard it never had.
  - `tests/test_snapshot.py` exercises the collector **with no console at all**, which is half the
    value of the refactor.
- **Decision.** D-087.
- **Verify.** Capture `bora doctor` stdout before and after: **byte-identical**. Then a fake raising
  `EngineError` from `engine_status()` produces exit 1 with a message on stderr, not a traceback.
- **Done when.** `doctor` prints what it printed before, and nothing it needs is computed while it
  prints.

> **Keep the collection order.** Configuration, hardware, content validation, records, engine status,
> and the four public roots **last**. Today the roots are resolved during rendering
> (`_cli_diagnostics.py:354-355`) and the comment above them (`:351-353`) says why: resolving a public
> root is the only step there that can fail, and *which error a reader meets first is part of the
> behavior* (specification 5.11). Collecting them earlier silently reorders that. This is the one
> trap in the step.

> **Scope guard.** The snapshot covers *exactly* what `doctor` renders today. Not services, not the
> presence of the model, not anything a screen might want later: `AGENTS.md:23-24` forbids code that
> anticipates a later milestone, and the front end composes this snapshot with the
> `across_service_roots` sweep `status` already uses (`_cli_services.py:208-224`) without a line of
> new core code.

### A10 — Make the documented surface and the real surface unable to drift

- **Goal.** Stop the surface and its documentation from diverging silently, now that both were just
  rewritten.
- **Files.** new `tests/test_docs_commands.py`.
- **Change.** Walk `typer.main.get_command(app)`, collect every command path and every option string,
  and assert each appears somewhere in `docs/commands.md`. Search by presence rather than by
  heading, because `coding`, `studio`, and `vstudio` share one section. Exclude `--help`, documented
  once at `docs/commands.md:9`. Offline, deterministic, host-independent. Assert the moved-name map
  too: every old name in it must appear in the "what moved" table.
- **Decision.** —
- **Verify.** Delete a command row from `docs/commands.md` → the test fails. Add a flag without
  documenting it → the test fails.
- **Done when.** Documentation kept in sync by discipline alone is no longer the mechanism.

## A.8 What Part A must not become

Not a chance to "improve" an API, merge modules, introduce a `core/` layer, add `Protocol`s, or write
the front end's data path ahead of the front end. **`compose(state) -> argv` is not written in
Part A**: it would have no caller, and `AGENTS.md:95-98` forbids unused extension points. What makes
this CLI composable is A7 — a parser that names every option it accepts — not a helper waiting for a
user.

---

# Part B — The front end

`TUI.md` is the design record: the banner, the gust, the sea, the palette, the mockups, and the
degradation ladder are good and this file does not restate them. What follows is the part `TUI.md`
does not cover — how it is built, in what order, against which vocabulary, and what "excellent"
means precisely enough to be checked.

## B.0 What "excellent" means here

Ten commitments. Each one is testable, and each one is the reason for at least one design decision
below.

- **U1 — The first frame is instant.** The chrome (banner, rail, key bar) needs no data and is
  painted before any collection starts; the detail pane fills in when the snapshot arrives.
  `detect_hardware()` shells out to `nvidia-smi` with a 5-second timeout (specification 5.4), so a
  front end that collects before it paints can look hung on exactly the machine it exists to serve.
  No async, no threads — two synchronous paints, in the order a human reads them.
- **U2 — It always knows the next step, and it is one key away.** A pure function over the snapshot
  produces one suggestion, always correct, never nagging (B.3). This is the single feature that turns
  a dashboard into something a person is glad to open.
- **U3 — The command is always visible, and copyable.** Every screen that can act shows the exact
  argv it will run, in a fixed place, before it runs it (`TUI.md:166-169`). `y` copies it with an
  OSC 52 sequence — no dependency, works over SSH — and the line stays on screen so a terminal that
  ignores OSC 52 loses nothing.
- **U4 — Read is free, act is deliberate, destroy is typed.** Opening it starts no process, creates
  no directory, writes no state, touches no config. Actions need an explicit key; destructive ones
  need a typed word and then still meet the real command's own confirmation.
- **U5 — The words never change.** A record is `active`, `candidate`, `absent`, `incompatible`,
  `stale`, `superseded`, or `insufficient headroom` — the seven states `doctor` already
  distinguishes. The front end must show exactly those words. A "superseded" record is not "old", and
  "insufficient headroom" is not "won't work".
- **U6 — Motion is the bora, then stillness.** Gusts, not a breeze; the header settles after about
  three seconds and returns only while a handoff child is running. It never blocks a keystroke and
  it never encodes a measurement.
- **U7 — Nothing is front-end-only.** Everything reachable here is reachable by typing, and the
  front end's last act for any real operation is to run the command it is showing.
- **U8 — Degrade by layers, never by failure.** Truecolor+UTF-8+motion → 16 colours → no motion →
  ASCII → plain banner → the CLI. Each rung is a supported configuration with a test.
- **U9 — Close the loop.** After every handoff that returns, re-collect and print one line of
  difference: `engine: not installed → b10011 CUDA active`. The CLI cannot do this; it is the front
  end's own contribution.
- **U10 — Honest over comfortable.** It never implies it will do something the project refuses to do.
  It says "bora never downloads weights you did not ask for" on the screen where that matters, gives
  the exact pinned revision, and never offers to write `config.toml`.

## B.1 The four seams

The whole architecture is four connections to code that already exists.

| Seam | What it is | State |
|---|---|---|
| **Snapshot** | the read-only picture, as data | **A9 builds it** |
| **Advice** | `next_step(snapshot) -> Suggestion` — what this machine should do now | B3, pure |
| **Composer** | `compose(state) -> tuple[str, ...]` — the exact argv the CLI would parse | B4, pure |
| **Handoff** | restore the terminal, print the command, run it, return or exit with its code | B4 |

No new event system, no plugins, no adapters. If a job is ever hosted in-process — it should not be —
the port already exists: `RunOptions(progress=…)` takes a `CalibrationProgress`, and both
`cli/calibration.py` and `cli/diagnostics.py` already branch on `console.is_terminal` to choose live
versus line-oriented rendering.

## B.2 What the snapshot does not cover

A9's snapshot is exactly `doctor`'s picture. Two things the front end also shows come from elsewhere,
and neither needs new core code:

- **live services** — `across_service_roots(status_services)` (`cli/services.py:208-224`), the same
  sweep `status` and `bora pi` use;
- **the model on disk** — `locate_copies(lock)` from `models/`, which is what `model rm --dry-run`
  reports.

Refresh policy: on entry, on `r`, and after any handoff returns. **Never on a timer.** A dashboard
that polls `nvidia-smi` in a loop is a dashboard that perturbs what calibration measures.

## B.3 The advice engine

```python
def next_step(snapshot: Snapshot, services: tuple[ServiceState, ...]) -> Suggestion: ...
```

One suggestion, one reason, one command. Deterministic, table-tested, and the first thing the home
screen prints — above the rail, because most sessions should end after reading one line.

| Order | When | Suggestion |
|---:|---|---|
| 1 | packaged content has errors | `bora validate` — the installation itself is wrong |
| 2 | engine absent or incompatible | `bora engine install` |
| 3 | model artifacts missing | `bora model pull` |
| 4 | a managed service is running | open the UI, or `bora stop` |
| 5 | a valid candidate is pending | `bora calibrate --mode <id> --activate` |
| 6 | no active record for any mode | `bora calibrate --mode all` — *the nudge, once* |
| 7 | everything is in place | `bora coding` |

Rule 6 is where tone is decided. `README.md:266-268` is explicit that calibration is *the second
step, not the entry price*, so the wording nudges and never scolds, and never implies the tool is
broken before it: "All three modes start on the verified baseline (ctx 8192, n_cpu_moe 48). That
works — it is not optimized."

## B.4 Composer and handoff

**Handoff, not embedding.** `TUI.md:259-295` argues it in full; the short version is that the run
modes hold the foreground until `Ctrl-C`, calibration runs for hours, `self uninstall` deletes the
installation that would be running the UI, and the exit codes are a contract — and every one of those
problems disappears when the front end's last act is to run the command it is showing and get out of
the way.

Mechanics, identical on both platforms (Windows has no real `exec`):

1. leave the alternate screen and restore the terminal — cursor, colours, mouse, raw mode;
2. print the exact command line, so it stays in the scrollback;
3. restore the default `SIGINT` handler;
4. `subprocess.run(argv, shell=False)` with inherited stdio;
5. **terminal actions** — `coding`, `studio`, `vstudio`, `calibrate`, `self update`,
   `self uninstall` — exit with the child's code and do not come back; **returning actions** —
   `doctor`, `validate`, `engine status`, `engine install`, `model pull`, `model rm`, `status`,
   `stop`, `pi *` — return, re-collect, and print the U9 difference line.

**What to display and what to execute are different strings.** The screen always shows `bora …`,
because that is what a human types. The process always runs
`[sys.executable, "-m", "bora_workbench.cli", *args]`, because that is what works in a development
checkout, inside `uv run`, and when the console script is not on `PATH`. A3 already adds the
`cli/__main__.py` this depends on.

The composer is the only piece worth testing heavily, and it is pure:

```python
def compose(state: ScreenState) -> tuple[str, ...]:
    """Return the exact argv the CLI would parse for this screen state."""
```

Two tests carry the whole design. One enumerates every reachable screen state and asserts the argv.
The other feeds every produced argv to **the real parser** — `typer.main.get_command(app)` plus
`make_context`, which parses without executing anything — and asserts it is accepted. After A7 the
Typer app *is* the parser, so a screen that can compose an invalid command fails the suite offline,
on both platforms.

The wizard's real advantage over the CLI follows from that: `--activate` with `--target-ctx` is an
input error today, reported after the fact. In the wizard it is **unreachable**, with the reason
shown inline. That is a genuine improvement, not a reskin.

## B.5 Screens

The rail is the six panels of A.3. Same words, three places.

| Rail | Shows | Acts (all handoffs) |
|---|---|---|
| **Overview** | the verdict line, engine, model, content, memory, services, the seven record states | the suggestion of B.3 |
| **Run a mode** | the three modes, their sampling, the record or baseline each would use, the API/UI URLs | `coding` / `studio` / `vstudio`, `[f]` adds `--force` with its meaning printed inline |
| **Tune** | per-mode record state, stored `ctx` and `n_cpu_moe`, reserves, record path | the four-step wizard → `calibrate …`; `[a]` on a candidate row → `--activate` |
| **Setup** | engine release/backend/lock match; the model artifacts, sizes, and where each copy lives | `engine install`, `model pull`, `model rm` (`[d]` previews with `--dry-run`) |
| **Connect** | whether pi is on `PATH`, the provider entry, and **which of the three sources** the context window would come from | `pi connect`, `pi remove`, `pi uninstall` |
| **This installation** | version, published version, the four roots, what `uninstall` deletes and what it does not | `self update`; `self uninstall` behind a typed word |

Two screens deserve their exact wording:

**Setup, when weights are missing.** This is where a naive wizard lies. State the boundary on the
screen where the user meets it — `bora model pull` downloads the pinned artifacts, and nothing else
is ever fetched — and show the revision, filenames, and byte sizes from the lock, so the project's
most surprising constraint becomes its clearest moment.

**This installation.** It lists the four roots, states that the model store is inside the data root
and goes with it, states that the Hugging Face cache is asked about separately and defaults to no,
and requires the word `remove` to be typed. Then it hands off to `bora self uninstall`, which asks
its own confirmation. Two deliberate acts for the only irreversible command in the tool — and because
it is a handoff, the front end is already gone before uv is asked to delete the installation it was
running from.

**Settings are read-only, permanently.** Show the resolved value, its source (`environment` /
`config.toml` / `default`), the file path, and the environment variable names. `[o]` opens the file in
`$EDITOR`. The user's editor writes that file; bora never does (`README.md:316-318`, specification
5.12).

## B.6 Keymap

| Key | Action |
|---|---|
| `↑ ↓` / `k j` | move within the focused list |
| `← →` / `h l` | move between rail and detail |
| `Enter` | open, or confirm the focused item |
| `Esc` | back; at the root, quit |
| `r` | refresh the snapshot |
| `y` | copy the visible command (OSC 52) |
| `?` | help overlay with the full keymap |
| `q` / `Ctrl-Q` | quit |

Rules that avoid the classic accidents: no destructive action on a single letter at the root;
confirmation modals default to **No**; `y`/`n` answer a modal only while one is open, and `y` means
*copy* only while none is; no key that starts a job is adjacent to a navigation key.

## B.7 Motion, palette, identity

Unchanged from `TUI.md` sections 4.1–4.6, with its budget kept as a hard rule: **≤ 12 fps**, idle CPU
**≤ ~2 %** of one core *measured, not assumed*, motion only on a focused home screen, off entirely
under `BORA_TUI_MOTION=off`, `NO_COLOR`, `TERM=dumb`, or `--plain`, and **never** in the path of
`coding`, `studio`, `vstudio`, `calibrate`, `engine install`, `doctor`, `status`, `stop`, `validate`,
or `self uninstall`. A splash on every invocation would be charming twice and irritating forever.

The palette extends `cli/theme.py:25-34` and does not contradict it: success, warning, error, and
heading reuse `STYLE_*` verbatim, wind takes `bold white` / `cyan` / `dim cyan`, sea takes `blue` /
`dim blue`. Built-in Rich style names only, so styles stay valid on a theme-free console. Colour never
carries meaning alone. No emoji, ever: variable-width glyphs wrap lines and split tokens, which is
why the existing theme banned them.

## B.8 Degradation and access

| Environment | Behavior |
|---|---|
| Windows Terminal, `gnome-terminal`, `kitty`, `alacritty`, VS Code | full; debounce redraws on resize |
| legacy `conhost.exe` with a raster font | detected → ASCII glyph set, no box drawing |
| `tmux` / `screen`, SSH | assume the lowest capability reported; 256 colours unless `COLORTERM` says more |
| `NO_COLOR`, `TERM=dumb`, `--plain` | no colour, no motion, plain banner |
| no TTY (pipe, CI, redirect) | **no front end**: one line of explanation, exit 2 |

Capability detection is one small named helper in `tui/terminal.py`, not `if os.name` scattered
through screens. That module is the front end's only OS branch and specification 4.1 names it as
such in A1 — terminal capability is not platform *logic*, but pretending it is not platform-specific
would be worse than declaring it.

`docs/tui.md` states plainly that alternate-screen interfaces are hostile to screen readers and that
**the CLI remains the complete, accessible path**. That sentence is part of the feature, not a
disclaimer bolted on.

## B.9 Performance budget

| Budget | Value | Why |
|---|---|---|
| first paint | < 150 ms | before any collection; chrome only (U1) |
| full snapshot | < 1.5 s typical, 5 s worst case | bounded by the `nvidia-smi` timeout of specification 5.4 |
| idle CPU | ≤ ~2 % of one core | measured on both reference machines |
| frame rate | ≤ 12 fps, motion only | it is a terminal |
| key latency | never blocked by a frame | motion yields to input, always |
| `bora --version` | **not one millisecond slower** | the front end is imported only when its command runs |

## B.10 Testing

- `compose()` — table-driven over every reachable state.
- every composed argv accepted by the real parser, through `make_context`, executing nothing.
- `next_step()` — a truth table over the seven snapshot shapes.
- the snapshot collector — with fakes, no console.
- the capability ladder — a pure function from a capability tuple to a render mode.
- motion — pure functions of `(t, width, height, seed)` with a frozen clock and a seeded PRNG.
- `tui/` is walked by `tests/test_code_quality.py` the moment it exists: 600 lines, 40 lines,
  3 parameters, 3 nesting levels, docstrings everywhere, exceptions registered under A2.
- **No pixel snapshots.** Keep the logic out of the UI and there is nothing brittle left to test.

## B.11 The steps

| | Step | Content | Useful if you stop here |
|---|---|---|---|
| **B1** | `bora tui`, read-only | the command, the TTY refusal, `tui/terminal.py`, the banner, one static frame rendering the A9 snapshot, `r` and `q`. **Rich only.** | the identity plus a genuinely useful overview |
| **B2** | Motion | gust and sea as pure functions, the budget, the settle, every kill switch | the identity, complete |
| **B3** | Navigation and advice | rail, detail pane, help overlay, the verdict line and `next_step()` | the reason to open it |
| **B4** | Composer and handoff | `compose()`, the handoff, the U9 difference line, OSC 52 copy | the whole concept |
| **B5** | Run, Setup, Connect screens | the three simple action screens | daily use |
| **B6** | Tune | the four-step calibration wizard and the records pane | the strongest screen in the design |
| **B7** | This installation | `self update`, and the danger zone behind a typed word | first-run and last-run |
| **B8** | Polish and docs | empty states, `$EDITOR`, `docs/tui.md`, the acceptance run of C.1 | — |

**The dependency decision happens between B2 and B3**, with B1 and B2 as evidence. Rich is already a
dependency and gives layout, tables, `Live`, and colour but no keyboard handling. Textual is by the
same author, builds on Rich, is pure Python, works on Windows Terminal and POSIX, and ships a
headless test pilot — at the cost of a real dependency addition and a transitive tree to review in a
project whose identity is a verified supply chain. Deciding it **after** two phases of hand-rolled
input, following `AGENTS.md:163-174` and amending D-003, is the difference between deciding with
evidence and deciding by taste. If it is refused, B1–B2 still stand on their own.

## B.12 Contracts the front end must not break

A review checklist, not aspirations:

1. importing the package still performs no I/O; `tui/` is imported only when its command runs;
2. exit codes stay `0 / 1 / 2 / 130`, produced by the same code as today — the front end adds none;
3. no TTY, no front end;
4. `config.toml` is never written;
5. no new network access, no telemetry, no port; record *paths* are displayed, record *contents* are
   never shipped anywhere;
6. preflights and confirmations are never re-implemented, pre-answered, suppressed, or auto-`--yes`ed;
7. everything reachable here is reachable by typing;
8. opening it starts no process, creates no directory, writes no state;
9. platform branching stays in `paths`, `process/`, `hardware`, `engine/`, and the declared
   `tui/terminal.py`;
10. no candidate is ever activated on the maintainer's behalf, from any screen.

## B.13 Where the idea is still weak

Kept from `TUI.md:670-733`, because a plan that drops its own objections is a brochure:

- **Opportunity cost is the strongest objection.** Specification section 0 still lists open `0.2`
  work: the Windows trial adapter, the real `update`/`pull`/`rm`/`pi` runs, the cross-platform
  release CI. A front end is a new surface on a base with open items. Part A is worth doing either
  way; Part B should start only when the maintainer decides those items no longer block it — and "not
  yet" is a legitimate answer for a long time.
- **A UI is the opposite of reproducible**, and reproducibility is this project's thesis. The answer
  is U3 and U7: a front end that teaches the CLI is defensible; one that replaces it is not.
- **Two front ends drift.** The answer is that the front end owns no rules — snapshot in, argv out —
  and that one test proves every argv it can emit is accepted by the real parser.
- **Animation is a taste that fades.** The answer is the budget, the settle, the kill switches, and
  never putting motion in the command path.
- **Scope creep has a natural home in a UI.** Model pickers, flag editors, profile builders: none of
  them become reachable because a screen has room. `README.md:37-43` draws that line already.

---

# Part C — Release `0.4.0`

## C.1 Definition of done

`0.4.0` is taken only when **all** of these hold. Anything unmet is either fixed or written down as a
limitation — never described as passed.

**Part A**

- [ ] every step A1–A10 committed, each with its own green suite;
- [ ] `bora --help` prints six panels; all seventeen paths behave exactly as `0.3.2` did;
- [ ] the four old names exit 2 naming their replacement;
- [ ] `bora doctor` stdout is byte-identical to `0.3.2` on the same machine;
- [ ] `ls src/bora_workbench` shows eight directories and seven files;
- [ ] `docs/commands.md` matches the parsed surface, enforced by `tests/test_docs_commands.py`.

**Part B**

- [ ] `bora tui` starts with no side effects: no process, no directory, no state, no config write —
      asserted by a test, not by inspection;
- [ ] it exits cleanly restoring the terminal, including after `Ctrl-C` and after a handoff;
- [ ] it renders correctly at 80×24, 120×40, and 60×20; degrades to ASCII without UTF-8; prints one
      line and exits 2 without a TTY;
- [ ] every screen action composes an argv the real parser accepts, proven offline;
- [ ] idle CPU measured under budget on both reference machines, with the number recorded;
- [ ] `bora --version` is no slower than in `0.3.2`;
- [ ] **manual**: on Windows Terminal and on legacy `conhost`, and on one Ubuntu terminal, open it,
      navigate every screen, hand off one returning action and one terminal action, and confirm the
      terminal is intact afterwards.

**Both**

- [ ] `uv sync --frozen`, `ruff check`, `ruff format --check`, `pytest`, `bora validate`;
- [ ] `uv build`, `scripts/verify_wheel.py`, `scripts/verify_uninstall.py`;
- [ ] `docs/tui.md` exists and every other page still works, because nothing became front-end-only.

## C.2 The version bump

Eleven files carry `0.3.2` today. Change them in one commit, at the end, never earlier:

| File | What |
|---|---|
| `pyproject.toml` | `version = "0.4.0"` |
| `src/bora_workbench/cli/app.py` | the `package_version()` source-checkout fallback |
| `scripts/verify_wheel.py` | the installed-version assertion |
| `tests/test_cli.py` | `test_version` |
| `CHANGELOG.md` | a new `## [0.4.0]` section: Added / Changed / Removed, in the existing voice |
| `README.md` | badge, both installation blocks, the status paragraph |
| `docs/README.md` | current status and preceding public release |
| `docs/installation.md` | the pinned version in the install commands |
| `docs/operations.md` | version-bearing examples |
| `docs/releasing.md` | a new `### Release 0.4.0` section describing what shipped and what stayed a limitation |
| `IMPLEMENTATION_SPEC.md` | section 0 tracker, section 1.3 boundary |

The changelog needs three honest headings: **Added** (`bora tui`, `bora model`, `bora self`,
`bora pi connect`, the declared `calibrate` options, the structured snapshot), **Changed** (the tree,
the panels, the flag vocabulary, the stream rule), **Removed** (the epilog parser; the old spellings,
with the note that the moved-name notice goes in `0.5.0`).

## C.3 The procedure

Exactly `docs/releasing.md:26-58`: clean checkout, required uv, the five frozen checks, `dist/`
deleted, `uv build`, `verify_wheel.py`, `verify_uninstall.py`, then the artifact checks. Any change
made after the build invalidates the artifacts: remove `dist/`, repeat every check, rebuild.

Then, and only with explicit authorization in the session where each happens: the commit; the push;
the tag `v0.4.0`; and the GitHub Release created **from that tag's green release workflow's exact
bundle**. Distribution stays GitHub Releases only (D-070); no registry, no rebuild of a published
artifact.

## C.4 What must not be claimed

- not a passed Gate — calibration coverage stays `GATE-PARTIAL`;
- no local candidate is activated by this release, or by any screen in it;
- manual checks that were not run are listed as limitations, with the platform named;
- the front end is not described as an improvement over the CLI for accessibility, because it is not.

---

# Appendix A — Decisions to record in A1

Proposed text is one paragraph each, in the voice of the existing table. Numbers are indicative.

| | Subject |
|---|---|
| **D-083** | `0.4.0` scope: the reorganized command surface, the reorganized package tree, and the interactive front end are released together as `0.4.0`. Records the six answers below. Nothing about the engine, model, calibration protocol, record format, or `command_contract_sha256` changes, so every existing `calibration-record/v6` stays valid. |
| **D-084** | The file, function, and parameter limits become registered defaults with a reason; nesting and docstrings stay absolute. Records why: the mechanical ceiling hid a published CLI interface in order to protect an internal one. |
| **D-085** | The command surface: `model` and `self` groups, `pi connect`, the six help panels, `--dry-run` as the single "show and stop" spelling, the three declared `calibrate` options, the moved-name notice and its removal in `0.5.0`. Names the licence: `0.3` carries no interface stability guarantee, and no command string is checksum-bound. |
| **D-086** | The package tree: eight areas, public import paths preserved, `cli/__main__.py`, tests mirrored, specification 4.1/4.2 rewritten, `tui/terminal.py` added to the modules allowed to branch on the operating system. |
| **D-087** | `doctor` renders a structured snapshot instead of computing while it prints; `validate` and the four unguarded calls gain the guard that specification 5.11 already required. |
| **D-088** | The interactive front end as Backlog D: `bora tui`, **handoff not embedding**, read-only settings, bare `bora` unchanged, Rich for phases 1–2, and the dependency question deferred to the phase-3 decision point with phases 1–2 as evidence. |

**The six questions of `TUI.md:787-794`, answered:**

| | Question | Answer |
|---|---|---|
| **Q1** | Is the package reorganization approved as an independent step? | **Yes, and first** — A3/A4, ahead of the front end and worth doing even if the front end is never built. |
| **Q2** | Is an interactive front end accepted at all? | **Yes**, as Backlog D, released in `0.4.0` when Part C's criteria are met. |
| **Q3** | Handoff or embedded execution? | **Handoff.** It leaves exit codes, signal handling, and process lifetime with the code that already owns them. |
| **Q4** | Rich only, or is `textual` approved? | **Deferred**, to the decision point between B2 and B3, with evidence. D-003 unchanged for now. |
| **Q5** | Does bare `bora` stay `no_args_is_help`? | **Yes.** The front end ships as `bora tui`. Changing what a bare invocation does is a contract change with no upside. |
| **Q6** | Is the settings pane read-only forever? | **Read-only.** It follows a rule that is already normative: the launcher never rewrites `config.toml`. |

# Appendix B — `TUI.md` errata, applied by A1

| Where | Now says | Should say |
|---|---|---|
| status block `:1-14` | proposal written against `0.2.1`, disposition open | design record for Backlog D, written against `0.3.2`, pointing at this file for the steps |
| `:49-60` | 26 modules, 21 `_`-prefixed, five areas | 45 modules, 29 `_`-prefixed, eight areas; the target tree is A.6 of this file |
| Part I `:45-156` | "code layout first", with its own tree | superseded by A.6 and A3/A4 |
| `:186-196` | screen→command table | the six panels of A.3, including `model pull`/`model rm`, `pi connect`, `self update`/`self uninstall`, and `engine install --no-model` |
| `:40-41` | a quotation in Italian | English (`AGENTS.md:46-47`) |
| `:334`, `:469` and mockups | `workbench 0.2.1` | the version the release carries |

# Appendix C — Verification

After **every** step (`AGENTS.md:176-198`):

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
```

After A3, A4, and before the release, additionally:

```bash
rm -rf dist
uv build
uv run --frozen python scripts/verify_wheel.py
uv run --frozen python scripts/verify_uninstall.py
```

Three per-step checks carry most of the weight:

- **A3** — `git diff -M --stat` shows renames, and the wheel verification passes. A move that changed
  a byte inside a file is not a move.
- **A9** — `bora doctor` stdout byte-identical before and after. A refactor that changes output is
  not a refactor.
- **B4** — every argv the composer can emit is accepted by the real parser. A screen that can produce
  a command the CLI rejects is a screen that lies.

If a tool or a platform is unavailable, report that limitation. Do not claim the check passed.

# Appendix D — Considered and rejected

- **A third level, `bora service status` / `bora service stop`.** Rejected: `status` and `stop` are
  the second and third most typed commands, and the object is already unambiguous — there is only one
  kind of managed service.
- **`bora run coding` with `bora coding` kept as a shortcut.** Rejected: two spellings of the most
  used command, forever, to gain a grouping that `rich_help_panel` already provides for free.
- **Renaming `vstudio`.** Rejected: mode ids are packaged content bound into every
  `calibration-record/v6`. Renaming one invalidates records for cosmetics.
- **Renaming the launch `--force` to `--skip-memory-gate`.** Rejected: more honest, more typing on
  the one escape hatch needed under pressure. The two meanings get a documented row each instead, and
  the front end prints the meaning inline.
- **Deprecated aliases that still work.** Rejected: a second spelling to keep correct forever, and a
  second thing a front end could compose. A notice that exits 2 teaches the new name once
  (`AGENTS.md:132-133`).
- **`bora model status`, `bora records show`.** Rejected: new capability. `doctor` is the aggregate
  view, and Part A adds nothing a user could not do in `0.3.2`.
- **`doctor --json` as the front end's data source.** Rejected: it would make a public output
  contract out of an internal need. The snapshot is an in-process API; a JSON contract is a separate
  decision with its own compatibility obligations.
- **Reading the CLI's stdout to build the dashboard.** Rejected: scraping your own tool is how two
  front ends drift apart.
- **A front end that runs everything in-process.** Rejected: `TUI.md:259-295` and B.4.
- **A web UI.** Rejected: it would open a port, and this project's security posture is built on
  `127.0.0.1`-only services with a verified lifecycle.
