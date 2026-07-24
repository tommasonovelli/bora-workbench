# Spike cross-context — TEMPLATE NON MISURATO

**Stato:** `PENDING-HUMAN-RUN`

**Verdetto:** `PENDING` (`GO` oppure `NO-GO` dopo revisione umana)

Questo albero è un template redatto, non evidenza e non un risultato. Seguire
[`scripts/spike_ctx/protocol.md`](../../../scripts/spike_ctx/protocol.md).

## Scope da compilare

- OS/build: `<redacted measured value>`
- CPU/RAM: `<measured value>`
- GPU/driver/VRAM: `<measured value>`
- engine: `llama.cpp b10011`, commit `bf2c86ddc0685f580595954056c2e77ebabfab4f`
- model digest: `0b21525e972670ed59e1812e170b27c26355381f0656ecc4e25617ece7dac58b`

## Risultati da compilare

| Configurazione | ctx | n_cpu_moe | e2e corto mediano ms | prefill 8K tok/s | decode tok/s | min VRAM GiB | min RAM GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| best 131K | 131072 | `<n>` | `<value>` | `<value>` | `<value>` | `<value>` | `<value>` |
| best 65K | 65536 | `<n>` | `<value>` | `<value>` | `<value>` | `<value>` | `<value>` |
| best 32K | 32768 | `<n>` | `<value>` | `<value>` | `<value>` | `<value>` | `<value>` |

## Appendici da compilare

- MTP 131K off↔2: `<delta e2e>`, `<delta decode>`, acceptance `<accepted/draft>`.
- MTP 65K off↔2: `<delta e2e>`, `<delta decode>`, acceptance `<accepted/draft>`.
- Reasoning off: `<reasoning-off | reasoning-off-plus-budget-0>`, nessun `<think>`: `<true|false>`.

## Decisione da compilare

- criterio e calcolo applicato: `<one of the three D-061 criteria, or none>`;
- verdetto umano: `<GO|NO-GO>`;
- limiti e anomalie: `<measured facts only>`.

Prima del commit sostituire o rimuovere ogni placeholder, revisionare privacy, aggiornare il JSON e
rigenerare `SHA256SUMS`. Non dichiarare Gate per un template o un dry-run.
