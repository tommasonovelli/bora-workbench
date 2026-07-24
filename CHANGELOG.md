# Changelog

Relevant changes are recorded here by version. Future plans do not belong in the changelog: they
live in `IMPLEMENTATION_SPEC.md`.

## [Unreleased]

## [0.1.4] - 2026-07-24

Implements `calibration/v6-lite` as an **opt-in** experimental protocol. Under a recorded maintainer
decision (D-063) the engine was built before the GO verdict of the cross-context spike;
`calibration/v5` remains the default and promoting v6 to the default remains a human decision. The
logic is tested offline with fakes; the real trial adapter is validated on hardware.

### Added

- `--protocol v6` with `--preference fast|balanced|max-context`: measures and records three envelopes
  per mode (`fast`, `balanced`, `max_context`) in the new `calibration-record/v5` record.
- The `_calibration_v6_*` engine: a shared `coding`+`studio` search bisecting the VRAM side only,
  a production quick-bench (`benchmark_quick.py`), Pareto-free selection, ABBA confirmation with a
  conditional third round, and a final per-envelope gate (smoke, multi-turn, vision).
- v6 trial reserves (0.5/2.0/0.125 GiB) written into the record; reuse and `doctor` evaluate the
  `active_preference` envelope and fall back to the baseline when headroom is insufficient.

### Changed

- Hard migration to `mode/v2`: the three modes now also emit `--min-p`, `--presence-penalty`,
  `--repeat-penalty`, and `--reasoning` (coding `on`; studio and vstudio `off`). Temperature, top-p,
  and top-k are unchanged and `command_contract_sha256` does not change. The loader accepts only
  `mode/v2`.

## [0.1.3] - 2026-07-24

A correctness release that prepares measurable input for the human gate of `calibration/v6-lite`;
protocol v5 remains the default and v6 is not implemented yet.

### Added

- A repository-only `scripts/spike_ctx/` package prepares the human cross-context spike with a
  non-cached quick-bench, bisection with typed outcomes, MTP/reasoning appendices, an offline
  dry-run, and evidence templates. It neither performs the real run nor decides GO/NO-GO.

### Fixed

- RAM/VRAM monitoring errors discovered during cleanup now take precedence over workload failures
  and correctly invalidate the whole run.
- VRAM reserve violations and failure to release memory after stop have distinct classes, so
  experimental protocols no longer confuse a monotonic limit with a retryable error.

### Changed

- The engine contract makes MTP explicit in the launch plan: `coding` and `studio` keep the same
  argv, while `vstudio` conservatively uses `speculative=disabled` together with `--mmproj`.
- The contract prepares — without enabling them in `mode/v1` modes — the verified extended sampling
  and reasoning flags needed by a possible `calibration/v6-lite`.
- The new contract digest makes earlier local records ineligible for reuse; the files remain
  readable and the remedy is to re-run `calibrate`.

## [0.1.2] - 2026-07-23

A stabilization release with `calibration/v5`, uniform terminal UX, Ubuntu CUDA build progress, and
complete removal of uv-managed installations.

### Fixed

- Dynamic CLI values are rendered as literal text: square brackets and sequences resembling Rich
  markup are no longer hidden, reinterpreted, or turned into unhandled errors.

### Changed

- `calibration/v5` adds 96K (`98304`) and 48K (`49152`) to the automatic scale, raises the cap to 14
  probes, and produces `calibration-record/v4`; historical v2/v3 records remain readable.
- `doctor` shows the calibrated parameters of the valid active record (`ctx` and, on CUDA,
  `--n-cpu-moe`) instead of just the "valid" label.
- The CLI uses a shared Rich presentation for states, tables, errors, and progress, keeping textual
  labels readable even without color.
- The Ubuntu CUDA build shows the real percentage read from the CMake output instead of an
  indeterminate indicator.
- `uninstall` uses a single confirmation to remove the managed roots and its own `uv tool`
  installation, without removing uv or the Hugging Face cache.
- The CI and release workflows use Node 24 releases of the actions, always pinned to a full SHA.

### Known limitations

- Calibration coverage remains `GATE-PARTIAL` while materially different hardware is missing.
- The maintainer authorized the GitHub publication of `0.1.2` without repeating a manual
  cross-platform Gate; PyPI remains unavailable and excluded.

