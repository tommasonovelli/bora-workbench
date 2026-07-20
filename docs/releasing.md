# Release 0.1

Questa guida registra il processo usato per `0.1.0` e separa finalizzazione locale, pubblicazione e
verifica. Tag, GitHub Release e upload PyPI richiedono sempre un'autorizzazione umana esplicita.

## Installare la release pubblicata

Gli installer richiedono una sorgente esplicita e fissano uv `0.11.28` e CPython `3.12.13`:

```bash
sh ./install.sh --pypi-version 0.1.0
```

```powershell
.\install.ps1 -PypiVersion 0.1.0
```

Sono supportati anche due percorsi verificabili alternativi:

```bash
sh ./install.sh --git-commit <commit-completo-40-hex>
sh ./install.sh --wheel <wheel-locale> --sha256 <64-hex-verificato>
```

```powershell
.\install.ps1 -GitCommit <commit-completo-40-hex>
.\install.ps1 -Wheel <wheel-locale> -Sha256 <64-hex-verificato>
```

Wheel, sdist e `SHA256SUMS` sono allegati alla
[GitHub Release v0.1.0](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.0).
Il digest deve essere verificato prima di consegnare una wheel all'installer.

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

## Verifica post-pubblicazione

Su Ubuntu 22.04 pulito e Windows 11/Sandbox:

- confrontare gli SHA-256 degli artefatti GitHub e PyPI;
- installare `qwen-launcher==0.1.0` con gli installer;
- verificare `--version`, `validate`, `doctor` ed `engine status`;
- eseguire almeno i modi principali e uno stop pulito;
- verificare `uninstall` e `uv tool uninstall qwen-launcher`;
- confermare che cache Hugging Face, processi e porte estranei restino intatti.

Una versione pubblicata non viene mai sostituita in place. Correzioni successive richiedono una nuova
versione, un nuovo changelog e lo stesso processo di test, autorizzazione e pubblicazione.
