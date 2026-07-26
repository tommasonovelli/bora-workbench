## Type of change

- [ ] Core
- [ ] Declarative content

> A PR must not change core and content at the same time.

## Calibration evidence (if applicable)

- [ ] Schema authorized for the measured method before any report is constructed
- [ ] Privacy-safe report, referenced by the policy with the exact SHA-256
- [ ] Actually measured scope and `GATE-PARTIAL` limit declared
- [ ] Historical fields are not presented as current runtime inputs or remote envelopes
- [ ] Manifest verified and the `docs/calibration.md#contributing-new-evidence` checklist completed

## Verifications

- [ ] `uv run --frozen ruff check .`
- [ ] `uv run --frozen ruff format --check .`
- [ ] `uv run --frozen pytest`
- [ ] No test uses the network
- [ ] Documentation updated, if needed
