# qwen-launcher — Specifica di implementazione e roadmap

Questo è l'unico piano normativo del repository. Descrive i vincoli che il lavoro futuro deve
preservare e le attività non ancora implementate. Il comportamento disponibile oggi è documentato
in [`docs/`](docs/README.md); la provenienza misurata di lock e report è conservata in
[`evidence/`](evidence/README.md).

## 0. Stato reale e tracker

Aggiornato al 22 luglio 2026.

### Baseline completata

- [x] La milestone 0.1 è implementata: package Python, configurazione, risorse, hardware, motore,
  lifecycle, tre modi, calibrazione locale v3, validazione, installer, uninstall, CI e release.
- [x] Versione `0.1.0`, tag `v0.1.0` e GitHub Release sono pubblici.
- [x] Il run release `29739366272` è verde per test Ubuntu/Windows, build e verifica wheel.
- [x] `llama.cpp b10011`, modello, mmproj, asset, flag, API e salute sono appuntati e verificati.
- [x] Cache K/V Q8 con mmap è attiva solo su CUDA; i pesi restano `UD-Q4_K_M`.
- [x] `calibration/v3` e `calibration-record/v2` hanno prodotto il Gate locale Windows CUDA
  accettato per `coding`, `studio` e `vstudio`; i tre candidati originari restano inattivi.
- [x] Policy e report pubblici v2 conservano metodo/evidenza v3 e forniscono a v4 soltanto seed
  d'ordine, mai la busta di un altro host.
- [x] Le correzioni post-release D-051 e D-052 sono nel branch: porta temporanea per i trial e
  tolleranza massima di 1 MiB nel confronto del totale RAM.

### Lavoro aperto

- [ ] Configurare il Trusted Publisher PyPI e rieseguire solo il job `publish` fallito di
  `29739366272`; non ricostruire gli artefatti `0.1.0`.
- [ ] Completare il Gate Windows reale per `calibration/v4`; `0.1.1rc1` non diventa 0.1.1 prima.
- [ ] Distribuire D-051/D-052 e D-053 soltanto tramite la 0.1.1 dopo il Gate e decisione `RELEASE`.
- [ ] Stabilizzare ulteriormente la serie 0.1 prima di iniziare la 0.2.
- [~] Ripetere `calibration/v4 --no-activate` su Windows e hardware materialmente diverso. Windows
  è bloccante per 0.1.1; l'hardware diverso resta follow-up e la copertura è `GATE-PARTIAL`.
- [ ] Step 7 — skill e router deterministico.
- [ ] Step 8 — Open WebUI gestita e sync.
- [ ] Step 9 — benchmark autonomo e doctor definitivo.
- [ ] Step 10A / Human Gate / 10B — release 0.2.

Nessun candidato locale viene attivato e nessuno Step 7 viene iniziato senza richiesta esplicita.
Push, tag, release, upload e impostazioni remote richiedono sempre autorizzazione nella sessione
corrente.

---

## 1. Prodotto e perimetro

### 1.1 Prodotto corrente

