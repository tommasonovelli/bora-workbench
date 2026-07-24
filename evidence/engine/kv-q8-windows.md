# Windows 11 smoke test — Q8 KV cache on llama.cpp b10011 CUDA 13.3

## Decision

**Windows 11 CUDA 13.3: `GO` for the `q8_0` K/V cache while keeping `--mmap`.**

Together with the Ubuntu GO from the previous mini-spike, this evidence completes the requirement of
D-033: the CUDA 13.3 server/runtime pair accepts `--cache-type-k q8_0 --cache-type-v q8_0`, serves
the three modes at `ctx=131072` with correct MTP, UI, and vision, and releases the VRAM within the
window and tolerance. The separate declarative change adopts the two arguments in the CUDA branch of
`engine.lock` only; `--no-mmap` stays out of the contract (Ubuntu NO-GO, not retried here).

The GO concerns the contract's functional compatibility and memory behavior, not performance
promises: the Windows measurements record the ambient load of a real desktop and its dispersion,
data used by the design of `calibration/v2`.

## Machine and protocol

- Windows 11 Pro build 26200, x86-64 — **the same physical hardware as the Ubuntu machine of the
  mini-spike** (dual boot): Intel Core i5-10400F, 31.9 GiB RAM, NVIDIA GeForce RTX 2060 SUPER
  8 GiB; Windows driver 610.47 (Ubuntu: 595.71.05);
- the managed b10011 engine (`bf2c86ddc`), the CUDA 13.3 server/runtime pair and the CPU prebuilt,
  with the lock's digests; the model and mmproj verified against the lock's digests
  (`system-info.txt`);
- `ctx=131072`, Q8+mmap, `n_cpu_moe ∈ {48, 38}` for coding and vstudio, `38` for studio, plus a
  reference with the current contract at `48`; CPU compatibility at `ctx=8192`;
- `benchmark/v1` (pinned digests): one excluded warm-up and five valid 256-token measurements;
- VRAM/RAM polling at 250 ms, health, MTP, stop, and release for up to 10 s with a 0.125 GiB
  tolerance;
- unlike the Ubuntu run (quiet X, about 0.6 GiB ambient), the Windows desktop had a real ambient
  graphics load of about 1.4–1.5 GiB VRAM and about 20 GiB RAM already committed; the absolute
  values must be read in that context and every run records its own baseline;
- stop through CTRL_BREAK: on Windows the process exits with `0xC000013A`
  (`STATUS_CONTROL_C_EXIT`), the console equivalent of the signal termination recorded as exit 0 on
  Ubuntu.

The complete commands, with only the private paths redacted, are in `results.json`; the prompt and
request keep the pinned `benchmark/v1` digests.

## The `n_cpu_moe` domain on the pinned model

The model's GGUF metadata (`general.architecture=qwen35moe`) declares `block_count=41`,
`expert_count=256`, `expert_used_count=8`, `context_length=262144`. The probes at `ctx=8192`
measure:

| Probe | n_cpu_moe | Peak VRAM used GiB | Min free VRAM GiB |
|---|---:|---:|---:|
| `ncmoe-domain-48` | 48 | 4.479 | 3.341 |
| `ncmoe-domain-49` | 49 | 4.485 | 3.334 |
| `ncmoe-domain-41` | 41 | 4.477 | 3.343 |
| `ncmoe-domain-40` | 40 | 4.731 | 3.088 |

48, 49, and 41 are the same configuration within measurement noise; VRAM only grows below 41. **The
axis's legal domain is `[0, 41]`**: every higher value is an alias of "all MoE layers on the CPU".
The historical `n_cpu_moe=48` baseline stays valid as a conservative alias of the maximum; in the
historical `48, 44, 42, 40, 39, 38, 37` scale the first three values were aliases of the same
envelope.

## CUDA coding comparison (ctx 131072)

| Configuration | n_cpu_moe | Load s | Median tok/s | Min free VRAM GiB | Min avail. RAM GiB | Outcome |
|---|---:|---:|---:|---:|---:|---|
| current, default mmap/cache | 48 | 5.28 | 20.011 | 0.505 | 4.97 | PASS |
| **Q8 K/V + mmap** | 48 | 5.54 | 20.155 | 1.687 | 5.11 | PASS |
| **Q8 K/V + mmap** | 38 | 6.06 | 21.796 | 0.248 | 4.90 | functional PASS, below the reserve |

At equal `n_cpu_moe=48`, Q8+mmap freed 1.18 GiB of minimum VRAM on Windows as well (Ubuntu:
1.16 GiB), with an equivalent median within the noise. MTP was enabled in every measurement (Q8:
197/156, identical to Ubuntu at equal seed). The PASS of `38` with a 0.248 GiB margin confirms that
the boundary is sensitive to ambient load, as already observed on Ubuntu (0.235 with the current
contract).

## Mode smoke tests with Q8+mmap (ctx 131072) and CPU

| Backend/mode | Envelope | Median tok/s | Min free VRAM GiB | Checks | Outcome |
|---|---|---:|---:|---|---|
| CUDA studio | 131072 / 38 | 22.153 | 0.307 | health, UI 200, MTP, benchmark, stop | functional PASS, below the reserve |
| CUDA vstudio | 131072 / 48 | 22.110 | 0.378 | health, UI 200, vision `Rosso`, MTP, benchmark, stop | functional PASS, below the reserve |
| CUDA vstudio | 131072 / 38 | 22.668 | 0.072 | health, UI 200, vision `Rosso`, MTP, benchmark, stop | functional PASS, almost no margin |
| CPU coding | 8192 | 8.885 | n/a | CPU asset, health, MTP, benchmark, stop | compatibility PASS |

Under the desktop's ambient load, **every** aggressive candidate stays below the conservative
reserve: on this machine under these conditions, a calibration with a 0.5 GiB reserve would select
more conservative envelopes than the functional PASS results listed here. That is the intended
behavior: the smoke test proves the contract, the local search chooses the envelope.

During the CPU run the available RAM dropped to 0.01 GiB (quiet Ubuntu: 16.85): the compatibility
PASS is real, but the system was on the edge of paging. This is the most direct evidence in favor of
mandatory RAM monitoring for every backend in the following protocol.

## Measurement dispersion and ambient noise

Relative dispersion `(max − min) / median` of the five measurements:

| Run | Dispersion |
|---|---:|
| coding current 48 / Q8 48 | 11.7% / 11.5% |
| coding Q8 38 | 9.6% |
| studio Q8 38 | 18.0% |
| vstudio Q8 48 / 38 | 10.5% / 18.8% |
| CPU coding Q8 | 6.3% |

On the same physical hardware, the quiet Ubuntu host measured 0.14–2.4%. Dispersion is therefore a
property of the environment, not of the configuration: a fixed equivalence band would misjudge at
least one of the two cases. The current protocol addresses this limit with paired time rounds and
dominance by unanimity, described in `docs/calibration.md`.

`benchmark/v1` does not measure semantic quality; the GO attests functional compatibility, vision,
MTP, and memory behavior, not zero quality regression.

## Evidence

- `evidence/engine/kv-q8-windows/results.json`;
- `evidence/engine/kv-q8-windows/logs/`;
- `evidence/engine/kv-q8-windows/system-info.txt`;
- `evidence/engine/kv-q8-windows/flag-help.txt`;
- `evidence/engine/kv-q8-windows/SHA256SUMS`.
