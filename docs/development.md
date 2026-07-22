# Sviluppo e contributi

## Orientarsi nel repository

Per chi apre il progetto per la prima volta:

```text
src/qwen_launcher/       pacchetto Python
├── cli.py               gruppo di comandi pubblico
├── config.py            configurazione
├── paths.py             directory per OS
├── hardware.py          CPU, RAM e NVIDIA
├── profiles.py          modi e piano di lancio
├── engine.py            modello e llama.cpp
├── process.py           lifecycle del server
├── calibration.py       API principale di calibrazione
├── benchmark.py         benchmark/v1
├── validation.py        validazione dei contenuti
├── _*.py                responsabilità interne estratte
└── resources/           dati inclusi nella wheel

tests/                   test offline e fake
scripts/                 verifiche di packaging
docs/                    manuali dello stato corrente
evidence/                prove misurate e manifest
IMPLEMENTATION_SPEC.md   solo piano normativo e lavoro futuro
AGENTS.md                regole permanenti per contributori e agenti
```

Prima di modificare codice leggere [Architettura](architecture.md), `AGENTS.md` e l'intera
`IMPLEMENTATION_SPEC.md`.

## Ambiente riproducibile

Versioni di sviluppo:

- CPython `3.12.13`;
- uv `0.11.28`;
- dipendenze congelate in `uv.lock`.

Preparazione:

```bash
uv sync --frozen
```

