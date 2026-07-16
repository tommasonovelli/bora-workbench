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

### Changed

- Split Step 2 into declarative and core phases and added a 0.1 assisted-calibration gate so
  feasibility benchmarks cannot be published as optimized profiles.
