# Terminal workbench

`bora tui` is an optional, read-mostly dashboard and exact command composer for the existing CLI. It
is not a second launcher: every operation remains available as a documented `bora` command, and the
TUI runs the same callback only after restoring the terminal.

## Opening it

```bash
bora tui
bora tui --plain
```

Both stdin and stdout must be interactive terminals. Redirected invocation exits with invalid-input
status 2 before Textual is imported. `--plain` keeps the same screens and actions but uses the
reduced monochrome presentation. Use the normal CLI for scripts, redirected output, screen readers,
or whenever an alternate-screen interface is unsuitable.

Opening and refreshing are non-mutating and make no network request. The first static frame appears
before one worker collects the local snapshot. Collection may read configuration and local state,
inspect process identities, and run bounded read-only `nvidia-smi` and engine version/help probes.
It does not:

- hash the model payload or write its verification receipt;
- create directories, repair or quarantine service state, or rewrite configuration;
- start, stop, install, update, remove, or calibrate anything;
- query the newest published release;
- poll in the background.

A slow probe does not block navigation or quitting. Pressing `r` during collection queues at most one
follow-up refresh, so collectors never overlap. A failed collection is shown as current diagnostic
text without a traceback and prevents command selection until a later refresh succeeds.

## The central menu

Opening the workbench shows one screen: the identity, the single deterministic next step, and a
central menu. The workbench draws on the terminal's own background, so it inherits the colours of
the surrounding shell instead of painting a window inside it.

Each menu row carries a one-line summary of that area, so the state of the machine is readable
without opening anything:

```text
                        B O R A   W O R K B E N C H
                     0.4.1 · AMD Ryzen 9 · 64.0 GiB · cuda

                       The pinned engine is not active.
                             bora engine install

     ╭──────────────────────────────────────────────────────────────╮
     │  ▸ Run                 verified baseline                     │
     │    Calibration         no active record                      │
     │    Setup               engine not active                     │
     │    Diagnostics         no blocking error                     │
     │    Pi                  not found on PATH                     │
     │    Settings            all defaults                          │
     │    This installation   version 0.4.1                         │
     ╰──────────────────────────────────────────────────────────────╯
```

`Enter` opens the marked entry as a full window and `Esc` returns to the menu, so a section is never
navigated at the same time as the menu.

| Entry | Read-only information and choices |
|---|---|
| **Run** | the three foreground modes with the active calibrated cell or verified baseline each would use |
| **Calibration** | active and candidate record states, plus a staged composer for measurement or candidate activation |
| **Setup** | engine compatibility and receipt-aware pinned-model state, plus existing install, pull, and removal commands |
| **Diagnostics** | the full local report — memory, engine, model receipt state, services, records, pi, validation — and the returning diagnostic commands |
| **Pi** | pi availability and the selected context-window source, plus valid current pi commands |
| **Settings** | resolved values, environment names, winning source, and config path; no editing |
| **This installation** | installed version, managed roots, update choices, and the exact uninstall boundary |

The published version is deliberately not fetched on opening. Select `bora update --check` when that
network request is wanted. Presence alone is not reported as model verification, and an absent local
calibration record is shown as a working but non-optimized baseline rather than a launch failure.

## Keys

| Key | Action |
|---|---|
| arrows or `j` / `k` | move the marker of whichever surface is open |
| `Enter` or `Right` | open the marked entry, accept a wizard answer, or select the exact shown command |
| `Esc` or `Left` | return to the central menu; on the menu it quits |
| a bracketed letter | switch that flag of the marked action, for example `f` for `--force` |
| `PageUp` / `PageDown` | scroll long detail without leaving the section |
| `r` | request one serialized snapshot refresh |
| `?` | expand or collapse key help |
| `q` or `Ctrl-Q` | quit without running anything |

A section shows a short list of actions rather than one row per flag combination. The flags of the
marked action appear as toggles under it, and the exact command below them changes as they are
switched:

```text
  ▸ install engine
    download pinned model
    remove pinned model
    engine status

    [f] force on   [n] no-model off

  bora engine install --force
```

