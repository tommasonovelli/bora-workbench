# Cross-context spike — UNMEASURED TEMPLATE

**Status:** `PENDING-HUMAN-RUN`

**Verdict:** `PENDING` (`GO` or `NO-GO` after human review)

This tree is a redacted template, not evidence and not a result. Follow
[`scripts/spike_ctx/protocol.md`](../../../scripts/spike_ctx/protocol.md).

## Scope to fill in

- OS/build: `<redacted measured value>`
- CPU/RAM: `<measured value>`
- GPU/driver/VRAM: `<measured value>`
- engine: `llama.cpp b10011`, commit `bf2c86ddc0685f580595954056c2e77ebabfab4f`
- model digest: `0b21525e972670ed59e1812e170b27c26355381f0656ecc4e25617ece7dac58b`

## Results to fill in

| Configuration | ctx | n_cpu_moe | short e2e median ms | 8K prefill tok/s | decode tok/s | min VRAM GiB | min RAM GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| best 131K | 131072 | `<n>` | `<value>` | `<value>` | `<value>` | `<value>` | `<value>` |
| best 65K | 65536 | `<n>` | `<value>` | `<value>` | `<value>` | `<value>` | `<value>` |
| best 32K | 32768 | `<n>` | `<value>` | `<value>` | `<value>` | `<value>` | `<value>` |

## Appendices to fill in

- MTP 131K off↔2: `<delta e2e>`, `<delta decode>`, acceptance `<accepted/draft>`.
- MTP 65K off↔2: `<delta e2e>`, `<delta decode>`, acceptance `<accepted/draft>`.
- Reasoning off: `<reasoning-off | reasoning-off-plus-budget-0>`, no `<think>`: `<true|false>`.

## Decision to fill in

- criterion and calculation applied: `<one of the three D-061 criteria, or none>`;
- human verdict: `<GO|NO-GO>`;
- limits and anomalies: `<measured facts only>`.

Before committing, replace or remove every placeholder, review privacy, update the JSON, and
regenerate `SHA256SUMS`. Do not declare a Gate for a template or a dry-run.
