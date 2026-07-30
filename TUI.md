# bora TUI — implemented design record

> **Status: implemented current design.** D-083–D-092 in `IMPLEMENTATION_SPEC.md` authorize the
> reduced interactive-front-end milestone and the current unified presentation. `TUI_PLAN.md`
> retains the step-by-step execution and release checks. If this document, that plan, and the
> specification disagree, the specification wins; user operation is documented in `docs/tui.md`.

---

## 1. Product statement

Bare `bora` is a read-mostly terminal dashboard, exact command composer, and teaching surface for
the current explicit-command CLI. The old `bora tui` entry no longer exists, and the workbench is
not a second launcher runtime.

The front end exists to answer three questions quickly:

1. What is installed, configured, running, and calibrated on this machine?
2. What is the one truthful next step?
3. Which exact `bora ...` command performs the selected action?

Bare `bora` requires an interactive terminal and opens the workbench; `bora --plain` selects its
reduced presentation. Scripts and redirected use call explicit subcommands, and no operation is
available only through the TUI.

### 1.1 Included

- a responsive local-state overview;
- one central menu that opens seven read-only sections as full windows;
- deterministic next-step advice;
- exact composition of current commands, with per-action flag toggles;
- a calibration wizard that can produce only valid option combinations;
- post-UI command dispatch with normal terminal I/O and existing confirmations;
- one blue/white visual identity, wider centred sections, and motion-free static section graphics;
- continuous multicolour Unicode wind/sea motion on home with accessibility kill switches.

### 1.2 Excluded

- command renames, aliases, or new `model`, `self`, or `pi connect` groups;
- package-tree reorganization;
- embedded launch, calibration, npm, uv, update, or uninstall execution;
- editable settings or generated TOML;
- arbitrary model selection or arbitrary flags;
- clipboard protocols and `$EDITOR` launching;
- Open WebUI rows, actions, service roles, or placeholders;
- passive network checks and background polling.

Open WebUI is a separately deferred backlog. The current machine may be used for its future spike
only after another explicit request.

---

## 2. Opening contract

Opening and refreshing the TUI are non-mutating. They perform no:

- network request;
- model-payload hashing;
- verification-receipt write;
- directory creation;
- service-state cleanup, quarantine, or rewrite;
- lifecycle-lock acquisition;
- configuration write;
- managed-service start;
- periodic background poll.

The snapshot may read local files, inspect process identities, and run the same bounded read-only
hardware and engine probes as `doctor`. Those probes can invoke `nvidia-smi` and the engine's
version/help commands, so the honest contract is "no managed or persistent process", not "no
subprocess".

Static chrome paints before collection starts. One presentation worker runs the synchronous
collector, refresh requests are coalesced, and input remains responsive while a probe is slow. A
collection failure becomes an actionable screen, never a traceback.

### 2.1 Truthful state

The snapshot distinguishes facts that the earlier proposal conflated:

- a service record may be live, stale, absent, or unreadable; unreadable state is never silently
  reported as empty and inspection never repairs it;
- a locked model artifact may be absent, wrong-size, receipt-verified, or present-unverified;
  presence alone is not verification;
- a custom `model_path` is user-managed and never receives a `bora pull` recommendation;
- configuration values carry their source: `environment`, `config.toml`, or `default`;
- the published release version is not queried passively; `bora update --check` is the explicit
  network action.

---

## 3. Information architecture

The workbench opens on one home surface: the verdict and a central menu of seven user-facing
entries. A close-set, entirely blue `Bora Workbench` title and the wind/sea graphics are shared
chrome around home and every section. They are not CLI help groups and do not rename commands.
`Enter` opens the marked entry as a full window; `Esc` returns. Only one surface is navigable at a
time, so the keyboard never carries two simultaneous axes of movement.

Home retains a compact menu. Each section uses a centred responsive measure wider than home, so
facts and paths wrap less often, and separates actions, exact command, and local details into blue
bordered panels. Blue headings and labels structure high-contrast white explanation text; the marked
action also carries one concise description. Selection and meaning remain explicit in text.

