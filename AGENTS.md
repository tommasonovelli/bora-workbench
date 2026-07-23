# Agent Guidelines

These rules apply to every AI agent and contributor working in this repository. They are tailored to
`qwen-launcher`; rules copied from unrelated Go, TypeScript, web, or habit-tracking projects do not
apply here.

## Sources of truth

1. Read **all** of `IMPLEMENTATION_SPEC.md`, including its tracker, before changing the project.
2. Follow the source hierarchy in section 2 of that specification. Versioned locks and measured
   evidence outrank assumptions and current online documentation.
3. Treat `IMPLEMENTATION_SPEC.md` as the only normative plan. `README.md` and this file summarize
   working practices; they do not override it.
4. Preserve pre-existing user changes. Stop and report contradictions instead of resolving them
   silently.

## Current project boundary

- This is a Python 3.12 launcher for a local, calibrated Qwen model served by an exact, verified
  `llama.cpp` release. It is not a generic model manager or plugin framework.
- Work one implementation step at a time and do not anticipate later milestones.
- **Steps 3, 4, 5, 5A, 5B, 6A and 6B are complete.** Versions `0.1.0` and `0.1.1`, their tags and
  GitHub Releases are public; release artifacts come only from their green release test/build jobs.
  The maintainer attested real Ubuntu and Windows v4 Gates and decided `RELEASE` on 23 July 2026.
  PyPI remains unconfigured and `0.1.1` was explicitly authorized for GitHub only; do not upload,
  rebuild or replace published artifacts. Version 0.1.1 uses `calibration/v4`, a 0,3 GiB VRAM
  reserve and `calibration-record/v3`; historical v2 records keep their 0,5 GiB reuse reserve. Q8
  remains pinned, the `n_cpu_moe` domain is `[0, 41]`, and calibration coverage remains
  `GATE-PARTIAL`. The three local candidates remain inactive. Do not activate candidates or begin
  Step 7 without an explicit request.
- Never invent engine flags, checksums, source commits, benchmark results, hardware support, profiles,
  health responses, or compatibility claims.

## Stack and repository layout

- CPython `3.12.13`; package metadata remains `>=3.12,<3.13`.
- `uv 0.11.28`, `uv_build`, committed `uv.lock`, and frozen development/CI commands.
- Source layout: `src/qwen_launcher/`; tests: `tests/`; packaged data:
  `src/qwen_launcher/resources/`.
- Supported targets are Ubuntu 22.04+ x86-64 and Windows 11 x86-64, with CPU or one explicitly
  selected NVIDIA CUDA GPU.
- Keep the module responsibilities from specification section 4.1. Only `paths.py`, `process.py`,
  `hardware.py`, and `engine.py` may branch on the operating system.

## Code quality

Code here is written to be read. Optimize for the maintainer who opens a file months from now with no
memory of why it exists: prefer the obvious construction over the clever one, make intent explicit
instead of implied, and keep a reader from having to reconstruct a rule that a sentence could state.
Readability and maintainability outrank brevity, micro-optimizations, and personal style.

### Size and complexity

For hand-written Python in `src/`, `tests/`, and `scripts/`:

- file: maximum 200 lines;
- function or method: maximum 40 lines;
- production function parameters: maximum 3, excluding `self`/`cls`;
- nesting: maximum 3 levels; prefer guard clauses and early returns.

Split code by responsibility before exceeding a limit. Test fixtures may require additional injected
parameters when grouping them would reduce clarity. Normative documentation, measured evidence,
lockfiles, generated artifacts, JSON schemas, and declarative content are exempt from code-size
limits and must retain their required format.

### Functions and design

- Each function does one thing. If its description needs “and”, extract a named operation.
- Prefer small pure functions and frozen, slotted dataclasses for runtime models.
- Keep CLI functions limited to input, presentation, service calls, and exit-code mapping.
- Keep platform logic, process lifecycle, configuration, validation, resources, and engine management
  in their assigned modules.
- Prefer composition and narrow protocols over inheritance or broad interfaces.
- Apply DRY after the third real repetition, not before. Avoid speculative abstractions and unused
  extension points.
- Do not introduce async code, plugins, adapters, factories, or configuration frameworks without a
  current, demonstrated requirement.

### Naming and typing

- Use descriptive, pronounceable `snake_case` names; classes use `PascalCase`.
- Functions use verb-led names where practical; booleans start with `is_`, `has_`, or `can_`.
- Avoid abbreviations except established terms such as `id`, `url`, `api`, `gpu`, `cpu`, `ram`, and
  `ctx` where the specification defines them.
- Use precise unit suffixes. Memory values are GiB and names must end in `_gib`.
- Add type hints to production functions. Avoid `Any` unless data is genuinely unvalidated at that
  boundary, then validate it before constructing runtime models.

