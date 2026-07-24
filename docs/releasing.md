# Release e pubblicazione

Questa pagina descrive il processo attuale. Pubblicare significa creare o modificare risorse remote:
serve sempre un'autorizzazione umana esplicita per push, tag, GitHub Release e PyPI.

## Stato pubblico

- versione pubblica corrente: `0.1.4`;
- tag remoti: `v0.1.0`, `v0.1.1`, `v0.1.2`, `v0.1.3` e `v0.1.4`;
- GitHub Release `v0.1.4`: pubblicata con installer, wheel, sdist e `SHA256SUMS`;
- i digest `0.1.4` sono quelli del manifest allegato alla release e derivano dal build job verde;
- PyPI: non ancora pubblicata ed esclusa dall'autorizzazione di `0.1.4`;
- release pubblica `v0.1.4`: `calibration/v6-lite` opt-in (`--protocol v6`, record v5) su override
  D-063; `calibration/v5` resta il default e la promozione di v6 a default richiede un GO umano.

Gli artefatti pubblicati sono immutabili. Non ricostruire, sostituire o ricaricare file con la stessa
versione per includere correzioni successive: serve una nuova versione.

Per installare la release vedere [Installazione](installation.md).

## Preparare una versione

Partire da un checkout pulito e dalla versione di uv richiesta:

```bash
git status --short
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
```