| Entry | Purpose |
|---|---|
| **Run** | `coding`, `studio`, and `vstudio`, including the active cell or baseline |
| **Calibration** | record/candidate states and a command-composing wizard |
| **Setup** | engine and receipt-aware pinned-model readiness |
| **Diagnostics** | memory, services, the full local report, and the returning diagnostic commands |
| **Pi** | installation state, provider state, and D-082 context-window source |
| **Settings** | resolved values, provenance, config path, and environment names; read-only |
| **This installation** | installed version, four roots, update, and precise removal boundary |

Run comes first because launching a mode is the reason the workbench exists. The Overview section is
split: its verdict and identity live on the home surface, where they are read on every visit, and its
full report and diagnostic commands live under Diagnostics.

Every menu row carries a one-line summary derived from the snapshot, so the state of the machine is
readable without opening anything. Those summaries are the dashboard: a section holds detail, not a
restatement of what the menu already showed.

There is no first-run marker and no automatic onboarding state file. Missing prerequisites are
visible through the home verdict, the menu summaries, and Setup. The dashboard does not imply that
baseline launch is broken merely because calibration is absent.

### 3.1 Home wording

The first useful sentence is a diagnosis, not a greeting. Examples:

- `Nothing is running. All modes use the verified baseline.`
- `coding is serving ctx 65536 on 127.0.0.1:8080.`
- `The pinned weights are present but need verification. Run bora pull.`
- `A coding candidate is ready. Activation still uses the real calibration confirmation.`

Advice uses one deterministic priority:

1. collection or configuration failure;
2. packaged-content error;
3. absent or incompatible engine;
4. incomplete or unverified default model;
5. live service;
6. valid pending candidate;
7. missing active calibration, with a calm baseline explanation;
8. ready to run `bora coding`.

Advice never invents a command when no safe command is a truthful remedy.

---

## 4. Calibration vocabulary

The CLI, snapshot, documentation, and TUI use one display vocabulary.

| Core evaluation | Display label |
|---|---|
| `valid` | `active` |
| `missing` | `absent` |
| `candidate` | `candidate` |
| `superseded` | `superseded` |
| `invalid` | `invalid` |
| `incompatible` | `incompatible` |
| `insufficient-headroom` | `insufficient headroom` |

A pending candidate is a secondary fact beside the active-record state. `stale` describes process
state, not a calibration record. Older record formats are superseded and never migrated.

The absence of an active record is not a launch failure. The verified baseline remains available at
`ctx=8192`, with CUDA `n_cpu_moe=48` where applicable, and is explicitly described as working but not
locally optimized.

---

## 5. Command visibility and handoff

Every actionable screen shows the exact command before selection. The UI owns only composition.

A section lists its actions once and switches their optional flags in place, each flag bound to the
single letter shown in brackets beside it. Enumerating one menu row per flag combination produced
twenty Setup rows for four operations, which is unreadable; the toggles keep every reachable argv
available while the list stays the length of the operations it offers. Each action retains its own
flags while the marker visits another action, and a flag pair that the CLI rejects — pi's `--print`
with `--install` — excludes itself so the invalid pair stays unreachable.

When a command is selected:

1. the TUI exits its alternate screen;
2. cursor, styles, mouse mode, input mode, and signal handling are restored;
3. the exact command remains visible in normal scrollback;
4. the existing Click/Typer command is invoked in the same bora process;
5. the existing callback owns all prompts, subprocesses, network, writes, and exit mapping.

There is no `subprocess.run([sys.executable, "-m", ...])` parent waiting in the uv tool environment.
That matters on Windows: deferred `update` and `uninstall` must observe the one process that will
actually exit.

A returning action waits in the restored terminal after exit 0, keeping its output visible until
the operator presses Enter; only then does it reopen and re-collect. Exit 1, 2, or 130 ends the bare
`bora` invocation with that exact result. A terminal action never reopens.