`qwen-launcher` è una distribuzione locale specializzata attorno a
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`. Rileva l'hardware, verifica modello e motore, costruisce
un piano, governa `llama-server`, espone tre modi e misura localmente una busta per ogni macchina.

Non è un gestore generico di modelli, un framework di plugin o un orchestratore multi-backend.

### 1.2 Piattaforme

- Ubuntu 22.04+ x86-64;
- Windows 11 x86-64;
- CPU oppure una singola GPU NVIDIA CUDA;
- servizi esclusivamente su `127.0.0.1`.

Fuori perimetro: macOS, ARM, Vulkan, ROCm, multi-GPU distribuita, auto-update, GUI nativa, plugin
Python, cancellazione della cache Hugging Face e modi utente arbitrari.

### 1.3 Confine della 0.2

La 0.2 aggiunge soltanto quanto autorizzato dagli Step 7–9: skill dichiarative, router a frasi, Open
WebUI appuntata, sync locale, benchmark autonomo e doctor completato. Non trasforma il progetto in un
framework estensibile di codice.

---

## 2. Gerarchia delle fonti di verità

In caso di conflitto prevale la prima fonte applicabile:

1. lock versionati, policy/report accettati e artefatti strutturati;
2. output reali della versione appuntata conservati in `evidence/`;
3. schemi e test;
4. questo documento;
5. documentazione ufficiale della versione esatta appuntata;
6. documentazione ufficiale corrente per strumenti non ancora appuntati;
7. assunzioni.

Conseguenze:

- vietato `latest` nei file committati;
- una versione appuntata non cambia senza istruzione esplicita;
- il ramo corrente di un progetto upstream non corregge il contratto di una release fissata;
- una contraddizione viene riportata e ferma solo il lavoro interessato;
- flag, checksum, commit, benchmark, endpoint e claim hardware non vengono inventati;
- i file grezzi coperti da manifest restano byte-identici.

---

## 3. Decisioni normative attive

Gli identificatori restano stabili perché codice, test ed evidenza li citano.

| ID | Decisione |
|---|---|
| D-001 | Package Python `>=3.12,<3.13`; sviluppo e CI con CPython `3.12.13`. |
| D-002 | uv `0.11.28`, `uv_build`, `uv.lock` committato e comandi frozen. |
| D-003 | Runtime: `typer`, `rich`, `psutil`, `httpx`, `jsonschema`; sviluppo: `pytest`, `ruff`. |
| D-004 | `pyyaml` può entrare solo nello Step 7 per frontmatter letto con `safe_load`. |
| D-006 | Modi = comportamento; record locali = prestazioni; report/profili condivisi = seed o evidenza. |
| D-008 | Una sola GPU; `CUDA_VISIBLE_DEVICES` esclusivamente nell'ambiente figlio. |
| D-010 | `coding` senza UI; `studio` con UI; `vstudio` con UI e vision, sempre espliciti. |
| D-011 | Il router 0.2 usa frasi normalizzate, mai regex. |
| D-015 | Ogni servizio gestito ascolta solo su `127.0.0.1`. |
| D-017 | `engine.lock` contiene semantica macchina, non soltanto una lista di flag. |
| D-018 | Installazioni immutabili; attivazione atomica tramite `current.json`. |
| D-020 | Anche la release 0.2 usa preparazione locale, gate umano e finalizzazione separata. |
| D-022 | Open WebUI userà ambienti versionati e manifest di attivazione atomico. |
| D-024 | Le prove di fattibilità non sono profili calibrati né promesse prestazionali. |
| D-030 | Identità `model` separata dal `model_path`; default risolto in sola lettura alla revisione fissata. |
| D-033 | Pesi `UD-Q4_K_M`; cache K/V Q8 con mmap solo sul ramo CUDA verificato. |
| D-034 | Una busta ottima è locale; capacità nominali uguali non autorizzano trasferimento o nearest-match. |
| D-035 | Solo un record locale compatibile può pilotare un `LaunchPlan` calibrato. |
| D-039 | Dominio `[0, 41]`, riserve, scala, round e tetto probe hanno provenienza dichiarata; portabilità empirica parziale. |
| D-041 | Conferma v3 in due round `A→B/B→A`, benchmark completo e dominanza per unanimità. |
| D-042 | Ogni trial lascia almeno 2,0 GiB RAM; il riuso richiede fabbisogno misurato più la riserva. |
| D-043 | Lifecycle record candidato → attivo → singolo previous; default attiva, `--no-activate` separa il Gate. |
| D-044 | Telemetria GPU best-effort ed evidence-only, mai soglia decisionale. |
| D-045 | Monotonia solo fra probe fattibili; interpolazione solo per ordinare un punto interno. |
| D-046 | Su WDDM la popolazione di identità eseguibili è immutabile per run e non serializza percorsi. |
| D-047 | Il Gate locale è sufficiente per il metodo; copertura `GATE-PARTIAL` finché manca hardware diverso. |
| D-048 | Policy/report pubblici v2; il loader proietta soltanto `n_cpu_moe` come ordine di probe. |
| D-049 | Gate modello predefinito: 28 GiB RAM totali e 22 GiB disponibili. |
| D-050 | `98304` è target esperto esplicito, fuori dalla scala automatica. |
| D-051 | I trial usano `llama_port` se libera, altrimenti una porta loopback assegnata dall'OS. |
| D-052 | Il confronto del totale RAM tollera al massimo 1 MiB; headroom e componenti restano severi. |
| D-053 | `calibration/v4` conserva scala, ricerca e ABBA v3 ma usa 0,3 GiB di riserva VRAM e produce `calibration-record/v3`; i record v2 restano validi con la propria riserva 0,5 GiB. |

Una nuova decisione durevole aggiorna questa tabella nello stesso step che la autorizza.

---

## 4. Architettura

### 4.1 Responsabilità dei moduli

| Modulo | Responsabilità |
|---|---|
| `cli.py` / `_cli_*` | input, presentazione ed exit code; nessuna logica piattaforma |
| `paths.py` | directory per OS; nessuna creazione |
| `config.py` | TOML, ambiente, precedenza e validazione |
| `hardware.py` | CPU, RAM, NVIDIA e selezione GPU |
| `profiles.py` | modi, seed, gate e `LaunchPlan` |
| `benchmark.py` | protocollo `benchmark/v1` riusabile |
| `calibration.py` / `_calibration_*` | ricerca locale, record, bundle ed evidenza |
| `engine.py` / `_engine_*` | lock, modello, asset, comando, installazione e attivazione |
| `process.py` / `_process_*` | processo, salute, stato, lock, status e stop |
| `validation.py` / `_validation_*` | schemi e controlli semantici |
| `resources/__init__.py` | accesso `importlib.resources` |
| `routing.py` (futuro) | normalizzazione e scoring puro delle skill |
| `webui.py` (futuro) | lock, ambiente, installazione e processo Open WebUI |

Solo `paths.py`, `process.py`, `hardware.py` ed `engine.py` possono diramarsi sul sistema operativo.

### 4.2 Territori del repository

- `src/qwen_launcher/resources/schemas/`: contratti versionati;
- `src/qwen_launcher/resources/content/`: contenuto contribuito;
- `src/qwen_launcher/resources/*.lock`: compatibilità esterna appuntata;
- restante `src/qwen_launcher/`: core mantenuto dal proprietario;
- `docs/`: comportamento corrente per utenti e contributori;
- `evidence/`: output misurati e manifest, non manuali;
- `IMPLEMENTATION_SPEC.md`: roadmap e vincoli normativi;
- `tests/`: prova comportamentale offline.

Una PR modifica core oppure contenuto dichiarativo, mai entrambi.

### 4.3 Risorse e import

Le risorse della wheel sono `Traversable`. Usare `read_text()`/`read_bytes()`; `as_file()` soltanto
nel suo context manager. Non presumere un `Path` fisico.

Importare `qwen_launcher` non usa rete, non crea directory, non scrive file e non avvia processi.

---

## 5. Contratti trasversali correnti

La spiegazione operativa completa è in `docs/`; questa sezione conserva gli invarianti che il lavoro
futuro non deve rompere.

### 5.1 Stack, packaging e dipendenze

- Python package `>=3.12,<3.13`; sviluppo/CI `3.12.13`.
- uv `0.11.28`; backend `uv_build>=0.11.28,<0.12`.
- Layout `src/`; dipendenze sviluppo in `[dependency-groups]`.
- `uv.lock` committato; CI con `uv sync --frozen` e `uv run --frozen`.
- Wheel con tutte le risorse; sdist con installer, documentazione, piano ed evidenza.
- Action GitHub di terzi appuntate a SHA completo.

### 5.2 Configurazione e percorsi

Precedenza: ambiente > TOML > default. Il TOML intero viene validato prima degli override. Chiavi
sconosciute e valori malformati sono errori; il launcher non modifica il file.

| Chiave | Ambiente | Default |
|---|---|---|
| `model` | `QWEN_LAUNCHER_MODEL` | modello appuntato |
| `model_path` | `QWEN_LAUNCHER_MODEL_PATH` | `None` |
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` | `8080` |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` | `None` |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` | `true` |

Porte 1–65535. Booleani ambiente: `true/false`, `1/0`, `yes/no`, `on/off`. Solo le due variabili
percorso possono essere vuote per significare `None`.

| Radice | Linux | Windows |
|---|---|---|
| config | `${XDG_CONFIG_HOME:-~/.config}/qwen-launcher` | `%APPDATA%\qwen-launcher` |
| data | `${XDG_DATA_HOME:-~/.local/share}/qwen-launcher` | `%LOCALAPPDATA%\qwen-launcher\data` |
| cache | `${XDG_CACHE_HOME:-~/.cache}/qwen-launcher` | `%LOCALAPPDATA%\qwen-launcher\cache` |
| state | `${XDG_STATE_HOME:-~/.local/state}/qwen-launcher` | `%LOCALAPPDATA%\qwen-launcher\state` |

Variabili base assenti, vuote o relative usano il fallback. I path helper non creano directory.

### 5.3 Contratti dichiarativi

Tutti i documenti usano JSON Schema 2020-12, `additionalProperties: false` e identificatori
`^[a-z0-9-]+$`.

Contratti supportati: `mode/v1`, `profile/v1`, `calibration-policy/v1` e `/v2`,
`calibration-report/v1` e `/v2`, `calibration-record/v2` e `/v3`, `engine-lock/v1`.

- Un modo contiene descrizione, `services.ui`, `services.vision` e sampling.
- Un profilo v1 è solo compatibilità/evidenza; nessun profilo di produzione è distribuito.
- Policy v2 descrive il metodo storico v3, non buste; v4 la usa soltanto come seed d'ordine.
- Report v2 è privacy-safe e produce soltanto seed d'ordine.
- Record v2/v3 sono privati, per modo e legati a identità completa; v3 registra il metodo v4.
- Filename, riferimenti e SHA-256 sono controllati semanticamente.

Un nuovo campo incompatibile richiede una nuova versione di schema.

### 5.4 Hardware e unità

GiB = byte / `1024³`; MiB NVIDIA / `1024`. Nomi di memoria terminano in `_gib`.

`nvidia-smi` viene eseguito senza shell con timeout 5 secondi. Assenza, errore o output malformato
produce backend CPU con warning. Se esistono più GPU, la selezione è maggiore VRAM totale e poi
indice minore, ma l'avvio CUDA resta bloccato.

Il processo figlio CUDA riceve `CUDA_VISIBLE_DEVICES`; il processo padre non viene modificato.

### 5.5 Piano, record e baseline

Solo un attivo `calibration-record/v2` o `/v3` può fornire la busta. Devono coincidere
modello/digest, motore/commit/contratto, modo, OS, backend, hardware, driver e headroom. Il totale
RAM tollera al massimo 1 MiB di deriva; RAM disponibile e VRAM libera restano confronti separati.

Riuso:

- RAM disponibile ≥ fabbisogno misurato + 2,0 GiB;
- CUDA: VRAM libera ≥ fabbisogno misurato + riserva registrata (0,5 GiB per v2, 0,3 GiB per v3).

Fallback: `ctx=8192`; CUDA `n_cpu_moe=48`; CPU senza `n_cpu_moe`. È sempre non ottimizzato.
`--force` bypassa solo il gate 28/22 GiB del modello predefinito.

### 5.6 Calibrazione

Il default è `calibration/v4`. È locale, esplicito, confermato dall'utente e non effettua upload,
commit o modifica config. Conserva scala, ricerca del confine, finalisti e conferma ABBA di v3;
D-053 cambia soltanto riserva VRAM e versione del record. L'esecuzione v3 è ritirata, mentre i suoi
record e la sua evidenza pubblica restano leggibili.

Costanti:

- scala automatica `131072 → 65536 → 32768 → 16384 → 8192`;
- target esperti aggiuntivi ammessi: `98304`;
- dominio CUDA `[0, block_count]`, atteso `[0, 41]` sul modello corrente;
- polling RAM/VRAM 250 ms;
- riserva RAM 2,0 GiB;
- riserva VRAM 0,3 GiB;
- tolleranza rilascio/deriva 0,125 GiB;
- massimo 12 probe per modo;
- due round `A→B/B→A`;
- `benchmark/v1` completo su ogni avvio di conferma.

La dominanza richiede lo stesso vincitore in entrambi i round. Altrimenti margine e prudenza. Su CPU
si conferma la baseline; nessun asse CPU viene inventato.

Ogni trial usa la porta configurata se libera, altrimenti una porta temporanea loopback. Gli avvii
normali continuano a rifiutare la porta occupata.

Record: `<modo>.candidate.json`, attivo `<modo>.json`, rollback `<modo>.previous.json`. Default:
promozione atomica; `--no-activate` conserva il candidato; `--activate` promuove senza nuove prove.

`calibration/v1` resta laboratorio esplicito e produce solo bundle bozza. Record v1 sono superati e
inerti.

### 5.7 Comando motore

Il builder espande soltanto `command_contract` di `engine.lock`. Ogni token opzione deve appartenere
a `verified_flags`; placeholder sconosciuti sono invalidi.

Il comando rappresenta esplicitamente modello fisico, contesto, sampling, host/porta, metriche,
MTP/cache/mmap, UI, vision e backend. CPU non riceve argomenti CUDA. Nessun flag nasce da hardcode
semantico non presente nel lock.

### 5.8 Motore e modello

Ordine motore: `engine_path`, `PATH`, manifest gestito. Ogni candidato supera versione e help esatti.

Il modello predefinito è risolto in sola lettura alla revisione del lock secondo la precedenza cache
osservata. Filename, dimensione e SHA-256 devono coincidere. Un modello diverso richiede
`model_path` e non eredita dati del default. Non usare `--hf-repo`.

Gli asset sono selezionati per OS/backend, scaricati via HTTPS, verificati e attivati soltanto dopo
probe completi. Ubuntu CUDA usa il sorgente appuntato finché il lock non verifica un prebuilt.

### 5.9 Processi, stato, salute e log

- stato `state_dir()/services.json`, versione 1;
- identità processo `pid + create_time`;
- scritture atomiche con temporaneo nella stessa directory, flush e `replace`;
- stato corrotto rinominato `services.corrupt-<timestamp>.json`;
- lock di avvio esclusivo con proprietario `pid + create_time`;
- un solo servizio gestito;
- porta controllata su `127.0.0.1`;
- `Popen` senza shell e nuovo process group Windows;
- stdout/stderr nello stesso log UTF-8 timestampato;
- health request 2 s, polling 1 s, timeout totale 15 minuti;
- READY = status e JSON esatti del lock;
- stop: terminate 10 s, poi kill 5 s;
- `Ctrl-C` pulisce e termina 130.

`status` e `stop` senza servizi terminano 0.

### 5.10 Installazione e disinstallazione sicure

Vietati `sudo`, elevazione, package manager automatici e `shell=True`. Download in `.part`, checksum
prima dell'estrazione, staging confinato, installazioni immutabili e manifest atomico.

L'estrazione rifiuta path assoluti, drive, `..`, file speciali e link in fuga. Cancellazioni limitate
a data/cache gestiti dopo verifica.

`uninstall` mostra config/data/cache/state, richiede conferma, rifiuta servizi vivi e symlink, non
tocca mai la cache Hugging Face e non rimuove il tool uv.

### 5.11 Errori ed exit code

| Caso | Codice |
|---|---:|
| successo, stato vuoto, soli warning | 0 |
| errore operativo o validazione fallita | 1 |
| input CLI o configurazione invalida | 2 |
| `Ctrl-C` | 130 |

Errori attesi su stderr, azionabili e senza traceback. Eccezioni operative non vengono ignorate.

### 5.12 Divieti globali

- niente `shell=True`, `eval`, `exec`, elevazione o bind `0.0.0.0`;
- niente rete nei test o all'import;
- niente side effect all'import;
- niente schema incompatibile senza nuova versione;
- niente fallback non documentato;
- niente modifiche alla config utente o cache Hugging Face;
- niente cancellazioni fuori dalle radici gestite;
- niente TLS/checksum disabilitati;
- niente feature future anticipate;
- niente plugin, async o astrazioni speculative;
- niente operazioni remote senza autorizzazione esplicita.

---

## 6. Protocollo di lavoro

### 6.1 Prima delle modifiche

1. Leggere interamente questo documento e `AGENTS.md`.
2. Leggere documentazione corrente, lock, schemi, test ed evidenza pertinenti.
3. Eseguire `git status` e preservare modifiche preesistenti.
4. Eseguire `uv sync --frozen`, Ruff e pytest come baseline.
5. Se il punto di partenza non è verde, rendere visibile il problema.
6. Delimitare un solo step e una sola area: core oppure contenuto.

### 6.2 Durante

- implementare solo il perimetro autorizzato;
- aggiornare documentazione corrente, non creare nuovi piani laterali;
- registrare qui nuove decisioni durevoli;
- usare fake offline nei test;
- fermarsi su contraddizioni non risolvibili dalla gerarchia delle fonti.

### 6.3 Prima della conclusione

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
```

Se cambiano packaging o risorse:

```bash
rm -rf dist
uv build
uv run --frozen python scripts/verify_wheel.py
```

Poi `git diff --check`, ispezione del diff/staging e resoconto con file, comportamento, test, limiti e
verifiche manuali residue. Il commit locale è autorizzato solo quando richiesto; push e pubblicazione
non lo sono.

---

## 7. Stabilizzazione 0.1 aperta

### 7.1 Completare PyPI per `0.1.0`

Il maintainer configura su PyPI il Trusted Publisher:

```text
project:      qwen-launcher
owner/repo:   tommasonovelli/qwen-launcher
workflow:     release.yml
environment:  pypi
```

Poi riesegue soltanto il job `publish` fallito del run `29739366272`. Dopo il successo verifica
`qwen-launcher==0.1.0` su Ubuntu e Windows e confronta i digest con GitHub. Gli artefatti esistenti
non vengono ricostruiti.

### 7.2 Preparare la 0.1.1

La 0.1.1 distribuirà D-051, D-052, UX di progresso e D-053. Il Gate Ubuntu v4 comprende un primo run
fallito e un retry valido; questo non sostituisce il Gate Windows reale richiesto da
`docs/releasing.md`. Metadata e codice possono essere preparati localmente, ma commit finale, tag e
release restano bloccati fino a prova Windows e decisione umana `RELEASE`.

### 7.3 Evidenza eterogenea

Quando disponibile, ripetere v3 con `--no-activate` su hardware materialmente diverso, revisionare
privacy e aggiornare report/policy in una PR dichiarativa. L'esito non viene ricostruito a mano e non
trasforma retroattivamente l'unico host corrente in prova universale.

---

## 8. Milestone 0.2 — lavoro futuro

La 0.2 parte soltanto dopo stabilizzazione 0.1 e richiesta esplicita. Ogni step è separato.

### Step 7 — Skill e router deterministico

**Obiettivo:** contenuti instradabili senza regex o codice contribuito.

Contratto `skill/v1`: Markdown con frontmatter YAML letto con `yaml.safe_load`; nome uguale al file;
descrizione; `routing.phrases` come coppie `[frase, peso]`; almeno tre esempi positivi; almeno un
esempio negativo; `co_activate` anche vuoto; body Markdown come contenuto.

Normalizzazione:

1. tronca input a 20.000 caratteri;
2. Unicode NFKD;
3. rimuove combining characters;
4. `casefold()`;
5. sostituisce sequenze non alfanumeriche con spazio;
6. comprime spazi e trim.

Una frase normalizzata è una sequenza contigua di token e contribuisce al massimo una volta.

Routing:

- somma pesi;
- applica threshold;
- ordina score decrescente, poi nome alfabetico;
- `top_k` limita selezioni dirette;
- co-attivazioni valide si aggiungono dopo, senza duplicati o ricorsione, e possono superare `top_k`;
- un esempio positivo deve classificare la propria skill al primo posto;
- un negativo non deve selezionarla.

Attività:

1. versione `0.2.0.dev0`;
2. aggiungere `pyyaml` e aggiornare lock;
3. schema, parser sicuro e skill iniziali `epsilon-delta`, `math-solver`, `debug-systematic`,
   `linux-ops`;
4. router puro e test integrati in `validate`;
5. `mode/v2` con `prompt` e `skills` (`auto` o lista), mantenendo lettura v1;
6. migrazione dichiarativa dei modi in PR separata dal core quando necessario;
7. nessuna regex in schema, parser o documentazione.

Test: normalizzazione, accenti, case, punteggiatura, frase una volta, pareggi, threshold, top_k,
co-attivazioni, riferimenti mancanti, positivi/negativi, frontmatter ostile e compatibilità v1/v2.

### Step 8 — Open WebUI gestita e sync

**Precondizione:** il maintainer approva una versione precisa dopo uno spike reale su Python,
dipendenze CPU-only, comando, salute, Functions, prompt e variabili ambiente. Lo spike produce
`resources/open-webui.lock` ed evidenza separata.

Installazione:

- venv immutabili in `data_dir()/open-webui/installations/`;
- staging sullo stesso filesystem;
- verifica versione, import ed eseguibile;
- `installed.json` dentro l'installazione;
- `current.json` atomico con percorso relativo confinato;
- fallimento lascia intatti manifest e versione precedenti;
- pulizia solo di ambienti gestiti non attivi.

Configurazione 0.2: `webui_port=8081` e `QWEN_LAUNCHER_WEBUI_PORT`; porta 1–65535 e diversa da
`llama_port`.

Ambiente minimo, solo dopo verifica del lock: data dir dedicata, host `127.0.0.1`, config persistente
disabilitata, autenticazione disabilitata solo per servizio locale, Ollama off, endpoint OpenAI
locale e chiave placeholder. L'utente viene informato che modifiche UI non persistono.

Fallback: se llama-server è READY ma WebUI fallisce, mantenerlo attivo, mostrare il log e aprire la
UI integrata se consentita. Se il modo richiede UI e nessuna è disponibile, fermare i servizi e
terminare 1.

`sync` genera sotto `data_dir()/sync-out/` function, prompt e istruzioni d'importazione. Template
Python statico; regole e contenuti serializzati come dati JSON, mai interpolati come codice. Nessuna
scrittura API in questo step.

Test: installazione valida/parziale/fallita, manifest, config porte, ambiente, salute, fallback,
stato multi-servizio, contenuto ostile e output riproducibile.

### Step 9 — Benchmark autonomo e doctor definitivo

`benchmark --mode <id>` richiede un server vivo e legge dallo stato modo, modello, motore, record o
fallback, contesto e `n_cpu_moe`. Riusa esattamente `benchmark/v1`: warm-up escluso, cinque misure da
256 token, nessun client concorrente, min/mediana/max e metadata completi.

Con record locale mostra la differenza dalla mediana registrata senza modificarlo. Senza record non
crea una calibrazione e indirizza a `calibrate`.

Completare inoltre:

- `doctor` con stato ✅/⚠️/❌ e rimedio per ogni riga non verde;
- documentazione che distingue benchmark, calibrazione e regressione;
- verifica di regressione ripetibile senza soglia universale inventata;
- template PR evidenza e skill.

Test: server assente/incompatibile, warm-up, cinque misure, mediana, record presente/assente,
confronto, nessuna modifica contenuti, nessuna rete reale e metadata dallo stato.

### Step 10A — Preparazione locale 0.2

Completare documentazione e changelog; verificare upgrade da 0.1 e installazione pulita; versione
`0.2.0rc1`; suite, build, installazione isolata e ispezione artefatti. Nessun tag, push o upload.

### Human Gate 0.2

Il maintainer prova su Ubuntu e Windows: installazione pulita e upgrade, tre modi, router/skill,
Open WebUI e fallback, sync, benchmark, doctor, validate, dati, licenze e Trusted Publisher. Decide
`RELEASE` o `NO-RELEASE`.

### Step 10B — Finalizzazione locale 0.2

Solo dopo `RELEASE`: versione `0.2.0`, changelog finale, documentazione, suite, build e commit locale.
Push, tag, GitHub Release, PyPI e impostazioni remote restano operazioni autorizzate singolarmente.

---

## 9. Criteri di accettazione aperti

### Stabilizzazione 0.1

- [ ] PyPI contiene gli stessi artefatti `0.1.0` già testati.
- [ ] Installazione esplicita da PyPI verificata su Ubuntu e Windows.
- [ ] Correzioni post-release distribuite solo con nuova versione autorizzata.
- [ ] `calibration/v4` verificata realmente su Ubuntu e Windows prima della 0.1.1.
- [~] Evidenza eterogenea aggiunta quando disponibile, senza trasferire buste fra host.

### Milestone 0.2

- [ ] Router deterministico senza regex e skill con test positivi/negativi.
- [ ] Open WebUI e dipendenze appuntate, installazione atomica e fallback verificato.
- [ ] Sync locale tratta contenuti come dati e non li esegue.
- [ ] Benchmark autonomo riusa `benchmark/v1` e non crea record.
- [ ] Doctor fornisce stato e rimedio coerenti.
- [ ] Release 0.2 solo dopo Human Gate e autorizzazioni remote esplicite.

---

## 10. Riferimenti di processo

- Python 3.12 `importlib.resources`:
  <https://docs.python.org/3.12/library/importlib.resources.html>
- CPython 3.12.13: <https://www.python.org/downloads/release/python-31213/>
- uv 0.11.28: <https://github.com/astral-sh/uv/releases/tag/0.11.28>
- uv build backend: <https://docs.astral.sh/uv/concepts/build-backend/>
- sicurezza GitHub Actions: <https://docs.github.com/en/actions/reference/security/secure-use>
- PyPI Trusted Publishing: <https://docs.pypi.org/trusted-publishers/>
- Open WebUI environment: <https://docs.openwebui.com/reference/env-configuration/>

Per `llama.cpp` prevalgono lock ed evidenza della release appuntata, non link mobili al ramo
corrente.

---

## 11. Regola di chiusura

Un lavoro è concluso solo quando codice, test, documentazione corrente, lock ed evidenza concordano.
Un risultato locale non sostituisce CI o gate manuali dichiarati. Dubbi e limiti restano visibili;
non diventano fallback o claim silenziosi.