Each action keeps its own flags while the marker visits another action. Selection, flag state, and
commands are all marked in text, never by colour alone. At 60x20 the detail remains scrollable;
decorative motion is omitted below 80x24.

## Commands and handoff

Every selectable command is displayed before `Enter` can choose it:

| Section | Composed current command | After success |
|---|---|---|
| Run | `bora coding|studio|vstudio [--force]` | terminal; do not reopen |
| Calibration | `bora calibrate --mode ...` with only valid current options | terminal; do not reopen |
| Setup | `bora engine status`, `bora engine install [--force] [--no-model]`, `bora pull`, `bora rm [--keep-hf] [--dry-run]` | return and refresh |
| Diagnostics | `bora doctor`, `bora validate`, `bora status`, `bora engine status`, `bora stop` | return and refresh |
| Pi | `bora pi launch` | terminal; do not reopen |
| Pi | `bora pi [--print]`, `bora pi --install`, `bora pi remove`, `bora pi uninstall` | return and refresh |
| This installation | `bora update --check` | return and refresh |
| This installation | `bora update`, `bora uninstall` | terminal; do not reopen |

The workbench composes `bora pull` and `bora rm` without the optional `qwen` handle, because this
distribution pins exactly one model and the bare form does the same work. The handle remains valid
on the command line.

On selection, Textual ends first and restores the alternate screen, cursor, styles, input, and signal
handling. The displayed arguments then enter the existing recursive Click/Typer parser in the same
`bora` process. The real callback owns every preflight, prompt, network request, subprocess, write,
and exit code.

Returning actions reopen only after exit 0. The status line then counts the differences between the
before and after snapshots, and Diagnostics lists them above the local report. Exit 1, 2, or 130
propagates without reopening. Foreground modes, calibration, update, and
uninstall are terminal even after success. In particular, update and uninstall have no live TUI
parent holding the uv environment open while their deferred helper waits for the command process to
exit.

### Calibration review

The measurement route asks for mode, preference, activation behavior, and an optional approved
measurable context before showing the exact command. A valid pending candidate instead offers a
separate `bora calibrate --mode <id> --activate` route with no preference, target, or
`--no-activate`. The TUI answers none of the real calibration preflight or confirmation questions.

### Uninstall review

Selecting uninstall first requires typing `remove` exactly. While that phrase field has focus, the
single-letter keys stop acting as shortcuts and go into the field. This is only TUI friction: after
the TUI closes, `bora uninstall` still shows its scope and asks the real managed-root question. The
confined Hugging Face cache offer remains a second, separate question and still defaults to no.

## Optional motion

Normal presentation frames the central menu with deterministic, continuously moving decoration.
Three wind rows carry sparse `·`, `╌`, `╍`, and `━` ribbons through several sky colours. Beneath the
menu, one fractional-block wave surface (`▁` through `█`) sits over two shaded/full-cell water layers
with independently travelling currents and occasional bright foam. The effect runs at 6 fps while
the home remains focused, below the 12 fps ceiling. It carries no status or action information.

`BORA_TUI_MOTION` accepts exactly:

| Value | Effect |
|---|---|
| `auto` | default; animate only when every capability permits it |
| `off` | retain normal static presentation with no animation timer |

An empty, differently cased, or unknown value exits 2. Motion is also disabled by `--plain`,
`NO_COLOR`, `TERM=dumb`, limited output encoding, a terminal smaller than 80x24, an open section, or
detectable terminal focus loss. Any of those runtime switches removes the timer and both bands; the
timer is also released on unmount.

[`evidence/tui/ubuntu-motion.json`](../evidence/tui/ubuntu-motion.json) measured the superseded
finite 8 fps effect and remains historical evidence for that implementation only. It is not a CPU
measurement of the current continuous 6 fps decoration. A new Ubuntu observation and the Windows
visual/CPU checks have not been performed.

## Complete CLI path

No task requires this interface. [Commands](commands.md) documents every command and option
independently, and [Configuration and local data](configuration.md) documents the files and
presentation controls. Ignoring this page does not remove any product capability.
