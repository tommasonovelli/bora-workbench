# Verified evidence

This directory holds measured output, acquired sources, and SHA-256 manifests that back the
distributed contracts. It is not user documentation and it is not a collection of plans.

- `engine/spike-0.*` and `engine/spike-0/`: the selection and real matrix of `llama.cpp b10011`;
- `engine/kv-q8-*`: the evidence backing the Q8 K/V cache with mmap on the CUDA branch;
- `calibration/windows-11-rtx-2060-super-v3/`: the checksum-bound sources of the public v3 report;
- `tui/ubuntu-motion.json`: the local Ubuntu pseudo-terminal CPU observation for optional motion;
- `tui/ubuntu-acceptance.json`: the scoped Ubuntu pseudo-terminal presentation and handoff checks.

Raw files covered by a manifest must be preserved byte for byte. Some accepted documents contain
references to historical paths under `docs/`: those references are part of the hashed bytes and are
not rewritten. The authoritative current paths are the ones in the manifests and in the
`source_references` of the distributed report.

To understand current behavior use [`docs/`](../docs/README.md). To change a lock or add new
evidence follow [Development and contributions](../docs/development.md).
