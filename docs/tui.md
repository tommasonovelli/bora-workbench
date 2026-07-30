# Terminal workbench

Bare `bora` opens the read-mostly dashboard and exact command composer for the existing CLI. There
is no `tui` subcommand. The workbench is not a second launcher: every operation remains an explicit
scriptable `bora <command>`, and a selected action runs that same callback only after Textual has
restored the terminal.

## Opening it

```bash
bora
bora --plain
```

Both stdin and stdout must be interactive terminals. Redirected bare invocation exits with
invalid-input status 2 before Textual is imported; scripts should call an explicit command.
`--plain` is available only with bare `bora` and keeps every screen and action in a reduced
monochrome presentation. Use explicit CLI commands for redirection, screen readers, automation, or
whenever an alternate-screen interface is unsuitable.

Opening and refreshing are non-mutating and make no network request. The first static frame appears
before one worker collects the local snapshot. Collection may read configuration and local state,
inspect process identities, and run bounded read-only `nvidia-smi` and engine version/help probes.
It does not:

- hash model payloads or write verification receipts;
- create directories, repair or quarantine state, or rewrite configuration;
- start, stop, install, update, remove, or calibrate anything;
- query the newest published release;
- poll in the background.

A slow probe does not block navigation or quitting. Pressing `r` during collection queues at most
one follow-up refresh, so collectors never overlap. A failed collection is shown without a traceback
and prevents command selection until a later refresh succeeds.

## One visual identity

Every page retains the same close-set, entirely blue title:

```text
                              Bora Workbench
```

On a capable terminal, three wind rows frame the top and a layered sea frames the bottom. Every page
uses the same 6 fps continuous effect, including an open section, from one shared timer. Content
uses blue headings, labels, markers, commands, and borders against high-contrast white prose, while
the terminal's own background remains untouched. Colour never carries status by itself.

Home keeps its compact menu. Sections are centred at a wider responsive measure to reduce avoidable
wrapping, with separate bordered panels for actions, the exact command, and local facts. At narrow
sizes the same content scrolls rather than disappearing.

## The central menu

Home shows the machine identity, one deterministic next step, and seven summary rows:

```text
                         ▰  Bora Workbench  ▰
                   0.4.4 · AMD Ryzen 9 · 64.0 GiB · cuda

                       The pinned engine is not active.
                             bora engine install

     ╭──────────────────────────────────────────────────────────────╮
     │  ▸ Run                 verified baseline                     │
     │    Calibration         no active record                      │
     │    Setup               engine not active                     │
     │    Diagnostics         no blocking error                     │
     │    Pi                  not found on PATH                     │
     │    Settings            all defaults                          │
     │    This installation   version 0.4.4                         │
     ╰──────────────────────────────────────────────────────────────╯
```

`Enter` opens the marked entry and `Esc` returns, so the section and menu never own movement at the
same time.

| Entry | Read-only information and choices |
|---|---|
| **Run** | the three foreground experiences and the active cell or verified baseline each uses |
| **Calibration** | active/candidate record states and a staged valid-only command composer |
| **Setup** | engine compatibility and receipt-aware model state, with install/pull/removal actions |
| **Diagnostics** | memory, engine, model, services, records, pi, validation, and diagnostic actions |
| **Pi** | availability and context source, with the supported link/launch/removal actions |
| **Settings** | resolved values, environment names, winning source, and path; no editing |
| **This installation** | version, managed roots, update choices, and exact removal boundary |

The published version is not fetched on opening. Select `bora update --check` when that network
request is wanted. Presence alone is not model verification, and no active calibration record means
a working non-optimized baseline rather than a launch failure.

## Keys

| Key | Action |
|---|---|
| arrows or `j` / `k` | move the marker on the visible surface |
| `Enter` or `Right` | open, accept a wizard answer, or select the shown command |
| `Esc` or `Left` | return to home; on home, quit |
| a bracketed letter | switch that flag on the marked action |
| `PageUp` / `PageDown` | scroll long details |
| `r` | request one serialized snapshot refresh |
| `?` | expand or collapse key help |
| `q` or `Ctrl-Q` | quit without running anything |