### 5.1 Action matrix

| Section | Current command | Disposition |
|---|---|---|
| Run | `bora coding [--force]` | terminal |
| Run | `bora studio [--force]` | terminal |
| Run | `bora vstudio [--force]` | terminal |
| Calibration | `bora calibrate ...` | terminal |
| Calibration | `bora calibrate --mode ID --activate` | terminal |
| Setup | `bora engine status` | returning |
| Setup | `bora engine install [--force] [--no-model]` | returning on success |
| Setup | `bora pull` | returning on success |
| Setup | `bora rm [--keep-hf] [--dry-run]` | returning on success |
| Diagnostics | `bora doctor` | returning |
| Diagnostics | `bora validate` | returning |
| Diagnostics | `bora status` | returning |
| Diagnostics | `bora engine status` | returning |
| Diagnostics | `bora stop` | returning |
| Pi | `bora pi launch` | terminal |
| Pi | `bora pi [--print] [--install]` | returning on success |
| Pi | `bora pi remove` | returning on success |
| Pi | `bora pi uninstall` | returning on success |
| This installation | `bora update --check` | returning |
| This installation | `bora update` | terminal |
| This installation | `bora uninstall` | terminal |

`bora pull` and `bora rm` are composed without the optional `qwen` handle. This distribution pins one
model, so the handle names what the bare form already does; the CLI still accepts it.

Every reachable argv is tested through the real recursive Click parser to its leaf without executing
the callback. The enumeration is derived from each section's own action and flag declarations, so a
form the UI can reach cannot escape the parser check. Root-only parsing is insufficient for nested
options.

---

## 6. Calibration wizard

The wizard teaches the one current calibration protocol without reimplementing it.

1. choose `coding`, `studio`, `vstudio`, or `all`;
2. choose `fast`, `balanced`, or `max-context`;
3. choose normal activation or `--no-activate`;
4. optionally choose one approved measurable `--target-ctx`;
5. review the exact command.

Candidate activation is a separate route:

```text
bora calibrate --mode <id> --activate
```

When activation is selected, preference, target, and `--no-activate` are absent by construction.
The review says that the real preflight and confirmation follow. The TUI does not duplicate or
pre-answer either one, and calibration runs in the normal terminal after UI teardown.

---

## 7. Setup, model ownership, and removal

Since D-078, bora owns acquisition of the one pinned model:

- `bora pull` downloads and verifies locked weights and projector into the managed store;
- `bora engine install` performs the same acquisition unless `--no-model` declines it;
- the pinned Hugging Face snapshot remains a read-only fallback;
- a custom model path stays outside `pull` and `rm`.

The Setup screen reflects those facts. It does not tell the user to populate the cache manually and
does not call a file verified merely because it exists.

Removal follows D-079:

- `bora rm` removes managed pinned artifacts and asks separately about confined pinned copies in the
  shared Hugging Face cache;
- `bora uninstall` removes the four managed roots and asks that cache question separately;
- the cache question defaults to no and is never implied by another consent.

The TUI adds friction without replacing those prompts. Selecting uninstall requires typing
`remove`; after that, the UI exits and the real command still asks its independent questions.

---

## 8. Pi

The Pi screen reflects D-081/D-082/D-090. It shows:

- whether pi is available and its executable path;
- the `models.json` path without inferring or changing its provider contents;
- whether context came from the live service, active `coding` record, or verified baseline;
- the diagnostic attached to baseline fallback.

It composes only the existing forms:

```text
bora pi
bora pi --print
bora pi --install
bora pi launch
bora pi remove
bora pi uninstall
```

`--print --install`, and group options beside a subcommand, are invalid and unreachable. No other
agent, editor, or provider appears.

---

## 9. Interaction and terminal behavior

The interaction stack is the accepted Textual `8.2.8` dependency from D-086. Textual owns only the
presentation event loop, one snapshot thread worker, and the optional home motion timer; core APIs remain
synchronous. The implementation contains no parallel Rich raw-input loop or handwritten
`termios`/`msvcrt` behavior.

