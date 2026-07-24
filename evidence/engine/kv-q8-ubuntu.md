# Ubuntu mini-spike — Q8 KV cache on llama.cpp b10011

## Decision

**Ubuntu CUDA: `GO` for the `q8_0` K/V cache while keeping `--mmap`.**

**`--no-mmap`: `NO-GO`** on this machine: much slower loading, much lower available memory, worse
throughput, and VRAM still above the baseline after 10 seconds.

The GO covers only Ubuntu 24.04, llama.cpp `b10011`, commit
`bf2c86ddc0685f580595954056c2e77ebabfab4f`, the pinned `UD-Q4_K_M` model, and the CUDA backend. It
does not yet authorize changing the global lock: the Windows smoke test on the CUDA 13.3
server/runtime pair remains mandatory before the Windows contract can be declared verified.

## Machine and protocol

- Ubuntu 24.04 x86-64;
- Intel Core i5-10400F, about 32 GiB RAM;
- NVIDIA GeForce RTX 2060 SUPER 8 GiB, driver 595.71.05;
- `ctx=131072`, `n_cpu_moe ∈ {48, 38}` for the CUDA coding comparisons;
- the same model, sampling, MTP, and rest of the contract for every configuration;
- `benchmark/v1`: one excluded warm-up and five valid 256-token measurements;
- RAM/VRAM polling at 250 ms, health, MTP, stop, and release for up to 10 seconds;
- a UI smoke test for `studio`, UI+vision for `vstudio`, and CPU compatibility at `ctx=8192`.

The complete commands, with only the private paths redacted, are in `coding-results.json` and
`extended-results.json`. The prompt and request keep the pinned `benchmark/v1` digests.

## CUDA coding comparison

| Configuration | n_cpu_moe | Load s | Median tok/s | Min free VRAM GiB | Min available RAM GiB | Outcome |
|---|---:|---:|---:|---:|---:|---|
| current, default mmap/cache | 48 | 2.32 | 31.751 | 1.638 | 27.905 | PASS |
| current, default mmap/cache | 38 | 2.17 | 35.889 | 0.235 | 27.932 | functional PASS, below the 0.25 reserve |
| **Q8 K/V + mmap** | 48 | 2.21 | 34.809 | 2.797 | 27.960 | PASS |
| **Q8 K/V + mmap** | 38 | 2.20 | 37.399 | 1.426 | 27.973 | PASS |
| Q8 K/V + no-mmap | 48 | 81.77 | 32.476 | 2.608 | 8.406 | NO-GO |
| Q8 K/V + no-mmap | 38 | 48.74 | 33.514 | 1.112 | 8.685 | NO-GO |

At equal `n_cpu_moe`, Q8+mmap raised the median by about 9.6% at 48 and 4.2% at 38, freeing about
1.16–1.19 GiB of minimum VRAM. MTP stayed enabled in every measurement. The new PASS of the current
contract at 38 does not contradict the earlier OOM: the minimum margin was only 0.235 GiB, below the
0.25 reserve, and it confirms how sensitive the boundary is to ambient load.

`benchmark/v1` does not measure semantic quality. The GO attests functional compatibility, vision,
MTP, speed, and memory, not zero quality regression; any quality promise would require a separate
approved protocol.

For no-mmap the final sample after 10 seconds was about 0.18–0.20 GiB above the baseline; with the
0.125 GiB tolerance used in the corrective spike those candidates would be discarded. The engine's
generic suggestion to use no-mmap therefore does not override this machine's measurements.

## Mode and CPU smoke tests with Q8+mmap

| Backend/mode | Envelope | Median tok/s | Min free VRAM GiB | Checks | Outcome |
|---|---|---:|---:|---|---|
| CUDA studio | ctx 131072 / n_cpu_moe 38 | 35.141 | 1.227 | health, UI 200, MTP, benchmark, stop | PASS |
| CUDA vstudio | ctx 131072 / n_cpu_moe 38 | 35.237 | 0.148 | health, UI 200, vision `Rosso`, MTP, benchmark, stop | functional PASS |
| CPU coding | ctx 8192 | 10.084 | n/a | CPU asset, health, MTP, benchmark, stop | compatibility PASS |

`vstudio` at 38 is functional but too close to the limit for a 0.25 GiB reserve: the subsequent
calibration must use a more conservative per-mode list and include higher values around the
boundary. This datum is not a profile and does not select an envelope yet.

CPU compatibility is confirmed, but the observed Q8 advantage concerns CUDA VRAM and these
measurements do not justify changing the CPU branch. Together with the Windows counter-check kept
alongside, this evidence supports the current contract: the Q8 K/V cache only in
`command_contract.backend_args.cuda`, `--mmap` still enabled, and the CPU branch unchanged.
`--no-mmap` stays excluded.

## Evidence

- `evidence/engine/kv-q8-ubuntu/coding-results.json`;
- `evidence/engine/kv-q8-ubuntu/extended-results.json`;
- `evidence/engine/kv-q8-ubuntu/logs/`;
- `evidence/engine/kv-q8-ubuntu/system-info.txt`;
- `evidence/engine/kv-q8-ubuntu/flag-help.txt`;
- `evidence/engine/kv-q8-ubuntu/SHA256SUMS`.
