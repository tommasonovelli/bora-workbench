# Contribuire evidenza `calibration/v3`

La contribuzione distribuisce evidenza e suggerimenti d'ordine per una **nuova ricerca locale
completa**. Non distribuisce la busta misurata come configurazione finale di altri PC.

Il flusso è manuale: il launcher non esegue login, upload, commit, branch remoto, issue o pull
request. Non usare mai `--activate` per preparare un contributo.

## 1. Eseguire il Gate locale

Con modello e motore appuntati già disponibili, chiudere workload concorrenti e usare:

```console
qwen-launcher calibrate --mode all --no-activate
```

Un report può includere soltanto i modi realmente completati. Un candidato, un record parziale o un
run invalidato non diventa evidenza accettata completando a mano i campi mancanti. I record
`calibration-record/v2` e i log sotto la directory dati restano privati e non vengono copiati nel
repository.

## 2. Naming

Usare identificatori ASCII minuscoli con trattini:

```text
<os>-<hardware-principale>-v3
```

Esempio: `windows-11-rtx-2060-super-v3`.

Percorsi del contributo:

```text
src/qwen_launcher/resources/content/calibrations/<id>.json
docs/calibrations/<id>/README.md
docs/calibrations/<id>/SHA256SUMS
```

Il campo `id` deve coincidere col nome JSON. La policy
`src/qwen_launcher/resources/content/calibration-policy.json` deve riferire il report come
`calibrations/<id>.json` e appuntare lo SHA-256 dei suoi byte UTF-8 esatti.

## 3. Preparare il report

Usare esclusivamente `calibration-report/v2`. Copiare dai risultati revisionati soltanto:

- identità appuntate di modello, artefatto e motore;
- OS, backend, RAM totale, GPU, VRAM e driver;
- dominio derivato dai metadati GGUF e costanti realmente usate;
- probe, finalisti, regola e risorse osservate per i modi completati;
- riferimenti repository-relative e relativi SHA-256.

`observed_local_envelope` documenta il PC d'origine. `seed_n_cpu_moe` deve coincidere col finalista
locale selezionato, ma il runtime può usarlo soltanto per anticipare un probe dentro la staffa. Non
aggiungere un
`profile/v1`: contesto, tok/s, hardware e busta osservata non entrano nel `LaunchPlan` remoto.

Non includere:

- hostname, username, seriali, UUID o indirizzi;
- percorsi assoluti Windows, POSIX o UNC;
- directory dati/config/cache/stato;
- log grezzi, record candidato/attivo/previous o configurazione locale;
- token, credenziali o dati dei prompt dell'utente;
- promesse di tok/s o validazione su componenti non provati.

La copertura resta `gate-partial` e
`constants_validated_on_materially_different_hardware=false` finché esiste soltanto il caso Windows
11/CUDA su RTX 2060 SUPER 8 GiB e 31,92 GiB RAM. Il follow-up eterogeneo è aperto ma non bloccante.

## 4. Checksum e validazione

Calcolare i digest dopo l'ultima modifica. Dalla radice del repository:

```console
sha256sum src/qwen_launcher/resources/content/calibrations/<id>.json
sha256sum -c docs/calibrations/<id>/SHA256SUMS
uv sync --frozen
uv run --frozen qwen-launcher validate
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv build
uv run --frozen python scripts/verify_wheel.py
```

Una modifica di un byte al report richiede di aggiornare sia il riferimento nella policy sia il
manifest. La validazione deve fallire per report mancante, digest divergente, modello/motore non
compatibile, seed fuori dominio, riserva violata, percorso privato o scope hardware incoerente.

## 5. Checklist della pull request

- [ ] La PR contiene contenuto/evidenza e documentazione, non modifiche Python core o nuovi schemi.
- [ ] Il run usa `calibration/v3`, `benchmark/v1`, modello e motore appuntati.
- [ ] Il report contiene solo modi completati e nessun dato ricostruito o inventato.
- [ ] `privacy_reviewed` è vero dopo una revisione umana dei byte esatti.
- [ ] Nessun hostname, username, percorso privato, record locale o log grezzo è incluso.
- [ ] La policy lega report, scope misurato e SHA-256 esatto.
- [ ] Nessun `profile/v1` o nearest-match trasferisce la busta locale.
- [ ] Rimuovere o ignorare il seed lascia invariati dominio, contesti, riserve e risultato misurato.
- [ ] Le incompatibilità di modello, motore o backend ignorano il seed; hardware e driver diversi
      richiedono comunque una nuova misura locale.
- [ ] `GATE-PARTIAL` e il follow-up hardware eterogeneo restano visibili quando applicabili.
- [ ] Manifest, `validate`, Ruff, pytest, build e verifica wheel sono verdi.
- [ ] Nessun upload, login, branch remoto, issue o PR è stato creato automaticamente.

## 6. Testo PR

Copiare e completare questo testo senza inserire dati privati:

```markdown
## Tipo

- [x] Contenuto dichiarativo di calibrazione
- [ ] Core

## Evidenza

- Report: `<id>`
- Protocollo: `calibration/v3`
- Modello/motore: `<identità appuntate>`
- Scope realmente misurato: `<OS/backend/componenti/capacità>`
- Modi completati: `<elenco>`
- Esito locale: `<CALIBRATION-ACCEPTED o CALIBRATION-REJECTED>`
- Copertura complessiva: `<GATE-PARTIAL o stato successivo autorizzato>`

## Portabilità

Il report è evidenza locale. Il seed modifica soltanto l'ordine della stessa ricerca completa e non
è una busta finale, un nearest-match o una promessa prestazionale. Hardware non misurato localmente
usa la baseline oppure esegue `calibrate`.

## Privacy e integrità

- [ ] Revisione privacy completata
- [ ] Report e riferimenti privi di hostname, username e percorsi privati
- [ ] SHA-256 e manifest verificati

## Verifiche

- [ ] `qwen-launcher validate`
- [ ] Ruff check e format
- [ ] pytest
- [ ] build
- [ ] verifica wheel isolata
```

Il maintainer revisiona personalmente evidenza, privacy e claim di portabilità prima del merge.
