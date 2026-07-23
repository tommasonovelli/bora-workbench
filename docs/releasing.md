# Release e pubblicazione

Questa pagina descrive il processo attuale. Pubblicare significa creare o modificare risorse remote:
serve sempre un'autorizzazione umana esplicita per push, tag, GitHub Release e PyPI.

## Stato pubblico

- versione pubblica corrente: `0.1.1`;
- tag remoti: `v0.1.0` e `v0.1.1`;
- GitHub Release `v0.1.1`: pubblicata con installer, wheel, sdist e `SHA256SUMS`;
- i digest `0.1.1` sono quelli del manifest allegato alla release e derivano dal build job verde;
- PyPI: non ancora pubblicata e fuori dall'autorizzazione di `0.1.1`;
- branch `main`: versione `0.1.1` con correzioni e `calibration/v4`.

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

Limiti e controlli non eseguiti devono essere espliciti. La pubblicazione `0.1.1` è stata autorizzata
per push, tag e GitHub Release, escludendo PyPI.

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
repository. Per `v0.1.1` la variabile resta assente e il job viene saltato.

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
build locale diversa da quella passata attraverso la matrice release. La `v0.1.1` è una release
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