Expected navigation:

| Key | Action |
|---|---|
| arrows or `j`/`k` | move the marker of whichever surface is open |
| `Enter` / `Right` | open the marked entry, accept a wizard answer, or select the marked action |
| `Esc` / `Left` | return to the menu; on the menu it quits; during review it cancels |
| a bracketed letter | switch that flag of the marked action |
| `PageUp` / `PageDown` | scroll long detail |
| `r` | request one serialized refresh |
| `?` | key help |
| `q` / `Ctrl-Q` | quit |

One marker moves at a time. The earlier design moved between screens with the arrows and between a
screen's actions with `Tab`, which forced the reader to hold two positions at once; opening a section
as a full window removes the second axis instead of documenting it.

While the typed removal phrase has focus, every single-letter binding is released to the field
instead of being intercepted, so the confirmation behaves like an ordinary text input.

Destructive actions are never root single-letter shortcuts. Confirmation defaults to no. Small
terminals scroll or simplify instead of hiding an operation.

A non-TTY bare invocation prints one actionable line and exits 2 before importing Textual. The
root-only `--plain` option, `NO_COLOR`, `TERM=dumb`, and unsupported output encoding select
deterministic plain rendering. `BORA_TUI_MOTION=off` retains the normal static title and graphics
when every other capability is available. Automatic legacy raster-font detection is not promised.

---

## 10. Bora identity and optional motion

The workbench asks for the terminal's default background rather than painting one. D-092 gives every
screen one close-set `Bora Workbench` title in blue and a blue/white hierarchy: blue title, borders,
headings, labels, marker, and exact commands; high-contrast white body prose; and muted blue
secondary facts. Shared Rich CLI helpers use the same identity while retaining explicit warning and
error labels. Colour and decoration carry no state.

D-092 refines D-090's visual effect without changing its home animation rate:

- three wind rows use sparse `·`, `╌`, `╍`, and `━` ribbons through blue-to-white sky colours;
- a fractional-block wave surface sits over two blue shaded/full-cell water rows;
- gust and sea remain pure functions of time, dimensions, and seed;
- motion continues only on focused home, at 6 fps under a 12 fps ceiling;
- an open section freezes and retains the current frame while removing the timer;
- `BORA_TUI_MOTION=off` renders a deterministic static frame with no timer;
- small terminals, lost focus, `bora --plain`, `NO_COLOR`, `TERM=dumb`, and limited encoding hide
  both bands and own no timer;
- unmount always releases the timer, malformed motion configuration exits 2, and static text retains
  the full meaning and every action.

The raw observation in `evidence/tui/ubuntu-motion.json` measured the superseded finite 8 fps effect.
It remains historical evidence and is not a CPU result for the continuous implementation. A new
Ubuntu observation and the Windows visual/CPU checks have not been performed.

No animation appears in normal CLI commands, launch, calibration, setup, update, or uninstall.

---

## 11. Accessibility and testing

Alternate-screen TUIs are not universally accessible. The complete CLI remains the supported path
for scripts, redirected output, screen readers, and users who prefer it. Colour and animation carry
no unique information.

Tests focus on semantics rather than pixel snapshots:

- pure advice, composition, capability, and motion functions;
- frozen, slotted snapshot models;
- no mutation or network during opening and refresh;
- first frame before collection and input during a blocked fake collector;
- no overlapping refresh;
- opening every section from the central menu at 60x20, 80x24, and 120x40;
- menu summaries, action markers, and flag toggles as pure state;
- every reachable command accepted by the real recursive parser;
- teardown before dispatch and exact exit propagation;
- lazy imports and side-effect-free package import.

Real network, GPU, model, service, npm, update, and administrative operations remain absent from the
offline suite. Ubuntu and Windows terminal restoration, signals, update, and uninstall require the
manual checks in `TUI_PLAN.md` Part F; unavailable checks stay explicit limitations and never become
a calibration Gate.
