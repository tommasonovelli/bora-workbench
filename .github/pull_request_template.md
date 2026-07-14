## Tipo di modifica

- [ ] Core
- [ ] Contenuto dichiarativo

> Una PR non deve modificare contemporaneamente core e contenuti.

## Verifiche

- [ ] `uv run --frozen ruff check .`
- [ ] `uv run --frozen ruff format --check .`
- [ ] `uv run --frozen pytest`
- [ ] Nessun test usa la rete
- [ ] Documentazione aggiornata, se necessaria
