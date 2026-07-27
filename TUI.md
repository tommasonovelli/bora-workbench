# bora TUI — design proposal

> **Status: PROPOSAL. Not normative, not planned, not approved.**
>
> `IMPLEMENTATION_SPEC.md` is the only normative plan in this repository, and `README.md` states
> that unimplemented work lives only there. This file therefore exists as a *decision input*: a
> proposal to read, cut down, and either reject or fold into specification section 8 as
> **Backlog D — Interactive front end**, after which this file should be deleted rather than kept
> as a second roadmap. Do not treat any sentence here as a commitment, and do not implement
> anything described below without an explicit maintainer decision recorded in the decision table
> of `IMPLEMENTATION_SPEC.md`.
>
> Everything here is written against the behavior that exists today in `0.2.1`: the commands in
> `docs/commands.md`, the contracts in specification section 5, and the rules in `AGENTS.md`.

---

## 0. Verdict first

**The idea is good, but not in its original shape.** The valuable half is real and cheap; the
expensive half is where the risk lives.

| Part of the idea | Verdict |
|---|---|
| A calm, branded home screen with the real state of the machine | **Keep.** Highest value per line of code. |
| Wind + waves identity, animated | **Keep, but budgeted.** Motion must be optional, cheap, and never in the command path. |
| opencode-style navigation (list left, detail right, keys at the bottom) | **Keep.** It fits a tool with ~10 commands and 3 modes. |
| A wizard that composes `calibrate` flags and asks "you are not calibrated, shall we?" | **Keep.** This is the strongest screen in the whole concept. |
| An uninstall key | **Keep, with friction.** One keystroke must never be enough. |
| The TUI *running* long jobs inside itself (engine install, calibration, the three modes) | **Change.** It should **hand off** to the real command instead of re-hosting it. |
| A settings editor | **Cut** (or make read-only). It contradicts a normative rule: the launcher never rewrites `config.toml`. |
| The TUI as the default behavior of bare `bora` | **Defer.** Ship it as `bora tui` first. Flipping the default is a CLI contract change. |

The single most important design decision in this document is in §3.4: **the TUI is a dashboard and
a command composer, not a second runtime.** Everything that makes a TUI expensive, fragile, and
dangerous in this project (process lifetime, Ctrl-C, exit codes, hours-long calibration, deleting
its own installation) disappears the moment the TUI's last act for any real operation is *"run the
exact `bora …` command you can see on screen, and get out of the way"*.

That also happens to be the thing you asked for in your own words — *"che rifletta i comandi che uno
andrebbe a lanciare"* — taken to its logical conclusion.

---

# Part I — Code layout first

## 1.1 Why this comes before the TUI

`src/bora_workbench/` currently holds 26 hand-written modules in one flat namespace, of which 21
are `_`-prefixed satellites of five real areas:

```
calibration.py  + 10 × _calibration_*.py
engine.py       +  2 × _engine_*.py
validation.py   +  4 × _validation_*.py
process.py      +  1 × _process_state.py
cli.py          +  4 × _cli_*.py
benchmark.py, benchmark_quick.py
config.py, hardware.py, paths.py, profiles.py, uninstall.py, _tool_uninstall_helper.py
```

