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

## Screens

| Screen | Read-only information and choices |
|---|---|
| **Overview** | machine diagnosis, memory, engine, model receipt state, services, records, pi, validation, and deterministic next-step advice |
| **Modes** | the active calibrated cell or verified baseline for each mode, plus exact foreground launch commands |
| **Calibration** | active and candidate record states, plus a staged composer for measurement or candidate activation |
| **Setup** | engine compatibility and receipt-aware pinned-model state, plus existing install, pull, and removal commands |
| **Pi** | pi availability and the selected context-window source, plus valid current pi commands |
| **Settings** | resolved values, environment names, winning source, and config path; no editing |
| **This installation** | installed version, managed roots, update choices, and the exact uninstall boundary |

The published version is deliberately not fetched on opening. Select `bora update --check` when that
network request is wanted. Presence alone is not reported as model verification, and an absent local
calibration record is shown as a working but non-optimized baseline rather than a launch failure.

## Keys

| Key | Action |
|---|---|
| arrows or `j` / `k` | move through the seven screens |
| `Tab` / `Shift-Tab` | move through the selected screen's visible command choices |
| `Enter` | accept a wizard choice or select the exact marked command |
| `PageUp` / `PageDown` | scroll long detail without changing screens |
| `r` | request one serialized snapshot refresh |
| `?` | expand or collapse key help |
| `q`, `Ctrl-Q`, or `Esc` | quit; during review, cancel without running the command |

Selection and commands are marked in text, not by colour alone. At 60x20 the detail remains
scrollable; decorative motion is omitted below 80x24.

## Commands and handoff

Every selectable command is displayed before `Enter` can choose it:

| Screen | Composed current command | After success |
|---|---|---|
| Overview | `bora doctor`, `bora validate`, `bora status`, `bora engine status`, `bora stop` | return and refresh |
| Modes | `bora coding|studio|vstudio [--force]` | terminal; do not reopen |
| Calibration | `bora calibrate --mode ...` with only valid current options | terminal; do not reopen |
| Setup | `bora engine status`, `bora engine install [--force] [--no-model]`, `bora pull [qwen]`, `bora rm [qwen] [--keep-hf] [--dry-run]` | return and refresh |
| Pi | `bora pi [--print]`, `bora pi --install`, `bora pi remove`, `bora pi uninstall` | return and refresh |
| This installation | `bora update --check` | return and refresh |
| This installation | `bora update`, `bora uninstall` | terminal; do not reopen |

On selection, Textual ends first and restores the alternate screen, cursor, styles, input, and signal
handling. The displayed arguments then enter the existing recursive Click/Typer parser in the same
`bora` process. The real callback owns every preflight, prompt, network request, subprocess, write,
and exit code.

Returning actions reopen only after exit 0 and show concise differences between the before and after
snapshots. Exit 1, 2, or 130 propagates without reopening. Foreground modes, calibration, update, and
uninstall are terminal even after success. In particular, update and uninstall have no live TUI
parent holding the uv environment open while their deferred helper waits for the command process to
exit.

### Calibration review

The measurement route asks for mode, preference, activation behavior, and an optional approved
measurable context before showing the exact command. A valid pending candidate instead offers a
separate `bora calibrate --mode <id> --activate` route with no preference, target, or
`--no-activate`. The TUI answers none of the real calibration preflight or confirmation questions.

### Uninstall review

Selecting uninstall first requires typing `remove` exactly. This is only TUI friction: after the TUI
closes, `bora uninstall` still shows its scope and asks the real managed-root question. The confined
Hugging Face cache offer remains a second, separate question and still defaults to no.

## Optional motion

Normal presentation shows deterministic wind and sea decoration on the focused Overview only. It
updates at 8 fps, below the 12 fps ceiling, and removes its timer after about three active seconds.
It carries no status or action information.

`BORA_TUI_MOTION` accepts exactly:

| Value | Effect |
|---|---|
| `auto` | default; animate only when every capability permits it |
| `off` | retain normal static presentation with no animation timer |

An empty, differently cased, or unknown value exits 2. Motion is also disabled by `--plain`,
`NO_COLOR`, `TERM=dumb`, limited output encoding, a terminal smaller than 80x24, another screen, or
detectable terminal focus loss.

The accepted Ubuntu 120x40 pseudo-terminal observation is stored in
[`evidence/tui/ubuntu-motion.json`](../evidence/tui/ubuntu-motion.json). It is one local observation,
not a portable performance claim. The Windows motion CPU observation was not performed.

## Complete CLI path

No task requires this interface. [Commands](commands.md) documents every command and option
independently, and [Configuration and local data](configuration.md) documents the files and
presentation controls. Ignoring this page does not remove any product capability.
