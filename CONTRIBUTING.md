# Contribuire

Il progetto segue il piano normativo `IMPLEMENTATION_SPEC.md` e procede uno step
alla volta. Prima di una modifica:

1. leggere l'intero piano e il tracker iniziale;
2. non anticipare feature di step successivi;
3. non inventare flag, benchmark o compatibilità del motore;
4. non usare rete nei test;
5. non modificare configurazione utente o cache Hugging Face.

Una pull request modifica **contenuto dichiarativo oppure core, mai entrambi**. I profili devono
contenere misure reali raccolte con il protocollo e la release del lock. Ogni PR richiede
l'approvazione del code owner.

## Verifiche

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Usare Conventional Commits. Push, tag e pubblicazioni richiedono sempre autorizzazione esplicita.