Baseline e verifica finale:

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
```

Se cambiano packaging, installer, documenti inclusi nella sdist o risorse:

```bash
rm -rf dist                       # PowerShell: Remove-Item dist -Recurse -Force
uv build
uv run --frozen python scripts/verify_wheel.py
```

La verifica installa la wheel in un ambiente temporaneo, legge le risorse, esegue CLI/validazione e
ispeziona la sdist. I test non devono usare rete, GPU, modello, server reale o privilegi
amministrativi.

## Fonti di verità

Quando due fonti divergono, usare quest'ordine:

1. lock, contenuti versionati e report accettati;
2. output misurati in `evidence/`;
3. schemi e test;
4. `IMPLEMENTATION_SPEC.md`;
5. documentazione ufficiale della versione appuntata;
6. documentazione corrente non versionata;
7. assunzioni.

Non correggere un contratto di `llama.cpp` guardando il ramo corrente del progetto upstream. Non
inventare flag, checksum, hardware supportato, endpoint, benchmark o compatibilità.

## Confini delle modifiche

Una pull request modifica **core oppure contenuto dichiarativo**, non entrambi.

- Core: Python, installer, workflow e test comportamentali.
- Contenuto: JSON sotto `resources/content`, lock, report, manifest ed evidenza collegata.
- Documentazione: accompagna il lato che sta cambiando e descrive il comportamento effettivo.

Una correzione a uno schema o a un lock può richiedere una PR dichiarativa distinta dalla modifica
Python che lo consumerà. Evitare rename, refactoring o formattazione estranei allo scopo.

## Regole del core

Il codice privilegia leggibilità e responsabilità strette:

- massimo 200 righe per file e 40 per funzione nel codice scritto a mano;
- massimo tre parametri di produzione, esclusi `self`/`cls`;
- massimo tre livelli di nesting;
- funzioni piccole, tipi precisi e dataclass frozen/slotted per modelli runtime;
- docstring per moduli, classi e funzioni;
- errori attesi azionabili, su stderr e senza traceback;
- niente framework, plugin, async o astrazioni senza requisito corrente.

La CLI raccoglie input, presenta risultati e mappa gli errori; non deve assorbire logica di
configurazione, piattaforma, lifecycle o calibrazione.

## Modificare un modo

I modi sono JSON sotto:

```text
src/qwen_launcher/resources/content/modes/
```

`mode/v1` contiene soltanto:

```json
{
  "schema": "mode/v1",
  "id": "coding",
  "description": "...",
  "services": {"ui": false, "vision": false},
  "sampling": {"temp": 0.6, "top_p": 0.95, "top_k": 20}
}
```

L'id deve coincidere col filename. Prestazioni, memoria, flag motore e hardware non appartengono al
modo. Un nuovo campo incompatibile richiede un nuovo schema autorizzato dal piano; non va aggiunto a
`mode/v1` per comodità.

Dopo la modifica eseguire almeno `validate`, test, build e verifica wheel.

## Schemi e contenuti

Gli schemi vivono in `resources/schemas/`, usano Draft 2020-12 e `additionalProperties: false`.
Cambiare in modo incompatibile un contratto esistente è vietato: serve un nuovo identificatore di
schema e una strategia di lettura esplicita.

I loader costruiscono modelli runtime solo dopo validazione. I default appartengono al loader o al
codice, non a una correzione silenziosa di input sconosciuto.

Non proporre nuovi `profile/v1` come configurazioni trasferibili. La busta runtime viene soltanto da
un record locale v2 attivo; report e profili condivisi sono evidenza o seed.

## Aggiornare `engine.lock`

`engine.lock` non segue `latest`. Un aggiornamento volontario richiede una nuova prova reale su tutte
le coppie supportate prima di cambiare il lock.

Procedura:

1. scegliere e approvare una release precisa;
2. registrare tag, commit completo, `--version`, `--help`, licenze e asset ufficiali;
3. acquisire gli archivi via HTTPS e verificarne SHA-256;
4. provare Ubuntu e Windows, CPU e CUDA, nei tre modi;
5. verificare salute, API, metriche, UI, vision, MTP, sampling, GPU, log e stop;
6. eseguire `benchmark/v1` senza interpretarlo come promessa prestazionale;
7. salvare output e manifest sotto `evidence/engine/`;
8. aggiornare insieme lock, notice, test del vocabolario flag e documentazione corrente;
9. ripetere installazioni reali e smoke `coding` su ogni target.

Per Ubuntu CUDA verificare prima se la nuova release offre un prebuilt: la build dal sorgente è una
conseguenza dell'asset mancante in `b10011`, non una preferenza permanente. Per Windows CUDA, server
e runtime devono appartenere alla stessa coppia verificata.

Una divergenza fra output, archivio, digest e lock interrompe l'aggiornamento.

## Contribuire evidenza di calibrazione

Seguire la sezione [Contribuire nuova evidenza](calibration.md#contribuire-nuova-evidenza). In
sintesi, una PR di evidenza:

- usa `calibration/v4`, `benchmark/v1`, modello e motore appuntati;
- contiene un report `calibration-report/v2` privacy-safe;
- dichiara lo scope realmente misurato e il limite di portabilità;
- aggiorna policy e SHA-256 dei byte esatti;
- conserva fonti revisionate in `evidence/calibration/<id>/`;
- non include record, config o log privati;
- non contiene modifiche core.

Un report condiviso può modificare soltanto l'ordine della ricerca completa. Non diventa un piano,
non promette tok/s e non autorizza nearest-match.

## Evidenza misurata

`evidence/` non è documentazione utente né un archivio di piani. Contiene byte che sostengono:

- contratto `llama.cpp b10011` e matrice funzionale;
- scelta della cache KV Q8 su CUDA;
- report di calibrazione pubblico e relativi digest.

I file coperti da manifest o referenziati da un report vanno trattati come immutabili. Se un percorso
deve cambiare, aggiornare riferimenti e manifest senza alterare i byte sorgente; se cambiano i byte,
ripetere la verifica e dichiarare una nuova evidenza invece di riscrivere quella accettata.

## Dipendenze

Le dipendenze runtime correnti sono `typer`, `rich`, `psutil`, `httpx` e `jsonschema`; quelle di
sviluppo sono `pytest` e `ruff`.

Prima di aggiungerne una:

1. dimostrare perché la standard library non basta;
2. verificare manutenzione, licenza, sicurezza e costo transitivo;
3. ottenere autorizzazione dalla specifica normativa attiva;
4. aggiornare `pyproject.toml` e `uv.lock` insieme;
5. provare l'ambiente congelato su Ubuntu e Windows.

## Packaging e risorse

Il backend è `uv_build` con layout `src/`. La wheel deve contenere tutto sotto
`qwen_launcher/resources/`; la sdist include inoltre installer, documentazione, piano ed evidenza.

Usare `importlib.resources.files()` e mantenere le risorse come `Traversable`. `as_file()` è ammesso
solo dentro il suo context manager. Importare il package deve restare privo di side effect.

Quando si aggiunge un manuale corrente, aggiornare l'elenco richiesto da `scripts/verify_wheel.py` e
la navigazione sequenziale in `docs/`.

## CI e controlli manuali

La CI esegue sync frozen, Ruff, pytest, validazione, build e verifica wheel su Ubuntu 22.04 e Windows
Server 2022. I fake provano le failure path senza sostituire i gate reali quando cambiano motore,
asset, installer, GPU o comportamento del modello.

Nel resoconto indicare sempre:

- file e comportamento cambiati;
- controlli eseguiti;
- test manuali o cross-platform mancanti;
- assunzioni, evidenza non disponibile e limiti.

## Git e pull request

Usare Conventional Commits con un oggetto concreto. Per modifiche non banali aggiungere un corpo che
spieghi cosa, perché, vincoli e verifiche. Prima del commit:

```bash
git diff --check
git status --short
git diff --staged
```

Push, tag, release, upload e impostazioni remote richiedono autorizzazione esplicita. Il branch
`main` applica CI e revisione code owner ai contributori.

**Successivo:** [Release](releasing.md)
