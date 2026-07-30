# Releasing and publication

This page describes the current GitHub-only process. Creating or modifying remote resources always
requires explicit human authorization for the push, tag, and GitHub Release.

## Public status

- release described by this branch: `bora-workbench 0.4.4`;
- preceding public version: `bora-workbench 0.4.3` on GitHub Releases;
- historical versions `0.1.0` through `0.1.6` remain immutable under their original
  `qwen-launcher` artifact identity;
- every published bundle comes from its green Ubuntu/Windows release workflow and contains the
  wheel, sdist, both installers, and `SHA256SUMS`;
- D-070 limits current and future publication to GitHub Releases until the maintainer makes a new
  explicit decision;
- calibration coverage remains `GATE-PARTIAL`; no local candidate is activated and no omitted
  platform or hardware run is described as a passed Gate.

Historical sections below name protocol versions and registry decisions that applied to those
artifacts. They preserve the record; they do not describe the current CLI or publication path.
Published artifacts are immutable and are never rebuilt, replaced, or re-uploaded under the same
version.

To install the release, see [Installation](installation.md).

## Preparing a version

Start from a clean checkout and the required uv version:

```bash
git status --short
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
```

Delete `dist/` before the build, then:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
uv run --frozen python scripts/verify_uninstall.py
```

Check:

- the version in `pyproject.toml` and the metadata;
- the changelog and documentation, with no references to an earlier state;
- installers consistent with the version, uv, and Python;
- a single wheel and sdist in `dist/`;
- the required resources, notices, and documents present;
- SHA-256 computed on the final bytes;
- no generated or private file in the commit.

Any change made after the build invalidates the artifacts: remove `dist/`, repeat every check, and
rebuild.

### Release 0.4.4

`0.4.4` distributes D-093 and changes only optional TUI motion.

`0.4.3` animated the wind and sea on the central menu and froze them the moment a section opened, so
the identity that every page shares stopped moving on six of seven pages. One 6 fps timer now serves
whichever page is visible, still under the 12 fps ceiling. Opening or leaving a section keeps that
same timer instead of freezing, restarting, or duplicating it, and elapsed animation time still
excludes every stopped period, so the graphic resumes instead of jumping forward.

Every kill switch is unchanged and is now the only route to a static frame: `BORA_TUI_MOTION=off`
renders one deterministic frame with no timer, while root `--plain`, `NO_COLOR`, `TERM=dumb`, limited
encoding, a terminal below 80x24, focus loss, and unmount hide the bands or release the timer. The
frame functions remain pure in time, dimensions, and seed, and decoration still carries no status.

Nothing else moves. The snapshot boundary, command composition, same-process handoff, output
acknowledgement, exit codes, engine, model, calibration protocol, record format,
`command_contract_sha256`, reserves, and candidate lifecycle are unchanged, so existing
`calibration-record/v6` files remain valid.

Release checks for this version are the complete frozen local suite, packaged-content validation,
build, isolated wheel verification, complete uv-tool uninstall, diff inspection, and the green tagged
Ubuntu/Windows workflow. Because motion now runs while a section is read, its cost is no longer
bounded by staying on the central menu; the manual visual and one-core CPU observation on Ubuntu and
Windows remains unavailable follow-up verification, not a passed check or a Gate, and
`evidence/tui/ubuntu-motion.json` still measures the superseded finite 8 fps effect. D-093 authorizes
the finalization commit, push to `main`, and tag `v0.4.4` after the local checks pass; the GitHub
Release is authorized only after that tag's workflow is green and only from its exact
`bora-workbench-release-bundle`. Publication remains GitHub Releases only, no candidate is activated,
and coverage remains `GATE-PARTIAL`.

### Release 0.4.3

`0.4.3` distributes D-092's unified workbench entry, presentation, and readable returning-command
handoff. Bare `bora` is now the sole dashboard entry and `bora tui` is removed; reduced presentation
moves to root `bora --plain`, while every explicit subcommand remains available for scripts and
redirection.

Every surface shares one close-set blue `Bora Workbench` title and the existing wind/sea identity.
Home continues to animate at 6 fps; sections freeze and retain the current frame with no timer, and
`BORA_TUI_MOTION=off` renders a deterministic static frame. Plain, encoding, size, focus, and
unmount switches remain. Sections are centred at a wider responsive measure than home and use
separate blue-bordered action, command, and detail panels. Blue labels and bold commands structure
high-contrast white prose, each action gains concise guidance, and the shared Rich CLI palette uses
the same blue/white identity while keeping warning and error text explicit.

The same-process handoff remains exact. After a successful returning callback, the restored terminal
now waits for Enter before Textual reopens, so report-only output remains visible. Terminal actions,
non-zero exits, preflights, confirmations, writes, network, and callback ownership are unchanged.

D-092 authorizes the finalization commit, push, and `v0.4.3` tag after the complete frozen suite,
packaged validation, build, isolated wheel/uninstall checks, and diff inspection pass. The GitHub
Release is authorized only after the tag's Ubuntu/Windows workflow is green and only from its exact
`bora-workbench-release-bundle`. Current manual visual/CPU, real foreground, and Windows terminal
observations remain unavailable follow-up checks, not passed checks or a Gate. The engine, model,
calibration protocol, record format, command contract, reserves, and candidate lifecycle are
unchanged; no candidate is activated, coverage remains `GATE-PARTIAL`, publication remains GitHub
Releases only, and no registry upload is authorized.

### Release 0.4.2

`0.4.2` distributes the direct pi launch and richer home identity requested in D-090 and authorized
for release by D-091.

`bora pi launch` locates pi on PATH and invokes it without a shell as
`pi --provider bora --model "Qwen 3.6"`; the id comes from `model_alias_contract.alias` in the
packaged engine lock. The child inherits the current directory and terminal. The command neither
starts `bora coding`, nor installs pi, nor writes `models.json`, so connecting the provider and
starting the local service remain explicit separate steps. An absent executable and ordinary child
failure map to operational exit 1; interruption maps to 130. The same command is available as a
terminal Pi action after Textual has restored the terminal.

The central menu keeps the terminal's own background but gains a multitone block-capped brand,
three rows of continuously travelling Unicode wind, and a three-layer fractional/shaded/full-block
sea with separate foreground gradients for ribbons, waves, foam, and depth. Motion updates at 6 fps
while the home remains focused instead of settling after three seconds. It remains below the 12 fps
ceiling and still stops immediately on an open section, focus loss, a small terminal, plain or
limited-colour/encoding presentation, `BORA_TUI_MOTION=off`, or unmount. Hidden and disabled motion
has no timer, and decoration carries no status or action meaning.

Release checks for this version are the complete frozen local suite, packaged-content validation,
build, isolated wheel verification, complete uv-tool uninstall, and the green tagged Ubuntu/Windows
workflow. D-087's CPU evidence measured the superseded finite 8 fps effect and is not reused for the
continuous timer. A new manual Ubuntu visual/CPU observation, every Windows visual/CPU check, and a
real `bora pi launch` remain follow-up verification; D-091 waives them for publication without
calling them passed or a Gate. The engine release, model identity, calibration protocol, record
format, command contract, `command_contract_sha256`, reserves, policy, and schemas are unchanged, so
existing `calibration-record/v6` files remain valid. No local candidate is activated, calibration
coverage remains `GATE-PARTIAL`, and publication remains GitHub Releases only. D-091 authorizes the
finalization commit, push, and `v0.4.2` tag after local checks pass, and the GitHub Release only from
the exact bundle of the green tag workflow.

### Release 0.4.1

`0.4.1` redesigns the presentation of `bora tui` and changes nothing else (D-089).

`0.4.0` shipped a dashboard that painted its own background inside the terminal, moved between
screens with the arrows while moving between a screen's actions with `Tab`, and listed one menu row
per flag combination. Two markers had to be tracked at once, `Setup` showed twenty rows for four
operations, and the explanatory text was long enough that it stopped being read.

The workbench now requests the terminal's default background, so the surrounding theme shows through
and colour is spent only on the brand, the selection marker, and the composed command. It opens on
one central menu, `Run` first, whose seven rows each carry a one-line summary derived from the
snapshot; `Enter` opens an entry as a full window and `Esc` returns, so one marker moves at a time
and `Tab` is unbound. A section lists its actions once and switches the marked action's optional
flags in place, each bound to the single letter shown beside it, so every reachable argv stays
available without a row per combination. Optional decoration follows the layout: two wind gusts
anchor the top corners with the long side alternating between their rows, and two sea rows sit under
the menu.

The read-only boundary, the non-mutating snapshot, the post-teardown same-process handoff, the
returning and terminal dispositions, the calibration wizard's valid-only combinations, and the
motion budget of D-084–D-087 are unchanged. Two defects are fixed: the motion timer is released when
Textual unmounts the tree, so no scheduled frame can outlive the widgets it draws into, and every
single-letter binding is released to the uninstall phrase field while it has focus. The TUI composes
`bora pull` and `bora rm` without the optional `qwen` handle, which the CLI still accepts.

Release checks for this version: the local suite, build, wheel and uninstall verification, and
pseudo-terminal runs at 60x20, 80x24, and 100x32 in plain and full presentation, each entering and
leaving the alternate screen, exiting 0, and emitting no explicit background colour and no traceback.
These are programmatic checks, not manual visual checks; no Windows terminal check was performed and
neither is a passed Gate. The engine release, model identity, calibration protocol, record format,
command contract, `command_contract_sha256`, reserves, policy, and schemas are unchanged, so existing
`calibration-record/v6` files remain valid. No local candidate is activated, calibration coverage
remains `GATE-PARTIAL`, and publication remains GitHub Releases only. D-089 authorizes the
finalization, push, and `v0.4.1` tag after the complete local suite is green. The GitHub Release is
authorized only after that tag's Ubuntu/Windows release workflow succeeds and must use its exact
bundle.

### Release 0.4.0

`0.4.0` adds the optional `bora tui` terminal workbench authorized by D-083–D-088. Seven
read-only screens present one structured local snapshot, deterministic advice, configuration
provenance, exact current commands, and a staged calibration composer. Textual always exits and
restores the terminal before the existing Click/Typer callback owns prompts, network, writes,
foreground processes, and exit codes. Returning success recollects; modes, calibration, update, and
uninstall never reopen. Bare `bora`, every existing command name, the flat core package tree, and the
read-only settings boundary stay unchanged.

Textual `8.2.8` is frozen under D-086. Optional 8 fps wind/sea decoration carries no information,
settles after about three active seconds, and has explicit accessibility, size, focus, terminal, and
environment kill switches. The Ubuntu motion observation and its limits are in
`evidence/tui/ubuntu-motion.json`.

Available Ubuntu acceptance used isolated pseudo-terminals at 60x20 and 120x40 in plain and full
modes. Navigation, explicit refresh, help, quit, alternate-screen exit, zero isolated-root writes,
and no traceback were observed; a real `doctor` returned and reopened the TUI, while a selected
`coding` command reached its terminal preflight and exited 1 without reopening because the isolated
roots had no engine or model. These are programmatic pseudo-terminal checks, not manual visual
checks. A real foreground model process and its `Ctrl-C` restoration were unavailable, and Windows
TUI checks were not performed under D-087. The raw scope is recorded in
`evidence/tui/ubuntu-acceptance.json`; none of the unavailable checks is called passed.

The engine release, model identity, calibration protocol, record format, command contract,
`command_contract_sha256`, reserves, policy, and schemas are unchanged, so existing
`calibration-record/v6` files remain valid. No local candidate is activated, calibration coverage
remains `GATE-PARTIAL`, and publication remains GitHub Releases only. D-088 authorizes the
finalization, push, and `v0.4.0` tag after the complete local suite is green. The GitHub Release is
authorized only after that tag's Ubuntu/Windows release workflow succeeds and must use its exact
bundle.

### Release 0.3.2

`0.3.2` finishes the pi handoff, after using it on a real machine (D-082).

The connection reported `ctx=8192` whatever the machine was serving. The window came from the local
`coding` record, and reusing that record also weighs the free memory a running service is holding,
so connecting during a session — the only moment the connection is useful — always fell back to the
baseline. The window is now taken from the service that is actually listening on the configured
port, then from the active record, then from the baseline, and the command names which of the three
answered and prints the reason when it is the last one. A calibration that activates a `coding`
record also names the command that applies its new window, because the entry is a copy that nothing
rewrites on its own.

Both writes into pi's world can now be taken back: `bora pi remove` for the provider entry,
`bora pi uninstall` for the package, as two consents that do not imply each other.

Release checks for this version: the npm removal itself was never executed on either platform, and
`bora pi` was exercised on Windows only, against an isolated home and state root. Neither is a
passed Gate. The engine, model, command contract, `command_contract_sha256`, record format,
reserves, and the packaged policy and schemas are unchanged, so every existing
`calibration-record/v6` stays valid and no local candidate is activated.

### Release 0.3.1

`0.3.1` finishes what `0.3.0` started, after using it on a real machine.

Removing the pinned artifacts left the cached repository behind as a stub whose `refs` still named
a revision whose files no longer existed, so a clean removal was not actually clean; the repository
now goes with its last snapshot, while a surviving revision keeps everything and another tool's
repository is still never examined. `pull` and `rm` accept the pinned model by name, so
`bora pull qwen` reads the way the command is meant to read. The suite also stopped writing
temporary paths into the verification receipt of whatever machine ran it.

### Release 0.3.0

`0.3.0` makes the launcher own the model it was already verifying (D-078/D-079/D-080/D-081).

Until now the weights had to be acquired by hand before anything worked, and could not be removed
by the tool that depended on them. `pull` downloads the locked artifacts into a managed store,
`engine install` does it in the same run, and `rm` gives the disk space back. Removal reaches the
shared Hugging Face cache too, but only for the pinned artifacts of the locked repository and only
behind a confirmation asked separately from every other one; writing into that cache stays
forbidden. The API now reports the model as `Qwen 3.6`, declared outside `command_contract` so that
`command_contract_sha256` — and therefore every existing calibration record — is unchanged. `bora pi`
connects the pi coding agent to the running service in one command.

Release checks for this version: the three symlink tests of `test_engine_assets` and
`test_engine_install` require a host that grants the symlink privilege, which a plain Windows
account does not; they must be green on the Ubuntu job. The manual Ubuntu run of `pull`, `rm`, and
`pi` is follow-up verification, not a passed Gate.

### Release 0.2.4

`0.2.4` makes calibration and startup stop paying for work no decision reads (D-074/D-075/D-076).

Three costs were removed. A paired confirmation round ran the full quick-bench, including the pinned
23180-token long request, four to six times per confirmation, while comparing only the median short
latency and the dispersion of that same triple. A `max-context` search walked the whole context
ladder although it selects the largest feasible context and compares rivals only within it. And the
model's SHA-256 was recomputed on every `calibrate` and every mode launch — 21.11 GiB, plus 0.84 GiB
of projector for a vision mode — silently, before any output.

None of this changes what is measured or recorded. The confirmed cell is still the sample the search
measured with a full quick-bench, so its `prefill_tps` is real; the same fresh processes still run in
the same `A→B`/`B→A` order under the same third-round rule; the final gate is untouched. The locked
filename and byte size are still checked on every resolution, and only a receipt matching path, size,
modification time, and the expected digest can skip the hash. Model resolution now writes that
receipt under the cache root, best-effort, so section 5.8 no longer calls it write-free.

The engine, model, command contract, `command_contract_sha256`, record format, reserves, and the
packaged policy and schemas are unchanged, so an existing `calibration-record/v6` stays valid and no
local candidate is activated. D-077 authorizes this release. The manual Ubuntu and Windows runs are
follow-up verification, not a passed Gate.

### Release 0.2.3

`0.2.3` adds `bora update` (D-073). Until now the only way to move to a new version was to repeat
the whole manual install: download the wheel, download `SHA256SUMS`, verify both by hand, and run
the installer. The command does exactly that and nothing more — newest published release, verified
wheel, `uv tool install --force` — so it inherits the existing trust boundary instead of adding
one. It never downgrades, and it never runs while a managed service is live.

The managed engine is deliberately outside the update. It lives under the data root and survives
the tool replacement, so the command does not reinstall or reactivate it; it reads `engine.lock`
out of the downloaded wheel and reports whether `bora engine install` is required afterwards.
Calibration records, the configuration, and the model are equally untouched, so an existing
`calibration-record/v6` stays valid.

The uv handoff that `uninstall` already used is generalized to any uv command, because Windows
cannot replace the environment of the process that is still running. That is also why the exit code
reports a scheduled installation rather than a completed one.

The engine, model, command contract, `command_contract_sha256`, record format, reserves, and the
packaged policy and schemas are unchanged. The real update path between two published releases is
follow-up verification on Ubuntu and Windows, not a passed Gate.

### Release 0.2.2

`0.2.2` exists because calibration could not finish on Windows (D-071). A real CUDA run on an
RTX 2060 SUPER 8 GiB hit three defects in a row, none of them a measurement: a redirected progress
line that a legacy code page could not encode and that ended the run, a permanent HTTP `400`
classified as retryable, and a pinned quick-bench long request of 23180 prompt tokens that the two
lowest context steps can never hold. Two further rules made a Windows desktop hostile to the
protocol: an immutable GPU compute-context population that no WDDM host can offer, and trial
servers registered where `status` and `stop` could not see them. After the fixes the same host
completed a `coding` run and wrote a valid candidate at `ctx=32768`, `n_cpu_moe=33`.

The engine, model, command contract, `command_contract_sha256`, record format, reserves, and the
packaged policy and schemas are unchanged, so existing `calibration-record/v6` records stay valid.
The VRAM reserve deliberately stays at `0.5` GiB (D-072). Automatic runs and `--target-ctx` no
longer accept `16384` or `8192`; CPU calibration confirms `32768` instead of `8192`.

### Release 0.2.1

`0.2.1` records D-070 and makes distribution exclusively GitHub-based. The registry publication
job, manual publication dispatch, OIDC permission, and registry installer options are removed. The
README and installation guide use copy-ready Ubuntu and Windows commands that verify the release
wheel and installer against `SHA256SUMS`.

This release does not change the engine, model, calibration search, record format, or candidate
state. Manual Ubuntu/Windows hardware runs are waived by the maintainer; the automated release
matrix remains required and the waiver is not a passed Gate.

### Release 0.2.0

`0.2.0` is the repository, distribution, package, command, and managed-root rename from
`qwen-launcher` to `bora-workbench`. It also replaces the three stored calibration envelopes with
one selected preference cell per mode. The public GitHub artifacts remain immutable; `0.2.1`
contains the later distribution-policy and installation-documentation changes.

### Release 0.1.6

`0.1.6` exists because calibration finally works. `0.1.5` had recorded that the three-envelope
search did not run at all (D-066): four defects made every attempt fail, two of them in the shared
process lifecycle that ordinary launches use as well. This release fixes them, and a full hardware
run then exposed two more failures that no offline test could reach, both caused by a memory
boundary that moves on a nearly full GPU.

With one protocol working, the redundant ones are removed: the gate-only laboratory, the
paired-search protocol, the `--protocol` option, `validate --path`, the `calibration-record/v2`-`/v4`
formats and their schemas, and the repository-only cross-context spike package. `calibrate` is one
command with `--preference`, `--target-ctx`, `--activate`, and `--no-activate`.

This is a breaking change for local state: a record written by `0.1.5` or earlier is diagnosed as
superseded rather than migrated, so re-run `calibrate` after upgrading. Nothing else moves — the
engine, the model, the command contract, and `command_contract_sha256` are unchanged.

Validated on hardware on Ubuntu (RTX 2060 SUPER 8 GiB): the shared `coding`+`studio` group completed
its search, its pairing, and six envelope gates; a separate `vstudio` run completed 44 trials in 61
minutes and wrote a valid candidate record whose three envelopes all passed smoke, multi-turn, and
the vision gate. Windows validation on hardware is still open; the offline suite runs on both
platforms in CI.

### Release 0.1.5

`0.1.5` translates the whole repository into English and republishes the calibration evidence with a
regenerated digest chain (D-065). It changes no runtime behavior: the engine, model, and command
contracts, `calibration/v5` as the default, and opt-in `calibration/v6-lite` all carry over
unchanged, and `command_contract_sha256` does not move.

The release exists because translating the checksum-bound evidence changed its bytes: the
`gate.md`/`protocol.md` digests, the report's `source_references`, the report digest inside the
policy, and `SHA256SUMS` were all recomputed, so the artifacts published for `0.1.0`–`0.1.4` no
longer match the branch. `0.1.5` is what realigns them; no earlier artifact was rebuilt or replaced.

Two measurement inputs deliberately keep their original Italian text, because translating them would
change what is measured rather than how it is described: the byte-pinned benchmark payloads and the
mirroring prompt constant in `scripts/spike_ctx/quick.py`.

### Release 0.1.4

`0.1.4` distributes `calibration/v6-lite` as an opt-in protocol (D-063/D-064): a hard `mode/v2`
migration, a production quick-bench, the `_calibration_v6_*` engine, `calibration-record/v5` records,
the `--protocol v6 --preference` CLI, and v5 reuse/`doctor`. `calibration/v5` remains the default;
promoting v6 to the default remains conditional on a human GO verdict from the cross-context spike.
The logic is tested offline with fakes. The claim that the real trial adapter had been validated on
hardware was premature: it has not, and `--protocol v6` does not work yet (corrected in 0.1.5 by
D-066). The maintainer authorized the commit, push, tag, and GitHub Release; PyPI
remains excluded.

### Release 0.1.3

`0.1.3` distributes D-058–D-061: correct precedence for cleanup errors, separate VRAM causes, an
additive taxonomy for spike/v6, MTP conservatively disabled for `vstudio`, and the repository-only
cross-context spike package in the sdist. `calibration/v5` remains the default; `mode/v2`, the
production quick-bench, the v6 engine, and v5 records are not present.

On 24 July 2026 the maintainer authorized the commit, push, tag, and GitHub Release before the local
spike runs, which remain post-release and are not declared a passed Gate. Phase 2 remains blocked
until a committed human `GO` verdict. PyPI and the activation of the candidates remain excluded.

### Release 0.1.2

`0.1.2` includes `calibration/v5`, the calibrated parameters in `doctor`, the shared Rich
presentation with literal dynamic values, the real percentage of the Ubuntu CUDA build, the pinned
Node 24 actions, and the automatic removal of the current `uv tool` installation.

On 23 July 2026 the maintainer decided `RELEASE` and authorized the commit, push, tag, and GitHub
Release, explicitly waiving a repeated manual cross-platform Gate beforehand. This does not amount
to a passed Gate: a real upgrade from `0.1.1`, v5 calibration, and complete paths on clean machines
remain post-release verifications. PyPI is excluded and the three local candidates remain inactive.

## Release candidate and human gate

A release candidate is prepared locally without tags or uploads. Before finalization the maintainer
tests at least:

- a clean installation on Ubuntu 22.04+ and Windows 11;
- `--version`, `validate`, `doctor`, and `engine status`;
- installing or resolving the engine;
- `coding`, `studio`, `vstudio`, and a clean stop;
- behavior with and without a local record;
- calibration and reuse when the change concerns them;
- a confined uninstall and preservation of the Hugging Face cache;
- an upgrade from the public version where applicable.

For 0.1.1 the Ubuntu v4 Gate has one failed run and one valid retry. On 23 July 2026 the maintainer
also attested the real Windows v4 Gate, including record reuse, and decided `RELEASE` after testing
on both systems. The private details of the Windows Gate are not reconstructed as measurements or
added to the public evidence.

Limits and checks that were not run must be explicit. `0.1.3` was authorized for commit, push, tag,
and GitHub Release before the real spike; this does not amount to a Gate, and PyPI remains excluded.
For `0.2.2`, `0.2.3`, and `0.2.4`, D-072, D-073, and D-077 carry forward the explicit waiver of
additional manual Ubuntu/Windows and hardware calibration runs before publication; the real update
path between two published releases is likewise follow-up verification. D-091 waives the `0.4.2`
manual pi-launch and continuous-motion observations while keeping them open. D-092 carries those
open checks into `0.4.3` and also leaves the revised cross-screen presentation without a manual
Windows observation. D-093 carries the same open motion observation into `0.4.4`, where it now covers
sections as well. The automated release matrix remains required; no waiver is a passed Gate,
and the maintainer will perform platform checks after release.

## Version, tag, and commit

The tag must be `v<version>` and the package version must match it exactly. The finalization commit
contains the version, changelog, and documentation, and **not** the artifacts, except for files the
repository versions on purpose.

The commit follows Conventional Commits and reports the checks performed in its body. Before
creating it:

```bash
git diff --check
git status --short
git diff --staged
```

## GitHub workflow

Pushing a `v*` tag runs `.github/workflows/release.yml`:

1. a test matrix on Ubuntu and Windows;
2. verification that the tag and metadata match;
3. a single build after the tests;
4. isolated verification of the wheel, sdist, and complete self-uninstall;
5. a `bora-workbench-release-bundle` containing wheel, sdist, both installers, and `SHA256SUMS`.

Every action is pinned to a full commit SHA and the workflow has only `contents: read`. It has no
manual dispatch, OIDC permission, registry environment, or publication job. The GitHub Release is
created from the exact bundle produced by this green workflow.

## Distribution boundary

D-070 supersedes the active registry-publication clauses in D-068 and D-069. `bora-workbench` is
published only through GitHub Releases until a future explicit maintainer decision changes that
boundary. The installers accept either a release wheel with its SHA-256 or a full Git commit; they
have no package-registry source.

Historical failed or pending publisher configuration is not used by this repository. Registry URLs
in `uv.lock` remain dependency sources for the frozen environment and do not publish
`bora-workbench`. A future registry release would require a new normative decision, implementation,
review, and current-session authorization.

## GitHub Release

The release attaches the same files produced by the build job:

- the wheel;
- the sdist;
- `install.sh`;
- `install.ps1`;
- `SHA256SUMS`.

The title, notes, and prerelease flag must be consistent with the changelog and metadata. Do not
upload a local build different from the one that went through the release matrix. Historical
`v0.1.6` stays under its `qwen-launcher` artifact identity.

## Verification after publication

On clean Ubuntu and Windows machines:

1. compare every downloaded artifact with the GitHub Release `SHA256SUMS`;
2. install the published source;
3. verify the version, validation, doctor, and engine;
4. run at least one mode and a clean stop;
5. try uninstall and uv removal;
6. confirm that the Hugging Face cache and unrelated processes and ports are intact.

A post-release problem is fixed on the branch, recorded under `Unreleased`, and distributed in a new
version. The previous release is never altered.

**End of the path:** [back to the documentation index](README.md).
