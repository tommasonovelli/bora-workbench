# Contribuire

`IMPLEMENTATION_SPEC.md` è l'unico piano normativo. Il progetto procede uno step alla volta: una PR
non può anticipare milestone, cambiare versioni appuntate o trasformare assunzioni in compatibilità.

## Prima della modifica

1. leggere l'intero piano e il tracker;
2. eseguire `git status`, conservando modifiche preesistenti;
3. eseguire sync, Ruff e pytest nel lock congelato;
4. leggere lock, schemi, test ed evidenza pertinenti;
5. fermarsi e descrivere qualunque contraddizione fra fonti.

Non inventare flag, checksum, commit, benchmark, hardware supportato, profili, salute o claim di
portabilità. I test non usano rete, GPU, modello, server reale o privilegi amministrativi.

## Una PR: core oppure contenuto

Una pull request modifica **core oppure contenuto dichiarativo, mai entrambi**.

- Core: Python, lifecycle, installer, workflow e test comportamentali.
- Contenuto: modi, policy, report, manifest, evidenza e relativa documentazione.

Schemi incompatibili richiedono una nuova versione e una milestone che la autorizzi. Non rinominare,
spostare o riformattare file estranei allo scopo della PR.

## Evidenza di calibrazione

Un contributo usa esclusivamente il protocollo pubblico approvato `calibration/v3`,
`benchmark/v1`, il modello appuntato e `llama.cpp b10011`. Numeri e scope devono provenire da un run
reale sulla release lock; un campo mancante non viene ricostruito o inventato.

Sono obbligatori:

- bundle/report validato e privacy-safe;
- SHA-256 dei byte esatti e manifest verificato;
- hardware e limite di copertura dichiarati senza hostname, username o percorsi privati;
- nessun record locale, config o log grezzo nel repository;
- `GATE-PARTIAL` visibile finché manca evidenza materialmente diversa;
- approvazione personale del maintainer prima dell'accettazione.

Un report condiviso è evidenza e seed di solo ordine: non diventa una busta finale remota. Non sono
accettati nuovi `profile/v1`, nearest-match, promesse tok/s o applicazione diretta del vincitore di un
altro PC. La procedura completa e il testo PR sono in
[`docs/calibration-contributing.md`](docs/calibration-contributing.md).

## Qualità e sicurezza

- funzioni piccole, tipi precisi e docstring su ogni modulo, classe e funzione;
- nessun `shell=True`, `eval`, `exec`, `sudo`, elevazione o bind `0.0.0.0`;
- TLS e checksum obbligatori, estrazione confinata e cancellazioni solo nelle radici gestite;
- nessuna modifica automatica a `config.toml` o alla cache Hugging Face;
- dipendenze nuove soltanto se autorizzate dallo step, con `pyproject.toml` e `uv.lock` insieme;
- errori attesi azionabili su stderr, senza traceback e con gli exit code normativi.

## Verifiche

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
```

Se packaging o risorse cambiano:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
```

Segnalare esplicitamente controlli non eseguiti; non sostituire CI o Gate umani con “funziona sulla
mia macchina”.

## Revisione e Git

Il branch `main` richiede CI Ubuntu/Windows verde e revisione code owner per i contributori. Nuovi
commit annullano l'approvazione precedente. Il bypass amministratore evita di bloccare l'unico
maintainer, ma non elimina i controlli locali e CI.

Usare Conventional Commits con oggetto concreto e, per cambi non banali, un corpo che spieghi
vincoli, motivazione e verifiche. Push, tag, release, upload, impostazioni remote e pubblicazione
richiedono autorizzazione esplicita nella sessione corrente.
