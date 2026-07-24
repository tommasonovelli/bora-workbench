## Type of change

- [ ] Core
- [ ] Declarative content

> A PR must not change core and content at the same time.

## Calibration evidence (if applicable)

- [ ] Privacy-safe `calibration-report/v2` report, referenced by the policy with the exact SHA-256
- [ ] Actually measured scope and `GATE-PARTIAL` limit declared
- [ ] Ordering-only seed; no `profile/v1`, nearest-match, or remote envelope
- [ ] Manifest verified and the `docs/calibration.md#contributing-new-evidence` checklist completed

## Verifications

- [ ] `uv run --frozen ruff check .`
- [ ] `uv run --frozen ruff format --check .`
- [ ] `uv run --frozen pytest`
- [ ] No test uses the network
- [ ] Documentation updated, if needed
