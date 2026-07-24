# Cross-context spike protocol (`D-061`)

This package prepares a real measurement; it does **not** authorize or implement
`calibration/v6-lite`. Running it and issuing the verdict are the maintainer's job. Before the run,
close GPU workloads, check `qwen-launcher validate`, the model/mmproj, and `llama.cpp b10011`, then
use a fresh private output directory:

```bash
uv run --frozen python -m scripts.spike_ctx --output /tmp/qwen-spike-ctx-evidence
```

To exercise the parser, requests, bisection, and structure without a model or GPU:

```bash
uv run --frozen python -m scripts.spike_ctx \
  --dry-run --output /tmp/qwen-spike-ctx-dry
```

## Measurements

The runner uses the real builder and lifecycle, a temporary loopback port, and a runtime directory
managed by `tempfile` (under `/tmp` on Ubuntu). Every process applies a 0.5 GiB VRAM reserve,
2.0 GiB RAM, and a 0.125 GiB release tolerance. The contexts are 131072, 65536, and 32768. At 131K
it measures the historical boundary 37 and the conservative 41; at 65K/32K it first tries the
conservative 41 and then uses at most six binary decisions over the `[0,41]` domain, with a single
retry per retryable outcome and classification by class.

Every configuration runs:

1. a short warm-up, excluded;
2. three short 128-token requests;
3. one deterministic request of about 8K tokens with output 64;
4. `cache_prompt:false`, `ignore_eos:true`, seed `424242`;
5. end-to-end wall-clock and the response's `timings` fields;
6. minimum RAM/VRAM, stop, and release verification.

Appendix A repeats the 131K and 65K boundaries with MTP disabled. MTP acceptance is derived only
from `draft_n_accepted / draft_n`; the logs are not analyzed. Appendix B starts 32K with
`--reasoning off`, issues three requests, and looks for `<think>` in the responses; it adds
`--reasoning-budget 0` only when the first mechanism is not enough.

If the comparison falls between steps, run a reviewed extension at 98304 or 49152 into a new output
directory before the verdict; do not reconstruct missing measurements by hand:

```bash
uv run --frozen python -m scripts.spike_ctx \
  --refine-ctx 98304 --output /tmp/qwen-spike-ctx-refine-98k
```

Use `49152` only for the 65K↔32K refinement. The base runner does not automatically declare that the
refinement is necessary.

## Human verdict

Compare the best of 65K and 32K with the best 131K. It is **GO** when at least one condition holds:

- the short end-to-end median is `≤ 0.92 ×` the 131K one;
- the prefill of the 8K request is `≥ 1.25 ×` the 131K one;
- performance is within a 3% deadband and there is at least 0.5 GiB more minimum free VRAM.

Otherwise it is **NO-GO**. The 3% is a materially minimum improvement, not statistical
significance. MTP and reasoning are informational data and do not change the verdict automatically.

## Redacting and committing the evidence

The initial output is private: responses and logs can contain local text or paths. Copy the template
from `evidence/engine/cross-context-spike-template/`, replace the placeholders only with
measurements that exist, remove hostnames, usernames, and absolute paths, then regenerate
`SHA256SUMS` over the final bytes. Check every file by hand before committing. The final document
must state `GO` or `NO-GO` explicitly, along with the redacted hardware/OS, the criteria applied, the
limits, and the reasoning mechanism.

Only a **committed GO**, together with a new normative decision, authorizes Phase 2. A dry-run, an
incomplete run, or the mere presence of `results.json` is not a Gate.