### Comments and documentation

Every module, class, and function—including private helpers—carries a concise docstring stating what
it does. State the reason as well whenever the behavior follows a normative rule or a platform
constraint rather than an obvious implementation choice, and name the `IMPLEMENTATION_SPEC.md`
section so the next reader can check the source instead of guessing.

Comments explain **why**, constraints, or trade-offs—not what the next line does. A comment that
restates the code is noise and must be removed. Do not leave dead code or commented-out code.
A TODO must include date and context, for example:

```python
# TODO(2026-07): remove after engine-lock/v2 migration is complete.
```

## Errors and configuration

- Expected failures must be actionable, go to stderr, and use the exit codes in specification
  section 5.11 without tracebacks.
- Do not catch and ignore operational exceptions. Add context or map them at the correct boundary.
- Configuration precedence is environment > TOML > code defaults. Validate the entire TOML file
  before applying environment overrides.
- Unknown or malformed values are errors. Do not add silent fallbacks beyond those explicitly
  specified.
- Never modify user `config.toml` automatically and never hardcode user-specific paths.

## Side effects and resources

- Importing `qwen_launcher` must not access the network, create files/directories, write state, or
  start processes.
- Path helpers compute paths only. Creation belongs to the operation that owns the data.
- Access packaged resources with `importlib.resources` and `Traversable`. Use `as_file()` only within
  its context manager; never assume a wheel resource is a physical `Path`.
- Use atomic same-directory writes and the exact state/process identity contracts from the
  specification when implementing lifecycle code.

## Security

- Never use `shell=True`, `eval()`, `exec()`, `sudo`, automatic elevation, or unverified executable
  strings.
- Bind managed services only to `127.0.0.1`, never `0.0.0.0`.
- Keep TLS and checksum verification enabled. Downloads must use HTTPS and safe extraction rules.
- Never delete outside managed data/cache/state roots, and never alter the Hugging Face cache.
- Keep declarative model identity separate from the physical GGUF path; resolve the default model
  only from the pinned revision and digest in `engine.lock`.
- Set `CUDA_VISIBLE_DEVICES` only in the child environment; do not mutate the parent process.
- Tests must not use real network, GPU, model, server, or administrative operations. Use fakes and
  mocks.
- Never commit credentials, tokens, private paths, or secrets. Use explicit placeholders in examples.

## Dependencies

The approved 0.1 runtime dependencies are `typer`, `rich`, `psutil`, `httpx`, and `jsonschema`; the
development dependencies are `pytest` and `ruff`. Add a dependency only when the active step requires
it and the normative plan permits it. In that case:

1. explain why a small standard-library implementation is insufficient;
2. verify maintenance, licensing, security, and transitive cost;
3. update `pyproject.toml` and `uv.lock` together;
4. test the frozen environment on supported platforms.

Do not add a library merely to avoid a short, clear implementation.

## Tests and verification

- Test the main flow first, then boundaries and failure paths.
- Tests must be deterministic, offline, and independent of host OS/hardware.
- Do not weaken assertions, delete coverage, or change expected behavior merely to make tests pass.
- Before changes, run the available baseline checks. Before completion, run:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

When packaging or resources change, also run:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
```

Run `qwen-launcher validate` once that command exists. If a required tool or platform is unavailable,
report that limitation explicitly; do not claim the check passed.

## Git and change discipline

- Use Conventional Commits and keep one implementation step per commit.
- Write an explicit subject in the form `<type>(<optional-scope>): <concrete outcome>`. Describe the
  behavior or repository state produced by the commit; avoid vague subjects such as `update files`,
  `fix issues`, `changes`, or a bare step number.
- For any non-trivial commit, add a body after a blank line. Explain what changed and why, note the
  important constraints or trade-offs, and list the relevant checks performed. A one-line message is
  acceptable only when the subject fully explains a small, self-contained change, such as a typo.
- Treat commit subjects suggested by `IMPLEMENTATION_SPEC.md` as starting points, not as complete
  messages when the change needs context. Keep the subject concise and put supporting detail in the
  body instead of compressing substantial work into one line.
- A pull request changes declarative content or core code, never both.
- Do not rename, move, generalize, or reformat unrelated files.
- Do not commit debug `print()` calls, temporary artifacts, caches, virtual environments, or build
  outputs.
- Local commits are allowed when requested. Pushes, tags, releases, uploads, remote configuration,
  and publication always require explicit authorization in the current session.
- Before committing, inspect `git diff`, run `git diff --check`, verify tests, and ensure the staged
  set contains only the intended work.

## Completion report

State which files changed, what behavior changed, which checks ran, and which manual or
cross-platform checks remain. Surface assumptions, unresolved evidence, and conflicts clearly.
“Works on my machine” is never a substitute for the required CI and human gates.
