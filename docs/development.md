# Development and contributions

## Finding your way around the repository

For anyone opening the project for the first time:

```text
src/bora_workbench/       Python package
├── cli.py               public command group
├── config.py            configuration
├── paths.py             per-OS directories
├── hardware.py          CPU, RAM, and NVIDIA
├── profiles.py          modes and launch plan
├── engine.py            model and llama.cpp
├── process.py           server lifecycle
├── calibration.py       main calibration API
├── benchmark.py         benchmark/v1
├── validation.py        content validation
├── _*.py                extracted internal responsibilities
└── resources/           data included in the wheel

tests/                   offline tests and fakes
scripts/                 packaging verifications
docs/                    manuals for the current state
evidence/                measured evidence and manifests
IMPLEMENTATION_SPEC.md   normative plan and future work only
AGENTS.md                permanent rules for contributors and agents
```

Before changing code, read [Architecture](architecture.md), `AGENTS.md`, and the whole of
`IMPLEMENTATION_SPEC.md`.

## Reproducible environment

Development versions:

- CPython `3.12.13`;
- uv `0.11.28`;
- dependencies frozen in `uv.lock`.

Preparation:

```bash
uv sync --frozen
```

Baseline and final verification:

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen bora validate
```

If packaging, installers, documents included in the sdist, or resources change:

```bash
rm -rf dist                       # PowerShell: Remove-Item dist -Recurse -Force
uv build
uv run --frozen python scripts/verify_wheel.py
uv run --frozen python scripts/verify_uninstall.py
```

The verifications install the wheel into temporary environments, read the resources, run
CLI/validation, inspect the sdist, and try the complete removal of the `uv tool` environment. Tests
must use no network, GPU, model, real server, or administrative privileges.

## Sources of truth

When two sources diverge, use this order:

1. locks, versioned content, and accepted reports;
2. measured output in `evidence/`;
3. schemas and tests;
4. `IMPLEMENTATION_SPEC.md`;
5. official documentation for the pinned version;
6. current unversioned documentation;
7. assumptions.

Do not fix a `llama.cpp` contract by looking at the current upstream branch. Do not invent flags,
checksums, supported hardware, endpoints, benchmarks, or compatibility.

## Change boundaries

A pull request changes **either core or declarative content**, not both.

- Core: Python, installers, workflows, and behavioral tests.
- Content: JSON under `resources/content`, locks, reports, manifests, and the evidence linked to
  them.
- Documentation: accompanies the side that is changing and describes the actual behavior.

A fix to a schema or a lock may require a declarative PR separate from the Python change that will
consume it. Avoid renames, refactors, or formatting unrelated to the purpose.

## Core rules

The code favors readability and narrow responsibilities:

- at most 600 lines per file and 40 per function in hand-written code;
- at most three production parameters, excluding `self`/`cls`; a published callback can exceed this
  only through the justified `path::qualified_name` registry enforced by `test_code_quality.py`,
  which also rejects stale entries;
- at most three nesting levels;
- small functions, precise types, and frozen/slotted dataclasses for runtime models;
- docstrings for modules, classes, and functions;
- expected errors actionable, on stderr, and without tracebacks;
- no frameworks, plugins, async, or abstractions without a current requirement.

The CLI collects input, presents results, and maps errors; it must not absorb configuration,
platform, lifecycle, or calibration logic.

## Changing a mode

Modes are JSON under:

```text
src/bora_workbench/resources/content/modes/
```

Runtime modes use `mode/v2`:

```json
{
  "schema": "mode/v2",
  "id": "coding",
  "description": "...",
  "services": {"ui": false, "vision": false},
  "sampling": {
    "temp": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 0.0,
    "repeat_penalty": 1.0,
    "reasoning": "on"
  }
}
```

The id must match the filename. Performance, memory, engine flags, and hardware do not belong to a
mode. A new incompatible field requires a new schema authorized by the plan; it must not be added to
`mode/v2` out of convenience. The packaged `mode/v1` schema remains only for precise validation of
older declarative content; the runtime loader requires v2.

After the change, run at least `validate`, the tests, the build, and the wheel verification.

## Schemas and content

The schemas live in `resources/schemas/`, use Draft 2020-12, and set `additionalProperties: false`.
Changing an existing contract incompatibly is forbidden: it requires a new schema identifier and an
explicit reading strategy.

Loaders build runtime models only after validation. Defaults belong to the loader or the code, not
to a silent correction of unknown input.

Do not propose new `profile/v1` documents as transferable configurations. The runtime envelope comes
only from the active local record; shared reports and profiles are evidence, never plans.

## Updating `engine.lock`

`engine.lock` does not follow `latest`. A deliberate update requires new real evidence on every
supported pair before the lock changes.

Procedure:

1. choose and approve a precise release;
2. record the tag, full commit, `--version`, `--help`, licenses, and official assets;
3. acquire the archives over HTTPS and verify their SHA-256;
4. test Ubuntu and Windows, CPU and CUDA, in all three modes;
5. verify health, API, metrics, UI, vision, MTP, sampling, GPU, logs, and stop;
6. run `benchmark/v1` without reading it as a performance promise;
7. save the output and manifests under `evidence/engine/`;
8. update the lock, notices, flag-vocabulary tests, and current documentation together;
9. repeat the real installations and the `coding` smoke test on every target.

For Ubuntu CUDA, first check whether the new release offers a prebuilt: building from source is a
consequence of the asset missing in `b10011`, not a permanent preference. For Windows CUDA, the
server and runtime must belong to the same verified pair.

Any divergence between the output, archive, digest, and lock stops the update.

## Contributing calibration evidence

Follow the [Contributing new evidence](calibration.md#contributing-new-evidence) section. In short,
an evidence PR:

- uses the current calibration protocol and the pinned model and engine;
- first establishes a schema authorized for the measured method;
- contains a privacy-safe report governed by that schema;
- declares the actually measured scope and the portability limit;
- updates the policy and the SHA-256 of the exact bytes;
- keeps the reviewed sources in `evidence/calibration/<id>/`;
- includes no private records, config, or logs;
- contains no core changes.

The packaged `calibration-report/v2` remains immutable historical reference evidence. Its legacy
seed fields do not enter the current runtime, become a plan, promise tok/s, or authorize
nearest-match.

## Measured evidence

`evidence/` is neither user documentation nor an archive of plans. It contains bytes that back:

- the `llama.cpp b10011` contract and the functional matrix;
- the choice of the Q8 KV cache on CUDA;
- the public calibration report and its digests.

Files covered by a manifest, or referenced by a report, must be treated as immutable. If a path has
to change, update the references and manifests without altering the source bytes; if the bytes
change, repeat the verification and declare new evidence instead of rewriting the accepted one.

## Dependencies

The current runtime dependencies are `typer`, `rich`, `psutil`, `httpx`, and `jsonschema`; the
development ones are `pytest` and `ruff`.

Before adding one:

1. show why the standard library is not enough;
2. verify maintenance, licensing, security, and transitive cost;
3. obtain authorization from the active normative specification;
4. update `pyproject.toml` and `uv.lock` together;
5. test the frozen environment on Ubuntu and Windows.

## Packaging and resources

The backend is `uv_build` with an `src/` layout. The wheel must contain everything under
`bora_workbench/resources/`; the sdist additionally includes the installers, documentation, plan, and
evidence.

Use `importlib.resources.files()` and keep the resources as a `Traversable`. `as_file()` is allowed
only inside its context manager. Importing the package must stay free of side effects.

When adding a current manual, update the list required by `scripts/verify_wheel.py` and the
sequential navigation in `docs/`.

## CI and manual checks

CI runs a frozen sync, Ruff, pytest, validation, the build, and the wheel verification on Ubuntu
22.04 and Windows Server 2022. The fakes exercise the failure paths without replacing the real gates
when the engine, assets, installers, GPU, or model behavior change.

Always state in the report:

- the files and behavior that changed;
- the checks that ran;
- the missing manual or cross-platform tests;
- the assumptions, unavailable evidence, and limits.

## Git and pull requests

Use Conventional Commits with a concrete subject. For non-trivial changes add a body explaining
what, why, the constraints, and the verifications. Before committing:

```bash
git diff --check
git status --short
git diff --staged
```

Pushes, tags, releases, uploads, and remote settings require explicit authorization. The `main`
branch enforces CI and code owner review for contributors.

**Next:** [Releasing](releasing.md)