Prima della build eliminare `dist/`, quindi:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
```

Controllare:

- versione in `pyproject.toml` e metadata;
- changelog e documentazione senza riferimenti a uno stato precedente;
- installer coerenti con versione, uv e Python;
- wheel e sdist uniche in `dist/`;
- risorse, notice e documenti richiesti presenti;
- SHA-256 calcolati sui byte finali;
- nessun file generato o privato nel commit.

Ogni modifica successiva alla build invalida gli artefatti: rimuovere `dist/`, ripetere tutti i
controlli e ricostruire.

### Release 0.1.4

La `0.1.4` distribuisce `calibration/v6-lite` come protocollo opt-in (D-063/D-064): migrazione secca
`mode/v2`, quick-bench di produzione, motore `_calibration_v6_*`, record `calibration-record/v5`, CLI
`--protocol v6 --preference`, riuso/`doctor` per v5. `calibration/v5` resta il default; la promozione
di v6 a default resta condizionata a un verdetto umano GO dello spike cross-context. La logica è
testata offline con fake; l'adapter di trial reale è validato dal maintainer su Ubuntu e Windows. Il
maintainer ha autorizzato commit, push, tag e GitHub Release; PyPI resta escluso.

### Release 0.1.3

La `0.1.3` distribuisce D-058–D-061: precedenza corretta degli errori di cleanup, cause VRAM
separate, tassonomia additiva per spike/v6, MTP disabilitato prudentemente per `vstudio` e pacchetto
repository-only dello spike cross-context nello sdist. `calibration/v5` resta il default; non sono
presenti `mode/v2`, quick-bench di produzione, motore v6 o record v5.

Il 24 luglio 2026 il maintainer ha autorizzato commit, push, tag e GitHub Release prima delle run
locali dello spike, che restano post-release e non sono dichiarate Gate superato. La Fase 2 resta
bloccata fino a un verdetto umano `GO` committato. PyPI e l'attivazione dei candidati restano esclusi.

### Release 0.1.2

La `0.1.2` include `calibration/v5`, i parametri calibrati in `doctor`, la presentazione Rich
condivisa con valori dinamici letterali, la percentuale reale della compilazione Ubuntu CUDA, le
action Node 24 appuntate e la rimozione automatica dell'installazione `uv tool` corrente.

Il 23 luglio 2026 il maintainer ha deciso `RELEASE` e autorizzato commit, push, tag e GitHub Release,
rinunciando esplicitamente a ripetere prima un Gate manuale multipiattaforma. Questo non equivale a
un Gate superato: upgrade reale da `0.1.1`, calibrazione v5 e percorsi completi su macchine pulite
restano verifiche post-release. PyPI è escluso e i tre candidati locali restano inattivi.

## Release candidate e gate umano

Una release candidate viene preparata localmente senza tag o upload. Prima della finalizzazione il
maintainer prova almeno:

- installazione pulita su Ubuntu 22.04+ e Windows 11;
- `--version`, `validate`, `doctor` ed `engine status`;
- installazione o risoluzione del motore;
- `coding`, `studio`, `vstudio` e stop pulito;
- comportamento con e senza record locale;
- calibrazione e riuso quando il cambiamento li riguarda;
- uninstall confinato e preservazione della cache Hugging Face;
- upgrade dalla versione pubblica quando applicabile.

Per 0.1.1 il Gate Ubuntu v4 ha un run fallito e un retry valido. Il 23 luglio 2026 il maintainer ha
attestato anche il Gate reale Windows v4, incluso il riuso del record, e ha deciso `RELEASE` dopo i
test sui due sistemi. I dettagli privati del Gate Windows non vengono ricostruiti come misure o
aggiunti all'evidenza pubblica.

Limiti e controlli non eseguiti devono essere espliciti. La `0.1.3` è stata autorizzata per commit,
push, tag e GitHub Release prima dello spike reale; questo non equivale a un Gate e PyPI resta
escluso.

## Versione, tag e commit

Il tag deve essere `v<versione>` e la versione del pacchetto deve coincidere esattamente. Il commit di
finalizzazione contiene versione, changelog, documentazione e artefatti **non** committati, salvo
file espressamente versionati dal repository.

Il commit segue Conventional Commits e riporta nel corpo i controlli eseguiti. Prima di crearlo:

```bash
git diff --check
git status --short
git diff --staged
```

## Workflow GitHub

Un push di un tag `v*` attiva `.github/workflows/release.yml`:

1. matrice di test su Ubuntu e Windows;
2. verifica che tag e metadata coincidano;
3. build unica dopo i test;
4. verifica isolata della wheel e ispezione della sdist;
5. upload dell'artefatto testato fra job;
6. pubblicazione PyPI dello stesso artefatto solo quando la variabile repository
   `PYPI_PUBLISH_ENABLED` vale esattamente `true`.

Le action sono appuntate a SHA completo. I permessi globali sono `contents: read`; solo il job
`publish`, protetto dall'environment `pypi`, riceve `id-token: write`. Non esiste un token PyPI nel
repository. Per `v0.1.3` la variabile resta assente e il job viene saltato.

## Trusted Publishing PyPI

Il job `0.1.0` è fallito con `invalid-publisher` perché PyPI non ha ancora la configurazione
corrispondente. Il Trusted Publisher deve specificare:

```text
progetto:     qwen-launcher
owner/repo:   tommasonovelli/qwen-launcher
workflow:     release.yml
environment:  pypi
```

Dopo la configurazione va rieseguito soltanto il job di pubblicazione fallito del run
`29739366272`. Test e build di quel run sono già verdi e gli stessi artefatti sono nella GitHub
Release; non vanno ricostruiti. La variabile opt-in riguarda i workflow successivi e può essere
impostata solo con una distinta autorizzazione remota.

Finché PyPI non contiene realmente una versione, gli installer non devono usare
`--pypi-version` / `-PypiVersion` per quella versione.

## GitHub Release

La release allega gli stessi file prodotti dal job build:

- wheel;
- sdist;
- `install.sh`;
- `install.ps1`;
- `SHA256SUMS`.

Titolo, note e prerelease flag devono essere coerenti con changelog e metadata. Non caricare una
build locale diversa da quella passata attraverso la matrice release. La `v0.1.3` è una release
GitHub stabile e non una prerelease.

## Verifica dopo la pubblicazione

Su Ubuntu e Windows puliti:

1. confrontare i digest di GitHub e, quando disponibile, PyPI;
2. installare la sorgente pubblicata;
3. verificare versione, validazione, doctor e motore;
4. eseguire almeno un modo e uno stop pulito;
5. provare uninstall e rimozione uv;
6. confermare che cache Hugging Face, processi e porte estranei siano intatti.

Un problema post-release viene corretto nel branch, registrato sotto `Unreleased` e distribuito con
una nuova versione. Non si altera la release precedente.

**Fine del percorso:** [torna all'indice della documentazione](README.md).