The 600-line file ceiling in `AGENTS.md` is doing its job — no file is a monolith — but the *cost*
of that ceiling is currently paid in the file listing: an area of competence is spread over eleven
sibling files that the reader has to reassemble mentally, which is exactly what the same section of
`AGENTS.md` warns against ("prefer one readable module per area over a constellation of
two-function files"). Adding a TUI to that flat namespace would add another 6–10 `_tui_*.py`
siblings and make it worse.

So: **reorganize first, in its own PR, with zero behavior change**, then decide about the TUI.
These are independent — the reorganization is worth doing even if the TUI is rejected.

## 1.2 Target tree

```
src/bora_workbench/
├── __init__.py
├── cli/
│   ├── __init__.py          # re-exports `app` for the console-script entry point
│   ├── app.py               # was cli.py: Typer wiring, options, exit codes
│   ├── services.py          # was _cli_services.py
│   ├── calibration.py       # was _cli_calibration.py
│   ├── diagnostics.py       # was _cli_diagnostics.py
│   └── theme.py             # was _cli_theme.py
├── tui/                     # only if Backlog D is approved
│   ├── __init__.py
│   ├── app.py               # screen graph, key routing, quit/handoff
│   ├── snapshot.py          # the read-only state the screens render (§3.2)
│   ├── actions.py           # screen state → the exact argv it would run (§3.4)
│   ├── palette.py           # colours and glyph sets, degradation ladder
│   ├── motion.py            # the gust and the sea, pure functions of (t, width)
│   └── screens/
│       ├── home.py  onboarding.py  modes.py  calibration.py
│       ├── diagnostics.py  records.py  danger.py  help.py
├── calibration/
│   ├── __init__.py          # public surface: what calibration.py exports today
│   ├── run.py  runner.py  trial.py  trial_control.py
│   ├── search.py  memory.py  record.py  reuse.py
│   ├── types.py  gguf.py  gpu_evidence.py
├── benchmark/
│   ├── __init__.py          # `benchmark/v1` public surface
│   ├── protocol.py          # was benchmark.py
│   └── quick.py             # was benchmark_quick.py
├── engine/
│   ├── __init__.py  lock.py  assets.py  install.py
├── validation/
│   ├── __init__.py  profiles.py  engine.py  calibration.py  calibration_v3.py
├── process/
│   ├── __init__.py  state.py
├── uninstall/
│   ├── __init__.py  tool_helper.py
├── config.py   hardware.py   paths.py   profiles.py
└── resources/
```

Left flat on purpose: `config.py`, `hardware.py`, `paths.py`, `profiles.py`. Each is a single
coherent module with no satellites; wrapping them in one-file packages would be ceremony.

## 1.3 The rules this move has to respect

1. **Import paths stay stable where they are public.** Turning `calibration.py` into
   `calibration/__init__.py` keeps `from bora_workbench.calibration import …` working. Do the same
   for `engine`, `validation`, `process`, `benchmark`. The 229 references across 63 files are
   overwhelmingly to *these* names plus the private `_`-prefixed ones; the private ones are free to
   move, and the tests that import them get updated in the same PR.
2. **`pyproject.toml` needs no change** for packaging (`uv_build` takes the whole `src/` package
   tree), but `scripts/verify_wheel.py` and `tests/test_resources.py` must be re-checked, because
   anything that asserts on file names will move with the tree.
3. **Specification section 4.1 (module responsibilities) and section 4.2 (territories) are
   normative and must be updated in the same commit**, together with `docs/architecture.md`. A
   layout change that leaves the normative table describing the old tree is a spec violation, not a
   cosmetic lag.
4. **`AGENTS.md`: "Do not rename, move, generalize, or reformat unrelated files."** The way to
   satisfy that rule is not to avoid the move but to make the move *be* the change: one PR, `git mv`
   only, no edits inside the moved files beyond import lines, and a commit body that says so.
5. **One implementation step per commit**, and a PR touches core or declarative content, never both.
   The reorganization touches no `resources/`.

## 1.4 Suggested commit sequence

| # | Commit | Content |
|---|---|---|
| 1 | `refactor(cli): move the CLI modules into a cli package` | `git mv` of `cli.py` + 4 `_cli_*`, entry point re-export, import fixes |
| 2 | `refactor(calibration): move the calibration modules into a package` | 11 files, `__init__.py` re-export |
| 3 | `refactor(engine): …` / `refactor(validation): …` / `refactor(process): …` / `refactor(benchmark): …` | one per area |
| 4 | `docs: realign the module tables with the package tree` | spec 4.1/4.2 + `docs/architecture.md` |

After each: `ruff check`, `ruff format --check`, `pytest`, `uv build`,
`python scripts/verify_wheel.py`, `bora validate`. The suite is the proof that the move changed
nothing — that is the entire point of doing it before the TUI rather than during it.

## 1.5 What this reorganization must not become

Not an excuse to merge modules, rename functions, "improve" APIs, add `Protocol`s, or introduce a
`core/` layer. Mechanical only. Any behavioral idea discovered along the way goes into a note, not
into the same PR.

---

# Part II — What the TUI is, and what it is not

## 2.1 Principles

- **P1 — One source of behavior.** The TUI never re-implements a check, a threshold, a preflight,
  or a confirmation. It reads the same functions the CLI reads and runs the same commands a human
  would type. If a rule exists in only one of the two front ends, that is a bug in the design.
- **P2 — The command is always visible.** Every screen that can *do* something shows the exact
  command line it will run, in a fixed place, before it runs it. The user learns the CLI by using
  the TUI. This is the `lazygit` / `opencode` property, and for this project it is not decoration:
  it is what keeps the TUI from becoming a way to run things you cannot reproduce.
- **P3 — The TUI is optional, always.** Everything reachable in the TUI is reachable by typing.
  Nothing is TUI-only. Scripts, CI, and redirected output behave exactly as they do today.
- **P4 — Read by default, act on purpose.** Opening the TUI must be free of consequences. It starts
  no process, creates no directory, writes no state, touches no config. Actions require an explicit,
  deliberate keystroke sequence, and destructive ones require more than one.
- **P5 — Degrade, never fail.** Small terminal, no colour, no UTF-8, no TTY, `NO_COLOR`, an SSH
  session, `tmux`, a screen reader: each removes a layer of decoration and never removes an ability.
- **P6 — Motion serves state.** Animation exists to say "the wind is what this tool is named after"
  and, secondarily, "something is happening". It never encodes a measurement, and it never becomes
  the only way to see a value.
- **P7 — The boundary holds.** The README says this is "a finished, opinionated setup rather than a
  fitting algorithm". A TUI is a natural place for scope creep — model pickers, flag editors,
  profile builders, plugin panes. None of those become reachable because a screen has room for them.

## 2.2 The mapping the TUI is allowed to expose

| Screen | Command(s) behind it | Kind |
|---|---|---|
| Overview | `doctor`, `status`, `engine status`, `validate` | read |
| Onboarding | the same reads, in order, as a checklist | read |
| Modes | `coding` / `studio` / `vstudio` `[--force]` | handoff |
| Calibration | `calibrate --mode … [--preference …] [--no-activate] [--activate] [--target-ctx N]` | handoff |
| Engine | `engine install [--force]`, `engine status` | handoff / read |
| Services | `status`, `stop` | read / short action |
| Records | the per-mode record states `doctor` already evaluates | read |
| Settings | the resolved configuration, **read-only**, plus the file path and env names | read |
| Danger zone | `uninstall` | handoff, with friction |

Nothing else. No screen invents a flag combination that the CLI would reject, because the composer
builds the same argv the CLI parser validates (§3.4), and invalid combinations — `--activate` with
`--target-ctx`, `--activate` with `--no-activate`, `--activate` with `--preference` — are simply not
reachable in the UI.

---

# Part III — Architecture

## 3.1 The seam that is missing today

`_cli_diagnostics.py`, `_cli_services.py`, and `_cli_calibration.py` currently do three jobs at
once: they orchestrate, they render to a `rich.Console`, and they map exceptions to exit codes.
`AGENTS.md` already asks CLI functions to be limited to "input, presentation, service calls, and
exit-code mapping", and today the diagnostics path is closest to the line, because assembling the
`doctor` picture *is* the orchestration.

A TUI cannot render `doctor` by scraping its stdout. It needs the same picture as data. So the
honest cost of any TUI is:

> **Extract, for the read-only picture only, a function that returns a structured snapshot, and
> make `doctor` render that snapshot instead of computing while it prints.**

This is a good refactor on its own terms (it is testable without a console), it is bounded, and it
is the *only* core change the recommended design requires. If it turns out to be large, that is the
signal to stop and reconsider the whole feature — not to let the TUI grow its own data path.

## 3.2 The snapshot

One frozen, slotted dataclass tree, computed on demand, cheap enough to refresh on a key press and
never automatically:

```
Snapshot
├── version, platform, backend                      (hardware.py)
├── config: resolved values + source of each        (config.py)
├── paths: config / data / cache / state            (paths.py)
├── engine: installed?, release, backend, lock match(engine)
├── model: present?, verified?, sizes, revision     (engine)
├── content: validate result (errors, warnings)     (validation)
├── memory: total / available GiB, gate verdict     (hardware.py)
├── services: [(mode, pid, port, log)] verified     (process)
└── records: per mode → one of
      active | candidate | absent | incompatible | stale | superseded | insufficient headroom
```

Those record states are the ones `doctor` already distinguishes (`docs/commands.md` §`doctor`). The
TUI must show exactly them, with the same words, and must not invent a friendlier taxonomy — a
"superseded" record is not "old", and "insufficient headroom" is not "won't work".

Refresh policy: on entry, on `r`, and after any handoff returns. Never on a timer. A dashboard that
polls `nvidia-smi` in a loop is a dashboard that perturbs the thing calibration measures.

## 3.3 Progress, if anything ever runs in-process

The seam already exists: `RunOptions(progress=…)` receives a `CalibrationProgress` object, and
`_cli_calibration.py` / `_cli_diagnostics.py` both branch on `console.is_terminal` to choose live
vs. line-oriented rendering. If a future phase ever hosts a job inside the TUI, it plugs a second
implementation into that same port. **No new event system.** That is a decision to defer, not to
prepare for: `AGENTS.md` forbids speculative extension points.

## 3.4 Handoff vs. embedding — the key decision

**Recommended: handoff.**

When the user confirms an action, the TUI:

1. leaves the alternate screen and restores the terminal (cursor, colours, mouse, raw mode);
2. prints the exact command line it is about to run, so it stays in the scrollback;
3. restores the default `SIGINT` handler;
4. runs it as a child process (`subprocess.run`) with stdio inherited, or replaces itself when the
   action is terminal (see below);
5. exits with the child's exit code, or returns to the TUI for short read-only actions.

Why not `os.execvp`: it is the clean POSIX answer, but Windows has no real `exec` — the emulation
returns a new process and detaches the console in ways that break foreground behavior. Since both
platforms are first-class here, use the same `subprocess.run` shape on both.

What this buys, concretely:

| Problem | With embedding | With handoff |
|---|---|---|
| `coding/studio/vstudio` stay attached in the foreground until `Ctrl-C` (exit 130) | The TUI must own the child's lifetime, forward signals, and guarantee state cleanup and identity-safe stop from inside a UI event loop | Unchanged behavior. The mode owns the terminal exactly as documented |
| Calibration can run for **hours**, starting many short-lived servers | Hours of alternate-screen ownership; one stray key near a cancel binding wastes the whole run | The existing live bar renders in a normal terminal; cancellation is the documented `Ctrl-C` → 130 |
| Exit codes 0/1/2/130 are a contract | The TUI must synthesize them | They are the child's, verbatim |
| `uninstall` deletes the installation that is running the TUI | Self-deletion while the UI process is alive | The TUI is already gone when `uninstall` starts |
| Testing | A UI harness driving multi-hour flows | The tested surface is one pure function: state → argv |

The composer is then trivially testable, and it is the whole "engine" of the TUI:

```python
def compose(screen_state) -> tuple[str, ...]:
    """Return the exact argv the CLI would parse for this screen state."""
```

One table-driven test enumerates every reachable screen state and asserts the argv, and a second
asserts that every produced argv is accepted by the real parser (`parse_calibration_input`) — which
means a UI that can only produce valid commands, proven offline, on both platforms.

## 3.5 Dependency: Textual, or Rich only?

`AGENTS.md` allows `typer`, `rich`, `psutil`, `httpx`, `jsonschema` and requires a justification for
anything new, including maintenance, licensing, security, and transitive cost.

- **Rich only** — already a dependency. Gives layout, tables, `Live`, and colour. Gives *no*
  keyboard handling: you write a raw-mode reader per platform (`msvcrt` on Windows, `termios`/
  `tty` + `select` on POSIX), your own focus model, your own resize handling. That is a few hundred
  lines of exactly the platform-branching code the module rules try to contain, and only
  `paths/process/hardware/engine` are allowed to branch on the OS.
- **Textual** — same author as Rich, builds on it, pure Python, works on Windows Terminal and
  POSIX, and ships a headless test pilot. Cost: a real dependency addition in a project whose whole
  identity is pinned, verified supply chain, plus a transitive tree to review at decision time.

**Recommendation:** if the TUI is approved as designed here (dashboard + composer + handoff), start
with **Rich only** for Phase 1, because a static, non-interactive splash and a snapshot table need
no event loop at all — and adopt Textual only when Phase 2's navigation makes the hand-rolled input
loop the larger risk. Deciding the dependency *after* Phase 1 is the cheap way to make the decision
with evidence instead of taste.

---

# Part IV — The bora, on a terminal

The identity is the point of the whole feature, so it deserves the same rigour as the rest: the
bora is a **katabatic, gusty north-easterly** — it arrives in bursts (*refoli*), not as a steady
breeze, and what it does to the gulf is short, steep, white-capped chop. A smoothly scrolling
sine wave and a constant particle stream would be a generic "wind animation". Bursts are the
signature.

## 4.1 Banner

Primary, when the terminal reports UTF-8 and ≥ 92 columns:

```
   ██████╗   ██████╗  ██████╗   █████╗
   ██╔══██╗ ██╔═══██╗ ██╔══██╗ ██╔══██╗
   ██████╔╝ ██║   ██║ ██████╔╝ ███████║      workbench 0.2.1
   ██╔══██╗ ██║   ██║ ██╔══██╗ ██╔══██║      one Qwen setup, three local experiences
   ██████╔╝ ╚██████╔╝ ██║  ██║ ██║  ██║
   ╚═════╝   ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝
```

ASCII fallback (any terminal, ≥ 60 columns):

```
   |__ )  / _ \  |  _ \   /   \
   |  _ \| | | | | |_| | | /_\ |     workbench 0.2.1
   |___/  \___/  |_| \_\ |_| |_|
```

Below 60 columns, or when output is redirected: the plain line `bora workbench 0.2.1`.

## 4.2 The gust

A pure function `gust(t, width, height) -> list[str]`, no state outside its arguments, so it can be
unit-tested and frozen in tests.

- **Envelope.** Gusts are discrete events, not a continuous flow. Each has a start time, a duration
  of ~0.6–1.4 s, and an intensity; between gusts there are calm gaps of 1–4 s where the header is
  almost still. Draw from a seeded PRNG so a session is reproducible and a test is deterministic.
- **Particles.** Each is `(row, x, speed, length, glyph_class)`, travelling **left → right** across
  the banner rows (the bora hits Trieste from the ENE; direction is a choice, consistency is not).
  Speed varies per particle so the front smears instead of marching.
- **Glyphs**, from faint to strong: `· ˙ ‧ ⋯ ~ ⁓ ─ ═ ≡`. A long streak is a run of `─` with a `═`
  head. ASCII set: `. , - ~ = _`.
- **Trails** fade by *style*, not by glyph swap: head bright, body accent, tail dim. This is why the
  effect survives on a 16-colour terminal — the shape carries it, colour only sweetens it.
- **Interaction with the banner:** particles pass *behind* the letterforms (they are skipped where a
  letter cell is non-blank), so the wind visibly blows around the word instead of through it.

## 4.3 The sea

Two or three rows at the bottom of the home screen only.

- **Surface**: superposition of 3 sines with incommensurable periods, quantized to
  `▁▂▃▄▅▆▇` (ASCII: `.-~^`). Slow drift, ~0.5 cell/s.
- **Coupling**: a gust in the header raises the local amplitude of the rows below it after a short
  lag (~0.4 s) and adds whitecaps (`▀`, ASCII `^`) where the local slope is steepest. That lag is
  the whole trick — it reads as *the wind pushing the water*, which is the actual feeling of the
  bora on the Molo Audace, and it costs one delay buffer.
- The sea never covers content and never scrolls the viewport. It occupies the bottom band above
  the key bar and is dropped entirely below 24 rows.

## 4.4 Palette

`_cli_theme.py` deliberately uses built-in Rich style names only, so styles stay valid on
theme-free consoles, and its comment states that colour never carries meaning alone. The TUI extends
that, and does not contradict it:

| Role | Style | Note |
|---|---|---|
| Wind head | `bold white` | |
| Wind body / accent | `cyan` | matches existing `STYLE_ACCENT` |
| Wind tail | `dim cyan` | |
| Sea | `blue` / `dim blue` | |
| Whitecap | `bold white` | |
| Success / warning / error / heading | reuse `STYLE_*` from the CLI theme verbatim | one palette, two front ends |

Truecolor (a deeper Adriatic blue ramp) only when `COLORTERM` says so, as an upgrade over the
16-colour rendering — never as a requirement.

## 4.5 Motion budget and the degradation ladder

Hard rules:

- **≤ 12 fps** idle, and only when the home screen is focused. Not 60. This is a terminal.
- **Idle CPU ≤ ~2 %** of one core on the reference machines; measure it, do not assume it.
- **Motion stops** when: the window loses focus (where detectable), any other screen is open, a
  handoff is in progress, the terminal is < 24 rows, or the process is not on a TTY.
- **Motion is off entirely** with `BORA_TUI_MOTION=off`, `NO_COLOR`, `TERM=dumb`, or `--plain`.
- **Motion never delays input.** Key handling is never blocked by a frame.
- Nothing animated ever appears in `coding`, `studio`, `vstudio`, `calibrate`, `engine install`,
  `doctor`, `status`, `stop`, `validate`, or `uninstall`. The animation belongs to `bora tui` and
  nowhere else. A splash on every command invocation would be charming twice and irritating forever.

Ladder: **truecolor + UTF-8 + motion** → 16-colour + UTF-8 + motion → UTF-8, no motion → ASCII, no
colour → plain banner line → the existing CLI output. Each rung is a supported configuration with a
test, not an accident.

## 4.6 Terminal compatibility

| Environment | Notes |
|---|---|
| Windows Terminal (PowerShell / cmd) | Primary Windows target. VT is on; UTF-8 available. |
| Legacy `conhost.exe` | Needs `ENABLE_VIRTUAL_TERMINAL_PROCESSING`; raster fonts break box drawing → detect and fall back to ASCII. |
| VS Code integrated terminal | Fine; resize events are frequent — debounce redraws. |
| Ubuntu `gnome-terminal`, `xterm`, `kitty`, `alacritty` | Fine. |
| `tmux` / `screen` | Fine; assume 256 colours unless `COLORTERM` says otherwise. |
| SSH from Windows to Ubuntu | Assume the *lowest* capability the environment reports. |
| Redirected / piped / CI | No TUI at all. `bora tui` without a TTY prints a one-line explanation and exits 2. |

Never emoji: variable-width glyphs wrap lines and split tokens, which is the exact reason the
existing theme banned decorative glyphs.

---

# Part V — Navigation and keymap

Model: a persistent left rail of sections, a detail pane on the right, a fixed key bar at the
bottom, modal overlays for confirmations. Selection moves with the arrow keys or `j`/`k`, `Enter`
opens, `Esc` backs out, and `Esc` at the root quits. That is the opencode-settings feel: a small
number of always-visible sections and a detail pane that changes under the cursor.

| Key | Action |
|---|---|
| `↑ ↓` / `k j` | move within the focused list |
| `← →` / `h l` | move between rail and detail |
| `Enter` | open / confirm the focused item |
| `Esc` | back; at the root, quit |
| `r` | refresh the snapshot |
| `c` | jump to calibration |
| `d` | run `doctor` (handoff, returns) |
| `s` | services (`status`) |
| `?` | help overlay with the full keymap |
| `q` / `Ctrl-Q` | quit |
| `y` / `n` | answer a confirmation (never bound to anything else) |

Rules that avoid the classic TUI accidents: destructive actions are **not** on a single letter at
the root; confirmation modals default to **No**; `y`/`n` exist only while a modal is open; no key
sequence that starts a job is adjacent to a navigation key.

---

# Part VI — Screens

## 6.1 Home

```
   ·        ⋯⋯───         ·                    ⋯⋯⋯────           ·
   ██████╗   ██████╗  ██████╗   █████╗   ⋯⋯──────           ⋯⋯───
   ██╔══██╗ ██╔═══██╗ ██╔══██╗ ██╔══██╗
   ██████╔╝ ██║   ██║ ██████╔╝ ███████║      workbench 0.2.1
   ██╔══██╗ ██║   ██║ ██╔══██╗ ██╔══██║      one Qwen setup, three local experiences
   ██████╔╝ ╚██████╔╝ ██║  ██║ ██║  ██║
   ╚═════╝   ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝

  ┌─────────────────┬──────────────────────────────────────────────────────┐
  │ › Overview      │  Engine     b10011 · CUDA · active                   │
  │   Modes         │  Model      Qwen3.6-35B-A3B UD-Q4_K_M · verified     │
  │   Calibration   │  Content    validate: ok                             │
  │   Diagnostics   │  Memory     31.9 GiB total · 24.1 GiB available      │
  │   Settings      │  Services   none running                             │
  │   Danger zone   │  Records    coding baseline · studio baseline ·      │
  │                 │             vstudio baseline                         │
  │                 │                                                      │
  │                 │  This machine has never been calibrated. All three   │
  │                 │  modes start on the verified baseline (ctx 8192,     │
  │                 │  n_cpu_moe 48). That works — it is not optimized.    │
  │                 │                                                      │
  │                 │  [c] calibrate this machine     [Enter] start a mode │
  └─────────────────┴──────────────────────────────────────────────────────┘
   ▁▂▃▄▃▂▁▁▂▃▄▅▄▃▂▁▁▂▃▄▃▂▁▂▃▄▅▆▅▄▃▂▁▁▂▃▄▃▂▁▁▂▃▄▅▄▃▂▁▂▃▄▃▂▁▁▂▃▄▅▄▃▂▁▁▂▃▄▃▂
   ≈≈~≈≈≈≈~≈≈≈≈~~≈≈≈≈~≈≈≈≈≈~≈≈≈~≈≈≈≈~~≈≈≈≈~≈≈≈~≈≈≈≈~≈≈≈≈~~≈≈≈≈~≈≈≈≈~≈≈≈≈~≈≈
  ↑↓ move   ⏎ open   c calibrate   d doctor   r refresh   ? help   q quit
```

The wording of the "never been calibrated" note matters: the README's position is that calibration
is *the second step, not the entry price*. The home screen must nudge, never scold, and must never
imply the tool is broken before calibration.

## 6.2 Onboarding

Shown automatically on first run — where "first run" means *the snapshot says a prerequisite is
missing*, not a "have I run before?" flag file (P4: opening the TUI writes nothing). It is a
**verifying checklist**, not an installer, because two of its steps are things the tool
deliberately does not do for you.

```
  ┌─ Getting started ────────────────────────────────────────────────────┐
  │                                                                      │
  │  ✓ 1. bora is installed              0.2.1                           │
  │  ✓ 2. Platform and hardware          Windows 11 · CUDA · 1 GPU       │
  │  ✓ 3. Packaged content valid         validate: ok                    │
  │  ✗ 4. Engine installed               not installed                   │
  │       → runs: bora engine install                                    │
  │         downloads and verifies the pinned llama.cpp b10011;          │
  │         on Ubuntu CUDA it builds, which takes several minutes.       │
  │       [Enter] run it now                                             │
  │                                                                      │
  │  ✗ 5. Model files present            mmproj missing                  │
  │       bora never downloads weights. Put the pinned revision in the   │
  │       Hugging Face cache, then press r.                              │
  │       repo  unsloth/Qwen3.6-35B-A3B-MTP-GGUF                         │
  │       rev   5bc3e238d916f48a861bac2f8a1990a0e9b7e98d                 │
  │       need  mmproj-BF16.gguf (902,822,528 bytes) — vstudio only      │
  │       [y] copy the revision URL to the clipboard   [r] check again   │
  │                                                                      │
  │  · 6. Start a mode                   after step 5                    │
  │  · 7. Calibrate (optional, later)    after a mode works              │
  │                                                                      │
  └──────────────────────────────────────────────────────────────────────┘
   Esc skip · this screen appears until every required step is ✓
```

Steps 4 and 5 are where a naive wizard would lie. The honest design states the boundary
("bora never downloads weights") on the screen where the user hits it, and gives them the exact
revision to fetch — turning the project's most surprising constraint into its clearest moment.

## 6.3 Modes

```
  ┌─ Modes ──────────────────────────────────────────────────────────────┐
  │                                                                      │
  │  › coding    API only, no UI, no vision      sampling 0.6/0.95/20    │
  │    studio    built-in llama.cpp UI           sampling 0.7/0.80/20    │
  │    vstudio   UI + pinned vision projector    sampling 0.7/0.80/20    │
  │                                                                      │
  │  coding — a local OpenAI-compatible API at http://127.0.0.1:8080/v1  │
  │  record: none · will start on the baseline (ctx 8192, n_cpu_moe 48)  │
  │  the process stays in the foreground; Ctrl-C stops it                │
  │                                                                      │
  │  runs:  bora coding                                                  │
  │         [f] add --force (skips only the 28/22 GiB RAM gate)          │
  │                                                                      │
  │  ⏎ leave the TUI and run this command                                │
  └──────────────────────────────────────────────────────────────────────┘
```

The `runs:` line is P2 in practice, and it is deliberately the last thing above the action.

## 6.4 Calibration

This is your "not calibrated — shall we?" flow, made explicit. Four steps, each answering one
question, `Esc` always going back one step.

```
  ┌─ Calibration · step 2 of 4 ──────────────────────────────────────────┐
  │                                                                      │
  │  What should it optimize for?                                        │
  │                                                                      │
  │    fast          lowest latency on a short prompt, ctx ≥ 16384       │
  │  › balanced      largest context whose latency stays within 1.10×    │
  │                  that of fast                        (default)       │
  │    max-context   largest feasible context, ordered by throughput,    │
  │                  then memory margin, then caution                    │
  │                                                                      │
  │  Only the preference you pick is measured, gated, and stored.        │
  │  Recalibrating one mode replaces only that mode's cell.              │
  │                                                                      │
  │  runs so far:  bora calibrate --mode all --preference balanced       │
  │                                                                      │
  │  ⏎ next     Esc back                                                 │
  └──────────────────────────────────────────────────────────────────────┘
```

| Step | Question | Maps to |
|---|---|---|
| 1 | Which modes? `coding` / `studio` / `vstudio` / all three | `--mode` |
| 2 | Which optimization rule? | `--preference` |
| 3 | Activate the result, or keep it as a candidate? | default / `--no-activate` |
| 4 | Review | the composed command line |

Advanced items (`--target-ctx`, `--activate` for candidates measured earlier) live behind an
"advanced" toggle in step 3, and remain mutually exclusive by construction: if `--activate` is
chosen, steps 2 and `--target-ctx` are struck out on screen with the reason, rather than producing
an error later.

Step 4 does **not** duplicate the preflight. It shows the command, warns in one line that the real
preflight and confirmation come next and that the run can take a long time, and hands off. The user
then sees the genuine preflight and answers the genuine `Start calibration?` prompt — one
confirmation, from the code that owns the safety rules.

## 6.5 Diagnostics, records, settings

- **Diagnostics**: the snapshot in full, plus `[d] doctor`, `[v] validate`, `[e] engine status` as
  handoffs that return to the TUI.
- **Records**: per mode, the state (`active`, `candidate`, `absent`, `incompatible`, `stale`,
  `superseded`, `insufficient headroom`), the stored `ctx` and `n_cpu_moe`, the reserves, and the
  record path. Read-only. A `candidate` row offers `[a] activate` → composes
  `bora calibrate --mode <id> --activate`.
- **Settings**: **read-only**, and this is a design position, not a phase-one shortcut. The
  specification says the launcher never modifies the user's `config.toml` automatically. A TUI that
  writes it would break that rule; a TUI that writes it "only on explicit save" still needs a new
  normative decision, a diff preview, and a backup story. Show the resolved value, its source
  (`environment` / `config.toml` / `default`), the file path, and the environment variable names.
  Add `[o] open the config file in $EDITOR` if you want a shortcut — the user's editor writes the
  file, not bora.

## 6.6 Danger zone

```
  ┌─ Remove bora-workbench ──────────────────────────────────────────────┐
  │                                                                      │
  │  This deletes the managed roots:                                     │
  │    config   C:\Users\<you>\AppData\Roaming\bora-workbench            │
  │    data     …\Local\bora-workbench\data                              │
  │    cache    …\Local\bora-workbench\cache                             │
  │    state    …\Local\bora-workbench\state                             │
  │  and removes the uv-managed Python tool after the process exits.     │
  │                                                                      │
  │  It does NOT touch the Hugging Face cache or your weights.           │
  │  Local calibration records are inside data and will be lost.         │
  │  Services running: none                                              │
  │                                                                      │
  │  runs:  bora uninstall   (which asks for its own confirmation)       │
  │                                                                      │
  │  Type  remove  to continue:  [        ]        Esc cancel            │
  └──────────────────────────────────────────────────────────────────────┘
```

Typing a word, not pressing `y`, and then still meeting the real `uninstall` confirmation. Two
deliberate acts for the only irreversible command in the tool. And because it is a handoff, the TUI
process is gone before uv is asked to delete the installation the TUI was running from — a problem
the embedded design would have to solve for no benefit.

---

# Part VII — Contracts the TUI must not break

A checklist to review any TUI PR against:

1. Importing the package still performs no I/O, creates nothing, starts nothing. The TUI module is
   imported only when the command runs.
2. Exit codes stay `0 / 1 / 2 / 130`, produced by the same code as today; the TUI adds none.
3. No TTY → no TUI. Redirected output is untouched, and every existing command behaves identically
   whether or not the TUI exists.
4. `config.toml` is never written by bora.
5. No new network access, no telemetry, no upload — the TUI displays only what already lives on
   this machine, and displays record paths rather than shipping record contents anywhere.
6. Services still bind `127.0.0.1` only; the TUI starts no server of its own and opens no port.
7. Preflight and confirmation prompts are never re-implemented, pre-answered, suppressed, or
   auto-`--yes`-ed by the TUI.
8. Platform branching stays in the modules allowed to branch; terminal capability detection is not
   "platform logic" but should still be one small named helper, not scattered `if os.name` checks.
9. `600` lines per file, `40` per function, `3` parameters, `3` nesting levels, docstrings
   everywhere — `tests/test_code_quality.py` walks all of `src/`, so `tui/` is governed the moment
   it exists.
10. Documentation gains one page (`docs/tui.md`) and every other page keeps working, because
    nothing became TUI-only.

---

# Part VIII — Where the idea is weak

Answering your question directly, with what I would do about each.

**1. Two front ends, one truth.** The real long-term cost is drift: a rule changes in the CLI, the
TUI keeps showing the old story. *Mitigation:* the TUI owns no rules — snapshot in, argv out — and
one test asserts that every argv the composer can emit is accepted by the real parser.

**2. A TUI is the opposite of reproducible, and reproducibility is this project's whole thesis.**
Everything here is pinned, verified, checksummed and scriptable; "I clicked something and it
worked" is culturally foreign to it. *Mitigation:* P2, the always-visible command, and P3, nothing
is TUI-only. The TUI is a teaching surface for the CLI, not an alternative to it.

**3. Process lifetime.** The three modes are foreground processes ending at `Ctrl-C` with exit 130.
Hosting them inside a UI event loop puts the identity-safe stop, the state file, and the log
handling behind a second layer that has to get signals exactly right on two platforms. *Mitigation:*
handoff. This is the argument that decided §3.4.

**4. Hours-long calibration inside an alternate screen.** Screen blanking, a stray key, a resize
storm, or an SSH drop during a multi-hour run is a real risk, and the CLI already renders that run
well. *Mitigation:* handoff again. The TUI's contribution is choosing the flags correctly, which is
where users actually struggle.

**5. Self-deletion.** `uninstall` schedules removal of the very tool that is running. From a TUI
that is a foot-gun; via handoff it is a non-issue.

**6. Onboarding promises more than the tool delivers.** A wizard implies "I will set this up for
you", and bora deliberately does not fetch weights. A wizard that stalls at step 5 with a vague
error would feel broken. *Mitigation:* §6.2 — a verifying checklist that states the boundary and
hands over the exact revision to fetch.

**7. Settings screens invite writes.** The most natural next request after a settings pane is "let
me edit it here", which collides with a normative rule. *Mitigation:* read-only by design, with
`$EDITOR` as the escape hatch; changing that needs a decision, not a PR.

**8. Animation is a taste that fades.** A gust that delights on day one is a delay on day thirty,
and motion is an accessibility problem for some users. *Mitigation:* motion budget, instant
interruptibility, `BORA_TUI_MOTION=off`, `--plain`, never on the command path, and the wind settling
into stillness a few seconds after the home screen opens rather than looping forever.

**9. Screen readers.** Alternate-screen TUIs are hostile to them. *Mitigation:* the CLI remains the
complete, accessible path, and `docs/tui.md` says so explicitly instead of pretending the TUI is a
strict improvement.

**10. Windows terminal fragmentation.** Legacy `conhost` with a raster font will mangle the banner
and the sea. *Mitigation:* the degradation ladder, plus one manual check on Windows Terminal and on
legacy `conhost` before any release that ships it.

**11. Testing and CI.** UI snapshot tests are brittle and `AGENTS.md` demands deterministic,
offline, host-independent tests. *Mitigation:* keep logic out of the UI. Test the composer, the
snapshot, and the motion functions with a frozen clock and a seeded PRNG. Do not snapshot-test
pixels.

**12. Opportunity cost — the strongest objection.** Section 0 of the specification still lists open
`0.2` work: the Windows trial adapter validation, the post-release upgrade/uninstall verification,
and the `0.2.1` release CI. A TUI is a new surface on an unstable base, and `AGENTS.md` says to work
one step at a time and not anticipate later milestones. *Mitigation:* propose it as **Backlog D**,
land the reorganization (Part I) now because it helps regardless, and start the TUI only after the
open `0.2` items close.

**13. Bare `bora` becoming the TUI is a contract change.** Today it prints help
(`no_args_is_help=True`), and scripts and habits depend on that. *Mitigation:* ship `bora tui` as an
explicit command. Consider flipping the default only after the TUI has been used for a while, with
a TTY check and `BORA_NO_TUI` — or never, which would be a perfectly good outcome.

---

# Part IX — What could be better than what you described

- **Make the wind mean something, once.** Instead of decorating every screen, let the gust exist on
  the home screen and settle after ~3 seconds into a still header. The one place it may return is
  while a handoff child is running and the TUI is waiting — a slow drift that says "the machine is
  busy" without inventing a fake percentage.
- **Lead with the diagnosis, not the menu.** The most useful first line for a returning user is
  "*nothing is running, all three modes are on the baseline, the engine matches the lock*". Put the
  verdict above the navigation and most sessions end after reading one screen.
- **Make the composed command copyable.** `[y]` to copy the command line to the clipboard turns the
  TUI into a CLI cheat sheet that teaches the flags the docs describe.
- **Use the wizard to prevent the mistakes the CLI can only report.** `--activate` with
  `--target-ctx` is an input error today; in the wizard it should be unreachable, with the reason
  shown inline. That is a genuine improvement over the CLI, not a reskin of it.
- **A "what changed" line after each handoff returns.** On return, re-read the snapshot and show one
  line: "engine: not installed → b10011 CUDA active". It closes the loop the CLI cannot close.
- **Name the wind in the empty states.** "Nothing is running. Calm." is one word of personality in
  the place where personality costs nothing and no one is waiting.

---

# Part X — Staging

| Phase | Content | Approx. cost | Value if you stop here |
|---|---|---|---|
| **0** | Part I reorganization, no TUI | small, mechanical | Real: the tree becomes readable |
| **1** | `bora tui`: banner, gust, sea, snapshot dashboard, read-only, `q` to quit, Rich only | small–medium | The identity plus a genuinely useful overview |
| **2** | Navigation rail, modes and calibration wizards, composer, handoff | medium (dependency decision here) | The full concept as described |
| **3** | Onboarding checklist, records pane, danger zone | small | First-run experience |
| **4** | Polish: clipboard, `$EDITOR`, "what changed", help overlay | small | — |

Each phase ships independently and is useful alone. If phase 2 turns out to need Textual and the
dependency is refused, phase 1 still stands on its own.

**Acceptance for phase 1:** starts with no side effects, exits cleanly restoring the terminal,
renders correctly at 80×24 / 120×40 / 60×20, degrades to ASCII without UTF-8 and to a plain line
without a TTY, idles under the CPU budget, and does not slow `bora --version` by importing anything
new.

---

# Part XI — Decisions the maintainer has to take

These are **open questions, not decisions**. They are numbered `Q1`–`Q6` on purpose: a `D-0xx`
identifier belongs to the decision table of `IMPLEMENTATION_SPEC.md` and is assigned when the
maintainer actually decides something, so a proposal that hands itself `D-0xx` numbers either
collides with real decisions taken meanwhile or silently reserves a block it does not own. Answering
one of these questions is what creates its `D-0xx` entry, in the specification, with the next free
number at that moment.

| # | Question |
|---|---|
| Q1 | Is the package reorganization (Part I) approved as an independent, behavior-free step? |
| Q2 | Is an interactive front end accepted at all, as post-0.2 **Backlog D**? |
| Q3 | Handoff or embedded execution? (This proposal recommends handoff, §3.4.) |
| Q4 | Rich-only, or is `textual` an approved runtime dependency per the `AGENTS.md` procedure? |
| Q5 | Does bare `bora` stay `no_args_is_help`? (This proposal recommends yes, plus `bora tui`.) |
| Q6 | Is the settings pane read-only forever, or is a guarded writer a future decision? |

---

# Appendix — Alternatives considered and rejected

- **A full TUI that runs everything in-process.** Rejected: §3.4 and §VIII.3–5.
- **A splash animation on every command.** Rejected: it would put motion in the path of `doctor`,
  `status`, and scripts, for a novelty that decays.
- **A web UI for management.** Rejected: it would open a port, and the project's security posture is
  built on `127.0.0.1`-only services with a verified lifecycle.
- **A `--json` flag on `doctor` as the TUI's data source.** Rejected: it would make a public output
  contract out of an internal need. The snapshot (§3.2) is an in-process API; a JSON contract is a
  separate decision with its own compatibility obligations.
- **Reading the CLI's stdout to build the dashboard.** Rejected: scraping your own tool is how two
  front ends drift apart.
