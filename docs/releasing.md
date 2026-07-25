# Releasing and publication

This page describes the current process. Publishing means creating or modifying remote resources: an
explicit human authorization is always required for pushes, tags, GitHub Releases, and PyPI.

## Public status

- current public version: `0.1.5`;
- remote tags: `v0.1.0`, `v0.1.1`, `v0.1.2`, `v0.1.3`, `v0.1.4`, and `v0.1.5`;
- GitHub Release `v0.1.5`: published with the installers, wheel, sdist, and `SHA256SUMS`;
- the `0.1.5` digests are the ones in the manifest attached to the release and come from the green
  build job;
- PyPI: not published yet, and excluded from the `0.1.5` authorization;
- public release `v0.1.5`: the first fully English release, republishing the calibration evidence
  with a regenerated digest chain; the runtime is unchanged.

The sections below describe what each published release contained. They name the protocol versions
that existed at the time on purpose: they are the history of the artifacts, not a description of the
current CLI, which offers one calibration protocol and no `--protocol` option.

Published artifacts are immutable. Do not rebuild, replace, or re-upload files under the same
version to include later fixes: that requires a new version.

To install the release, see [Installation](installation.md).

## Preparing a version

Start from a clean checkout and the required uv version:

```bash
git status --short
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
```

Delete `dist/` before the build, then:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
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

Pushing a `v*` tag triggers `.github/workflows/release.yml`:

1. a test matrix on Ubuntu and Windows;
2. verification that the tag and metadata match;
3. a single build after the tests;
4. isolated verification of the wheel and inspection of the sdist;
5. upload of the tested artifact between jobs;
6. PyPI publication of that same artifact only when the repository variable
   `PYPI_PUBLISH_ENABLED` is exactly `true`.

The actions are pinned to full SHAs. Global permissions are `contents: read`; only the `publish`
job, protected by the `pypi` environment, receives `id-token: write`. There is no PyPI token in the
repository. For `v0.1.3` the variable stays absent and the job is skipped.

## PyPI Trusted Publishing

The `0.1.0` job failed with `invalid-publisher` because PyPI does not have the matching
configuration yet. The Trusted Publisher must specify:

```text
project:      qwen-launcher
owner/repo:   tommasonovelli/qwen-launcher
workflow:     release.yml
environment:  pypi
```

After configuration, only the failed publication job of run `29739366272` should be re-run. The
tests and build of that run are already green and the same artifacts are in the GitHub Release; they
must not be rebuilt. The opt-in variable concerns later workflows and can only be set with a
separate remote authorization.

Until PyPI actually contains a version, the installers must not use `--pypi-version` /
`-PypiVersion` for that version.

## GitHub Release

The release attaches the same files produced by the build job:

- the wheel;
- the sdist;
- `install.sh`;
- `install.ps1`;
- `SHA256SUMS`.

The title, notes, and prerelease flag must be consistent with the changelog and metadata. Do not
upload a local build different from the one that went through the release matrix. `v0.1.3` is a
stable GitHub release, not a prerelease.

## Verification after publication

On clean Ubuntu and Windows machines:

1. compare the digests from GitHub and, when available, PyPI;
2. install the published source;
3. verify the version, validation, doctor, and engine;
4. run at least one mode and a clean stop;
5. try uninstall and uv removal;
6. confirm that the Hugging Face cache and unrelated processes and ports are intact.

A post-release problem is fixed on the branch, recorded under `Unreleased`, and distributed in a new
version. The previous release is never altered.

**End of the path:** [back to the documentation index](README.md).
