# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Initial Python package scaffold.
- Strict 0.1 configuration and Linux/Windows path contracts.
- Minimal `--version` and `doctor` CLI.
- Package-resource helpers, tests, wheel verification and CI.
- Normative `IMPLEMENTATION_SPEC.md` with progress tracker, plus archived raw spike evidence.
- Exact profile matching, pinned model resolution and lock-governed CPU/CUDA command building.
- `coding`, `status` and `stop` with atomic state, startup locking, health polling and safe PID identity.
- Complete verified engine asset matrix, secure streamed downloads and confined archive extraction.
- Immutable managed-engine installations with atomic manifest activation, status and doctor diagnostics.
- Pinned llama.cpp and NVIDIA CUDA third-party notices for managed installations.
- `studio` and `vstudio` commands with the integrated UI, optional browser opening and pinned vision
  projector activation.
- Assisted `calibrate` trials with immutable benchmark resources, aggregate VRAM monitoring,
  atomic draft bundles, privacy redaction and explicit bundle validation.
- Post-stop VRAM stabilization with an explicit release tolerance and final release evidence.
- Recursive JSON redaction, relative discard-log references and privacy scanning for shared bundles.
- Adaptive zero-input `calibration/v2`: GGUF-predicted axis domain, measured bisection screening
  with honest linear degradation, RAM monitoring for every backend, finalist confirmation with
  stable starts and `benchmark/v1`, noise-robust dominance selection, and an approved-scale
  context descent.
- Historical `calibration-record/v1` local records for the v2 implementation.
- `calibration/v3` paired ABBA confirmation with `benchmark/v1` on every start, unanimous-round
  dominance, honest baseline-drift degradation, a universal 2 GiB RAM reserve, and safe
  interpolation over feasible screening peaks only.
- `calibration-record/v2` with per-process timing, RAM/VRAM/release, benchmark, WDDM-context and
  best-effort GPU telemetry evidence; candidate/active/previous lifecycle, atomic promotion,
  `--no-activate`, `--activate`, `--target-ctx`, one-slot evidence retention and doctor states.

### Changed

- Split Step 2 into declarative and core phases and added a 0.1 assisted-calibration gate so
  feasibility benchmarks cannot be published as optimized profiles.
- Excessive VRAM baseline drift now discards only the affected candidate instead of aborting the
  complete calibration; all-discarded bundles receive an explicit CLI summary.
- Shared profile v1 envelopes are reference-only seeds and no longer enter a launch plan without a
  future compatible local calibration record.
- Calibration v1 now rejects mixed contexts, duplicate or unsafe candidate ordering, and validators
  recompute resource constraints, policy provenance and deterministic accepted selections.
- Calibration v2 refused an exhausted screening instead of claiming an unproven optimum, treated
  monitor and driver failures as run-invalidating, and tied reuse to finalist evidence. It is now
  superseded after the first real Gate rejected its disjoint confirmation windows and extreme
  maximum-based dominance rule; v1 records are diagnosed as superseded and never reused.
- The 0.1 plan now requires hardware-independent local search instead of exporting the 32/8 host's
  optimum through nominal RAM/VRAM classes.
- The engine command contract now pins KV-cache Q8 (`--cache-type-k q8_0 --cache-type-v q8_0`) on
  the CUDA branch only, keeping mmap enabled and the CPU branch unchanged, after paired Ubuntu and
  Windows 11 CUDA 13.3 smoke evidence on llama.cpp b10011.
