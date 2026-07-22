# Contribuire a qwen-launcher

Grazie per l'interesse. Prima di aprire una modifica, leggere:

1. [documentazione del progetto](docs/README.md);
2. [architettura](docs/architecture.md);
3. [guida di sviluppo](docs/development.md);
4. `AGENTS.md` e l'intero `IMPLEMENTATION_SPEC.md`.

`IMPLEMENTATION_SPEC.md` è l'unico piano normativo: una PR non deve implementare lavoro futuro non
ancora autorizzato.

## Preparare il checkout

```bash
git status --short
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Se la baseline non è verde, non nascondere il problema: descriverlo prima di aggiungere altre
modifiche. Conservare sempre cambi preesistenti dell'utente.

## Scegliere il tipo di contributo

Una pull request modifica **una sola** delle due aree:

- **core**: Python, installer, workflow e test comportamentali;
- **contenuto dichiarativo**: modi, policy, report, lock, manifest ed evidenza collegata.

La documentazione accompagna l'area scelta. Non mescolare core e contenuto nella stessa PR e non
riformattare, rinominare o spostare file estranei allo scopo.

Per un bug o una proposta, indicare prima comportamento corrente, comportamento atteso, fonti e
impatto. Non presentare un'ipotesi come compatibilità verificata.

## Fonti e prove

Versioni, flag, checksum, endpoint, hardware supportato e misure devono provenire da lock, test o
output reali. La gerarchia completa è in [Sviluppo e contributi](docs/development.md#fonti-di-verità).

In particolare:

- niente `latest` nei file versionati;
- niente flag `llama.cpp` ricordati o copiati dal ramo upstream corrente;
- niente benchmark, profili o claim hardware inventati;
- una contraddizione fra fonti va resa visibile, non risolta silenziosamente.

Le prove grezze stanno in [`evidence/`](evidence/README.md), separate dai manuali correnti.

## Qualità e sicurezza

Seguire le responsabilità dei moduli e i limiti descritti in `AGENTS.md`. In ogni caso:

- funzioni piccole, tipi precisi e docstring;
- nessun `shell=True`, `eval`, `exec`, `sudo` o elevazione;
- nessun bind su `0.0.0.0`;
- TLS e checksum sempre attivi;
- nessuna modifica automatica a `config.toml` o alla cache Hugging Face;
- cancellazioni soltanto nelle radici gestite;
- errori attesi azionabili, senza traceback;
- test offline, deterministici e indipendenti dall'hardware host.

Non aggiungere dipendenze senza un requisito corrente e un'analisi di standard library,
manutenzione, licenza, sicurezza e costo transitivo. `pyproject.toml` e `uv.lock` cambiano insieme.

## Evidenza di calibrazione

Una PR di calibrazione usa il protocollo corrente `calibration/v3` e segue la sezione
[Contribuire nuova evidenza](docs/calibration.md#contribuire-nuova-evidenza).

Sono obbligatori:

- run reale sul modello e motore appuntati;
- report `calibration-report/v2` privacy-safe;
- scope misurato e limite di portabilità espliciti;
- SHA-256 dei byte finali e manifest verificabile;
- nessun record locale, config, log grezzo o dato privato;
- seed di solo ordinamento, mai busta remota o nearest-match;
- approvazione personale del maintainer.

Il launcher non crea login, upload, commit, branch, issue o PR.

## Verifiche finali

Sempre:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
```

Se cambiano packaging, risorse, installer o documenti inclusi nella sdist:

```bash
rm -rf dist
uv build
uv run --frozen python scripts/verify_wheel.py
```

Eseguire inoltre:

```bash
git diff --check
git status --short
git diff --staged
```

Segnalare i test manuali o cross-platform non eseguiti. I fake offline non sostituiscono prove reali
quando cambiano motore, asset, GPU, modello o installer.

## Commit e pull request

Usare Conventional Commits con un oggetto concreto, per esempio:

```text
docs: reorganize current project documentation
fix(engine): preserve active manifest after failed extraction
feat(content): add verified calibration evidence for one host
```

Per modifiche non banali aggiungere un corpo che spieghi cosa è cambiato, perché, vincoli e controlli
eseguiti. Il template PR richiede tipo di modifica e verifiche.

Push, tag, release, upload e impostazioni remote richiedono autorizzazione esplicita. La CI copre
Ubuntu e Windows; i contributori richiedono revisione code owner.

Per i dettagli operativi continuare con [Sviluppo e contributi](docs/development.md).
