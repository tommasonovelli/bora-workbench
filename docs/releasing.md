# Releasing and publication

This page describes the current GitHub-only process. Creating or modifying remote resources always
requires explicit human authorization for the push, tag, and GitHub Release.

## Public status

- release described by this branch: `bora-workbench 0.2.3`;
- preceding public version: `bora-workbench 0.2.2` on GitHub Releases;
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
For `0.2.2` and `0.2.3`, D-072 and D-073 carry forward the explicit waiver of additional manual
Ubuntu/Windows and hardware calibration runs before publication; the real update path between two
published releases is likewise follow-up verification. The automated release matrix remains required; the
waiver is not a passed Gate, and the maintainer will perform platform checks after release.

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
