# Documentation

This directory describes **the behavior of the code on the current branch**. It contains no trackers,
proposals, or completed implementation plans.

The recommended reading order is linear:

1. [Installation and first run](installation.md) — platforms, requirements, model, engine, and
   initial startup;
2. [Commands](commands.md) — the whole CLI surface, options, output, and exit codes;
3. [Configuration and local data](configuration.md) — TOML, environment variables, precedence, and
   managed directories;
4. [Architecture](architecture.md) — components, flows, contracts, lifecycle, and security
   boundaries;
5. [Calibration](calibration.md) — local v5 search, benchmarks, records, reuse, and shared
   evidence;
6. [Operations and diagnostics](operations.md) — routine checks, errors, and recovery;
7. [Development](development.md) — repository structure, content, tests, packaging, and
   contributions;
8. [Releasing](releasing.md) — building, publishing, and the status of the public artifacts.

For a short overview and a quick start, see the [main README](../README.md).

## Which source to consult

| Question | Source |
|---|---|
| What does the program do today? | the code, locks, schemas, tests, and this documentation |
| Which versions and checksums are accepted? | `src/qwen_launcher/resources/engine.lock` and the versioned content |
| Which measurements do the locks and reports come from? | [`evidence/`](../evidence/README.md) |
| How do I contribute? | [CONTRIBUTING.md](../CONTRIBUTING.md) and [development](development.md) |
| What is planned but not implemented? | [IMPLEMENTATION_SPEC.md](../IMPLEMENTATION_SPEC.md) |
| What changed between versions? | [CHANGELOG.md](../CHANGELOG.md) |

`IMPLEMENTATION_SPEC.md` is the normative plan, not a user manual. Raw evidence is kept separately in
`evidence/` because it exists to verify where the contracts came from, not to explain day-to-day use
of the launcher.

## Current status

The public release is `0.1.4`: it keeps `calibration/v5` and v4 records as the default and adds
`calibration/v6-lite` as an opt-in experimental protocol (`--protocol v6`, `v5` records) under a
recorded maintainer override (D-063). Promoting v6 to the default remains conditional on a committed
GO.

PyPI remains unavailable. The verified artifacts are in the `v0.1.4` GitHub Release and must not be
rebuilt or replaced.

## Current limits

- guaranteed support: Ubuntu 22.04+ x86-64 and Windows 11 x86-64;
- backends: CPU, or a single NVIDIA CUDA GPU;
- CUDA on multi-GPU hosts is blocked;
- the default model and `llama.cpp` are pinned to exact identities;
- weights and mmproj are neither redistributed nor downloaded automatically;
- the empirical calibration evidence is still `GATE-PARTIAL` because it covers a single real machine;
- no interface stability guarantee for the 0.1 series.

**Next:** [Installation and first run](installation.md)