Each action appears once. Its short explanation and flags update with the marker, and the command
panel always shows exactly what `Enter` would select:

```text
╭──────────────────────────────────────────────────────────────────╮
│ ▸ install or repair engine                                      │
│   download pinned model                                         │
│   remove pinned model                                           │
│   inspect engine compatibility                                  │
│                                                                  │
│ About  Install the locked build and, by default, the model.      │
│ Flags  [f] force on   [n] no-model off                           │
╰──────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────────────────────────────────╮
│ Command  bora engine install --force                             │
╰──────────────────────────────────────────────────────────────────╯
```

Action, flag, and command state remain text-visible without colour.

## Commands and handoff

| Section | Composed command | After success |
|---|---|---|
| Run | `bora coding|studio|vstudio [--force]` | terminal; do not reopen |
| Calibration | `bora calibrate --mode ...` with valid current options | terminal; do not reopen |
| Setup | engine status/install, `pull`, and `rm` forms | wait for Enter, then refresh |
| Diagnostics | doctor, validate, status, engine status, and stop | wait for Enter, then refresh |
| Pi | `bora pi launch` | terminal; do not reopen |
| Pi | link/print/install/remove/uninstall forms | wait for Enter, then refresh |
| This installation | `bora update --check` | wait for Enter, then refresh |
| This installation | `bora update` and `bora uninstall` | terminal; do not reopen |

The workbench omits the optional `qwen` handle from `pull` and `rm`, because this distribution pins
one model and the bare forms do the same work. The handle remains valid on the explicit CLI.

On selection, Textual first restores the alternate screen, cursor, input, styles, and signals. The
visible arguments then enter the existing recursive Click/Typer parser in the same process. The real
callback owns every preflight, prompt, subprocess, network request, write, and exit code.

After a successful returning callback, the restored terminal displays
`Press Enter to return to Bora Workbench.` The output stays readable until acknowledgement; only
then does Textual reopen and recollect. Diagnostics lists concise before/after changes. Exit 1, 2,
or 130 propagates without reopening. Foreground modes, calibration, update, and uninstall remain
terminal, so no TUI parent can hold the uv environment during deferred replacement or removal.

### Calibration review

The wizard asks for mode, preference, activation behavior, and an optional approved measurable
context before showing the exact command. A valid pending candidate instead offers
`bora calibrate --mode <id> --activate`, with no preference, target, or `--no-activate`. The
workbench answers none of the real preflight or confirmation questions.

### Uninstall review

Selecting uninstall first requires typing `remove` exactly. While that field has focus, printable
keys go into it instead of triggering shortcuts. This is only workbench friction: the restored CLI
still shows scope and asks its independent managed-root question, then separately offers confined
Hugging Face cache removal with a default of no.

## Optional motion

`BORA_TUI_MOTION` accepts exactly:

| Value | Effect |
|---|---|
| `auto` | animate every page, home and sections alike, when every capability permits |
| `off` | retain static title/wind/sea graphics with no animation timer |

Unknown, empty, or differently cased values exit 2. Plain mode, `NO_COLOR`, `TERM=dumb`, limited
encoding, a terminal below 80x24, or detectable focus loss hides the bands and owns no timer.
Unmount always releases the timer. Decoration communicates no status or action.

Moving between the menu and a section neither restarts nor duplicates the timer, and time spent with
motion stopped is not counted, so the graphic resumes where it left off rather than jumping.

[`evidence/tui/ubuntu-motion.json`](../evidence/tui/ubuntu-motion.json) measured the superseded finite
8 fps implementation, not the current continuous 6 fps effect, which now also runs while a section is
read. A new Ubuntu observation and Windows visual/CPU checks remain unavailable follow-up work, not
passed checks.

## Complete CLI path

No task requires the alternate screen. [Commands](commands.md) documents every explicit command and
option independently; the complete product remains accessible and scriptable without the workbench.
