# Calibration Gate v3 — Windows CUDA, 19 July 2026

> **Status:** local evidence of the Step 5A Gate, not a portable policy. The run supports the
> `coding`, `studio`, and `vstudio` modes on the machine described; the overall Gate remains
> `GATE-PARTIAL` until the same protocol is tested on materially different hardware. The private
> records and logs stay in the local data directory and are not included in the repository.

## 1. Contracts tested

- Launcher: commit `6f69d7724a857d7e9527cc6d7fa01f082227c367` for D-046; the subsequent diagnostic
  fix `2d4cc22a8b76670172a1b0375f2e71c7e4c8e794` changes neither the protocol nor the candidates.
- Protocol: `calibration/v3`; record: `calibration-record/v2`; benchmark: `benchmark/v1`.
- Model: `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`, pinned by the lock.
- Engine: `llama.cpp b10011`, CUDA backend.
- Host: Windows 11 build 10.0.26200, 31.92 GiB RAM, an RTX 2060 SUPER with 8 GiB VRAM, and a single
  selected GPU.
- Command:

  ```console
  uv run --frozen qwen-launcher calibrate --mode all --no-activate
  ```

The preflight observed 26.34 GiB of available RAM, 7.30 GiB of free VRAM, and a stable WDDM
population of 20 identifiable contexts. Chrome was not present in the GPU contexts of the clean run.

## 2. Provenance of D-046 and environmental hygiene

Two earlier attempts had been invalidated by the respawn of a desktop executable already present in
the baseline. D-046 replaced the PID as a lifecycle proxy with a run-scoped opaque executable
identity, keeping new files, unreadable identities, and additional multiplicities invalidating.

The first attempt after D-046 progressed beyond the earlier failure points, then was correctly
invalidated when Chrome was opened during `studio`: that was a new executable file, not a respawn of
the baseline. No partial candidate was written. A subsequent 10-minute idle soak observed no change
in the population. The clean run therefore started with Chrome closed and suffered no contamination.

## 3. Outcome of the clean run

The command exited with code 0 in 1,623 seconds (27 minutes and 3 seconds). Every mode reached the
maximum context of the scale, `ctx=131072`, without degradation and with contiguous probe sequences
within the cap of 12.

| Mode | Screening | Confirmation | Probes | Candidate envelope | Rule |
|---|---:|---:|---:|---|---|
| coding | 3.53 min | 5.08 min | 7 | `ctx=131072`, `n_cpu_moe=37` | `dominance-unanimous-rounds` |
| studio | 3.06 min | 4.94 min | 6 | `ctx=131072`, `n_cpu_moe=37` | `equivalent-prefer-minimum-free-vram` |
| vstudio | 4.33 min | 5.19 min | 7 | `ctx=131072`, `n_cpu_moe=39` | `single-finalist` |

### Coding

- Probes `(n_cpu_moe, feasible)`: `41✓, 20✗, 31✗, 36✗, 39✓, 38✓, 37✓`.
- Finalists 37 and 38 in ABBA order; their respective positions `1/4` and `2/3`.
- Per-round medians: 37 = `25.814 / 24.873` tok/s; 38 = `25.088 / 24.555` tok/s.
- Winner of both rounds: 37.

### Studio

- Probes: `41✓, 20✗, 31✗, 36✓, 34✗, 35✗`.
- Finalists 36 and 37 in ABBA order.
- Per-round medians: 36 = `27.381 / 26.194` tok/s; 37 = `25.236 / 26.578` tok/s.
- The disagreeing rounds disabled dominance; the larger VRAM margin selected 37.

### Vstudio

- Probes: `41✓, 20✗, 31✗, 36✗, 39✓, 38✓, 37✗`.
- Finalists 38 and 39 both completed two benchmarks.
- Finalist 38 was discarded because the second session reached 0.488 GiB of free VRAM, below the
  0.5 GiB reserve; the first session had reached 0.505 GiB.
- The only valid finalist, 39, was selected.

## 4. Reserves, release, and telemetry

The minimums below consider only feasible probes and valid finalist sessions:

| Mode | Minimum available RAM | Minimum free VRAM | Maximum release above baseline | Baseline drift |
|---|---:|---:|---:|---:|
| coding | 9.291 GiB | 0.950 GiB | 0 GiB | 0 GiB |
| studio | 9.331 GiB | 0.503 GiB | 0.0078 GiB | 0.0146 GiB |
| vstudio | 8.602 GiB | 0.505 GiB | 0.0176 GiB | 0.0176 GiB |

The 2 GiB RAM reserve was not approached on this host. The VRAM reserve, by contrast, concretely
governed the boundary, including the vstudio 38 discard; the studio and vstudio margins are tight and
do not authorize lowering the constant. Release and drift stayed below 0.125 GiB.

Best-effort telemetry was present in all 32 trials and stayed evidence-only. All 32 logs contain the
MTP markers and all 11 vstudio logs contain the mmproj/vision markers; the valid vstudio trials also
passed the real vision request required by the protocol. The single evidence slot contains 11 coding
logs, 10 studio, and 11 vstudio, with no missing references.

## 5. Records and lifecycle

`--no-activate` produced three valid candidates without changing any launch plan:

| Mode | Candidate SHA-256 | Active after the run | Previous |
|---|---|---|---|
| coding | `666b4588c9e4f6ec2fca4d24596bfffffbeee0bb9f052a76805425a8f0987b8f` | historical v1, unchanged | absent |
| studio | `6fc8d291c90aa8def63be021f866976f947bbc5ab70c92da35af4e870b3c6632` | absent | absent |
| vstudio | `e904d4d18e4f295aa12250b80d0e2bedeb716fb3fda0ba66e7dbca4aaa0117d2` | absent | absent |

The historical coding active record stayed byte-identical, SHA-256
`6da4a4229ca9eb2c9d65f5780c8b735193cf13d4f013cacb8db75609fa5afbc9`. The loader reconstructed the
schema, probes, ABBA, medians, reserves, drift, and selection of every candidate. Commit `2d4cc22`
then verified that `doctor` shows the superseded v1 coding active record and the valid pending v2
candidate at the same time; no calibration was re-run and no candidate was activated.

## 6. Software verifications

- Locally on Windows, with uv 0.11.28 and CPython 3.12.13: Ruff check and format green, 314 tests,
  `validate`, the build, and the isolated wheel verification green.
- D-046, commit `6f69d77`: GitHub Actions run `29684539755` green on Ubuntu 22.04 and Windows 2022.
- Lifecycle diagnostics, commit `2d4cc22`: GitHub Actions run `29684866498` green on the same
  matrix.

## 7. Verdict and portability limit

- Windows 11 / CUDA / coding: `CALIBRATION-ACCEPTED`.
- Windows 11 / CUDA / studio: `CALIBRATION-ACCEPTED`.
- Windows 11 / CUDA / vstudio: `CALIBRATION-ACCEPTED`.
- Overall Calibration Gate: `GATE-PARTIAL`.

The result validates screening, ABBA, the reserves, lifecycle, MTP, vision, and D-046 locally, but
it does not prove that the shared constants are sufficient on different components or capacities.
D-047 explicitly accepts this partial coverage as sufficient for Step 5B, now completed with the
method policy, a privacy-safe report, and ordering-only seeds, without exporting the 32/8 envelope. A
new run with `--no-activate` on materially different hardware remains a future, non-blocking
follow-up. The local candidates stay inactive until the maintainer separately authorizes their
promotion.
