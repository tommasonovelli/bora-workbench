# `windows-11-rtx-2060-super-v3` evidence

This directory binds the public policy, the structured report, and the two reviewed sources of the
v3 calibration together through SHA-256. It contains no local records or raw logs.

From the repository root, verify with:

```bash
sha256sum -c evidence/calibration/windows-11-rtx-2060-super-v3/SHA256SUMS
```

## Measured scope

- Windows 11 build 10.0.26200;
- the CUDA backend and NVIDIA driver 610.47;
- an NVIDIA GeForce RTX 2060 SUPER with 8 GiB VRAM;
- 31.92 GiB RAM;
- the `coding`, `studio`, and `vstudio` modes;
- the exact model and engine pinned in the repository.

The local outcome is accepted, but the overall coverage remains `GATE-PARTIAL`: the constants have
not been repeated on materially different hardware.

## Permitted use

The report keeps the observed envelopes as evidence only. The loader projects `seed_n_cpu_moe` alone,
to bring one probe forward in a new, complete local search. It transfers no context, hardware, tok/s,
or envelope into another machine's `LaunchPlan`.

`gate.md` and `protocol.md` keep their original structure because their digests are referenced by
the report. Any historical paths in the text are part of the hashed evidence.
