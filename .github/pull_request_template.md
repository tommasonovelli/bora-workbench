## Tipo di modifica

- [ ] Core
- [ ] Contenuto dichiarativo

> Una PR non deve modificare contemporaneamente core e contenuti.

## Evidenza di calibrazione (se applicabile)

- [ ] Report `calibration-report/v2` privacy-safe e riferito dalla policy con SHA-256 esatto
- [ ] Scope realmente misurato e limite `GATE-PARTIAL` dichiarati
- [ ] Seed di solo ordinamento; nessun `profile/v1`, nearest-match o busta remota
- [ ] Manifest verificato e checklist di `docs/calibration.md#contribuire-nuova-evidenza` completata

## Verifiche

- [ ] `uv run --frozen ruff check .`
- [ ] `uv run --frozen ruff format --check .`
- [ ] `uv run --frozen pytest`
- [ ] Nessun test usa la rete
- [ ] Documentazione aggiornata, se necessaria
