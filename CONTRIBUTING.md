# Contributing to bora-workbench

Thank you for your interest. Before opening a change, read:

1. the [project documentation](docs/README.md);
2. the [architecture](docs/architecture.md);
3. the [development guide](docs/development.md);
4. `AGENTS.md` and the whole of `IMPLEMENTATION_SPEC.md`.

`IMPLEMENTATION_SPEC.md` is the only normative plan: a PR must not implement future work that has
not been authorized yet.

## Preparing the checkout

```bash
git status --short
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

If the baseline is not green, do not hide the problem: describe it before adding further changes.
Always preserve pre-existing user changes.

## Choosing the type of contribution

A pull request changes **only one** of the two areas:

- **core**: Python, installers, workflows, and behavioral tests;
- **declarative content**: modes, policies, reports, locks, manifests, and the evidence linked to
  them.

Documentation accompanies the chosen area. Do not mix core and content in the same PR, and do not
reformat, rename, or move files unrelated to the purpose.

For a bug or a proposal, state the current behavior, the expected behavior, the sources, and the
impact first. Do not present an assumption as verified compatibility.

## Sources and evidence

Versions, flags, checksums, endpoints, supported hardware, and measurements must come from locks,
tests, or real output. The full hierarchy is in
[Development and contributions](docs/development.md#sources-of-truth).

In particular:

- no `latest` in versioned files;
- no `llama.cpp` flags recalled from memory or copied from the current upstream branch;
- no invented benchmarks, profiles, or hardware claims;
- a contradiction between sources must be made visible, not resolved silently.

Raw evidence lives in [`evidence/`](evidence/README.md), separate from the current manuals.

## Quality and security

Follow the module responsibilities and limits described in `AGENTS.md`. In every case:

- small functions, precise types, and docstrings;
- no `shell=True`, `eval`, `exec`, `sudo`, or elevation;
- no bind on `0.0.0.0`;
- TLS and checksums always enabled;
- no automatic modification of `config.toml` or the Hugging Face cache;
- deletions only inside the managed roots;
- expected errors actionable, without tracebacks;
- offline, deterministic tests that are independent of the host hardware.

Do not add dependencies without a current requirement and an analysis of the standard library,
maintenance, licensing, security, and transitive cost. `pyproject.toml` and `uv.lock` change
together.

## Calibration evidence

A calibration PR uses the current calibration protocol and follows the
[Contributing new evidence](docs/calibration.md#contributing-new-evidence) section. The public
contract still describes the historical reference method, so evidence from the current protocol
first requires a new schema in a separate content PR.

The following are mandatory:

- a real run on the pinned model and engine, including Gate failures;
- a privacy-safe report in the schema version authorized for the method;
- an explicit measured scope and portability limit;
- SHA-256 of the final bytes and a verifiable manifest;
- no local records, config, raw logs, or private data;
- ordering-only seeds, never a remote envelope or nearest-match;
- personal approval by the maintainer.

The launcher creates no logins, uploads, commits, branches, issues, or PRs.

## Final checks

Always:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
```

If packaging, resources, installers, or documents included in the sdist change:

```bash
rm -rf dist
uv build
uv run --frozen python scripts/verify_wheel.py
```

Also run:

```bash
git diff --check
git status --short
git diff --staged
```

Report the manual or cross-platform tests you did not run. Offline fakes are no substitute for real
evidence when the engine, assets, GPU, model, or installers change.

## Commits and pull requests

Use Conventional Commits with a concrete subject, for example:

```text
docs: reorganize current project documentation
fix(engine): preserve active manifest after failed extraction
feat(content): add verified calibration evidence for one host
```

For non-trivial changes add a body explaining what changed, why, the constraints, and the checks
performed. The PR template requires the change type and the verifications.

Pushes, tags, releases, uploads, and remote settings require explicit authorization. CI covers
Ubuntu and Windows; contributors require code owner review.

For operational details continue with [Development and contributions](docs/development.md).