## [0.1.1] - 2026-07-23

A stabilization release with `calibration/v4`, trial port isolation, and visible progress during
calibration and engine installation.

### Added

- `calibration-record/v3` records `calibration/v4` and its reserve explicitly, while still loading
  and semantically reconstructing historical v2 records.

### Fixed

- Engine installation shows the current phase and, on terminals, byte progress bars with speed and
  ETA during download and extraction; probes stay bounded but raise the allowance for the slow first
  start of the Windows CUDA asset from 10 to 60 seconds.
- Temporary calibration servers use a system-assigned loopback port when `llama_port` is busy;
  normal startups still require the configured port.
- Record reuse tolerates at most 1 MiB of variation in the reported total RAM, leaving component
  identity and RAM/VRAM headroom checks unchanged.

### Changed

- `calibration/v4` replaces the v3 execution while keeping its scale, search, and ABBA confirmation,
  but uses a 0.3 GiB VRAM reserve; on reuse each record keeps its own original reserve.
- v4 calibration shows the running trial, live progress, and per-phase ETA on terminals, keeps
  linear output when redirected, and summarizes the selection rationale and measured headroom.
- The documentation was rewritten as a linear path for new users and describes only current
  behavior.
- Measured evidence was separated from the manuals under `evidence/`; superseded audits and designs
  were removed.
- `IMPLEMENTATION_SPEC.md` keeps the summarized status and only the work still to be done, without
  the detailed plans of completed milestones.

### Known limitations

- The real Ubuntu and Windows Gates were attested by the maintainer, but coverage remains
  `GATE-PARTIAL` while materially different hardware is missing; the Ubuntu Gate does not make
  `n_cpu_moe=36` safe.
- `0.1.1` is published on GitHub Releases only; PyPI is out of scope for this publication.

## [0.1.0] - 2026-07-20

First public release of `qwen-launcher`.

### Added

- Explicit tool installation on Ubuntu and Windows with uv `0.11.28`, CPython `3.12.13`, and SHA-256
  verification of the wheel.
- The Qwen model and vision projector pinned by revision, filename, size, and digest, read without
  modifying the Hugging Face cache.
- A `llama.cpp b10011` contract with verified flags, API, health check, and CPU/CUDA assets.
- Safe engine installation with HTTPS download, confined extraction, immutable directories, and
  atomic manifest-based activation.
- The `coding`, `studio`, and `vstudio` modes, with UI and vision applied explicitly.
- Foreground lifecycle, loopback port, logs, health polling, atomic state, startup lock, and
  `status` and `stop` based on `pid + create_time`.
- Strict TOML configuration with environment > file > default precedence and defined Linux/Windows
  directories.
- CPU, RAM, and NVIDIA detection; deterministic GPU selection and a CUDA environment confined to the
  child process.
- Local v3 calibration with adaptive search, RAM/VRAM monitoring, ABBA confirmation, `benchmark/v1`,
  candidate/active/previous records, and reuse diagnostics.
- Public v2 policy and reports used only as evidence and ordering seeds, never as a remote envelope.
- JSON Schema and semantic validation of locks, modes, policies, reports, and bundles.
- `doctor`, `validate`, `engine install`, `engine status`, `uninstall`, and installers without
  elevation.
- Cross-platform CI and release workflows with full-SHA-pinned actions and OIDC PyPI publication.

### Changed

- The available-RAM gate for the default model is set to 22 GiB, keeping 28 GiB total and a dynamic
  2 GiB calibration reserve.
- The expert context target `98304` is available through `--target-ctx`, separate from the automatic
  scale.
- The `q8_0` K/V cache is pinned on the CUDA branch with mmap; the CPU branch is unchanged.

### Known limitations

- The calibration evidence is `GATE-PARTIAL`: a repetition on materially different hardware is
  missing.
- CUDA is blocked on multi-GPU hosts.
- The weights are neither distributed nor downloaded by the launcher.
- PyPI awaits Trusted Publisher configuration; the GitHub artifacts are public.
- The 0.1 series guarantees no stability of the CLI, configuration, records, procedures,
  performance, or future compatibility.
