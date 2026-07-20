# Release 0.1

Questa guida registra il processo usato per `0.1.0` e separa finalizzazione locale, pubblicazione e
verifica. Tag, GitHub Release e upload PyPI richiedono sempre un'autorizzazione umana esplicita.

## Installare la release pubblicata

Installer, wheel, sdist e `SHA256SUMS` sono allegati alla
[GitHub Release v0.1.0](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.0).
Gli installer fissano uv `0.11.28` e CPython `3.12.13`; la wheel CI ha SHA-256:

```text
8966539a9e257f532d14fab821bf507a9c0327fa7fb246e5d8803fa69289c482
```

Dopo avere scaricato installer e wheel:

```bash
sh ./install.sh --wheel ./qwen_launcher-0.1.0-py3-none-any.whl \
  --sha256 8966539a9e257f532d14fab821bf507a9c0327fa7fb246e5d8803fa69289c482
```

```powershell
.\install.ps1 -Wheel .\qwen_launcher-0.1.0-py3-none-any.whl `
  -Sha256 8966539a9e257f532d14fab821bf507a9c0327fa7fb246e5d8803fa69289c482
```

Il sorgente resta installabile anche dal commit finale esatto
`ce5c1e9d84d81197323aa98848a12cce409647e6` tramite `--git-commit` / `-GitCommit`.

## Verifiche della finalizzazione

La release viene costruita soltanto da un checkout pulito:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
# dist/ deve essere assente prima della build
uv build
uv run --frozen python scripts/verify_wheel.py
```

La versione nei metadati deve essere `0.1.0`; il tag deve essere `v0.1.0`. Wheel e sdist vengono
rigenerate dopo ogni modifica e i relativi SHA-256 sono calcolati sui byte finali.

## Decisione umana 0.1

Il 20 luglio 2026 Tommaso ha dichiarato il progetto funzionante, ha deciso esplicitamente `RELEASE` e
ha autorizzato finalizzazione, push, tag e pubblicazione. Questa decisione accetta le limitazioni già
documentate: copertura di calibrazione `GATE-PARTIAL`, assenza di una prova su hardware
materialmente diverso, blocco CUDA multi-GPU e pesi non redistribuiti.

`0.1.0` è una prima release pubblica per valutazione ed early adopter: non garantisce stabilità di
CLI, configurazione, record, procedure operative, prestazioni o compatibilità futura. Test e lock
circoscrivono l'evidenza verificata ma non trasformano questa release iniziale in un servizio o in
un'interfaccia stabile.

I candidati di calibrazione locali restano separati dalla release e non vengono attivati o
pubblicati implicitamente.

## Workflow di pubblicazione

Il tag `v<versione>` attiva `.github/workflows/release.yml`, che:

1. ripete test e validazione su Ubuntu e Windows;
2. verifica che il tag coincida con la versione del pacchetto;
3. costruisce wheel e sdist una sola volta;
4. verifica la wheel in un ambiente isolato;
5. trasferisce gli stessi artefatti testati al job di pubblicazione;
6. pubblica su PyPI tramite Trusted Publishing OIDC e ambiente GitHub `pypi`.

Il workflow usa permessi globali `contents: read`. Soltanto il job `publish` riceve
`id-token: write`; nessun token PyPI è conservato nel repository o passato al workflow.

### Stato della pubblicazione 0.1.0

Il run release [`29739366272`](https://github.com/tommasonovelli/qwen-launcher/actions/runs/29739366272)
ha completato con successo la matrice Ubuntu/Windows, build e verifica isolata. La GitHub Release usa
gli stessi artefatti CI. Il solo job PyPI è bloccato da `invalid-publisher`: su PyPI non esiste ancora
un Trusted Publisher corrispondente.

Per completare PyPI, Tommaso deve configurare sul proprio account:

- progetto: `qwen-launcher`;
- owner/repository: `tommasonovelli/qwen-launcher`;
- workflow: `release.yml`;
- environment: `pypi`.

Dopo la configurazione si riesegue soltanto il job fallito. Fino a quel momento
`--pypi-version 0.1.0` non va usato; l'installazione supportata passa dagli artefatti GitHub o dal
commit completo.

## Verifica post-pubblicazione

Su Ubuntu 22.04 pulito e Windows 11/Sandbox:

- confrontare gli SHA-256 degli artefatti GitHub e, quando disponibile, PyPI;
- installare la wheel GitHub verificata e poi `qwen-launcher==0.1.0` da PyPI;
- verificare `--version`, `validate`, `doctor` ed `engine status`;
- eseguire almeno i modi principali e uno stop pulito;
- verificare `uninstall` e `uv tool uninstall qwen-launcher`;
- confermare che cache Hugging Face, processi e porte estranei restino intatti.

Una versione pubblicata non viene mai sostituita in place. Correzioni successive richiedono una nuova
versione, un nuovo changelog e lo stesso processo di test, autorizzazione e pubblicazione.
