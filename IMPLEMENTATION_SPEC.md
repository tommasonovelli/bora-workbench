# qwen-launcher — Specifica centrale di implementazione (v3.1)

## 0. Tracker di avanzamento — aggiornato al 15 luglio 2026

> Questo blocco registra lo stato reale del repository al commit iniziale. Questo è il documento
> normativo `IMPLEMENTATION_SPEC.md` alla radice, unica copia normativa nel repository come previsto
> dallo Step 1; gli output grezzi originali dello spike restano archiviati in
> `archive/project-kickoff-2026-07-14/docs/`. `[x]` significa completato e verificato; `[~]` parziale;
> `[ ]` ancora da eseguire. Una voce parziale **non** soddisfa il gate dello step.

### Stato sintetico

- [x] **Step 0 — Spike tecnico:** `llama.cpp b10011`, commit
  `bf2c86ddc0685f580595954056c2e77ebabfab4f`, ha completato la matrice Ubuntu 24.04 e Windows 11
  CPU/CUDA dei tre modi. Salute, API, metriche, UI esplicita, vision, MTP, sampling, stop/log e
  `benchmark/v1` con warm-up più cinque misure sono verificati. La coppia Windows CUDA 13.3 e i
  termini MIT/NVIDIA sono registrati. `docs/spike-0.md/json` dichiarano `GO`.
- [~] **Step 1 — Scaffold:** implementazione locale completa, incluso `engine.lock`; suite frozen,
  build e wheel isolata sono verdi su Windows. Restano la CI GitHub Ubuntu/Windows, che richiede un
  push non autorizzato implicitamente, e le successive attività umane sul branch.
- [ ] **Step 2 — Schemi, contenuti, validazione e hardware.**
- [ ] **Step 3 — Vertical slice `coding`, stato, stop e status.**
- [ ] **Step 4 — Asset lock e attivazione atomica del motore.**
- [ ] **Step 5 — `studio` e `vstudio`.**
- [ ] **Step 6A / Human Gate / 6B — Release 0.1.**
- [ ] **Step 7 — Skill e router.**
- [ ] **Step 8 — Open WebUI e sync.**
- [ ] **Step 9 — Benchmark e doctor definitivo.**
- [ ] **Step 10A / Human Gate / 10B — Release 0.2.**

### Step 0 — dettaglio

- [x] Release `b10011`, commit completo, versione, help e contratto semantico verificati.
- [x] Modello, mmproj, licenze MIT/Apache-2.0 e checksum verificati senza redistribuire i pesi.
- [x] Asset Ubuntu CPU e sorgente CUDA verificati; matrice CPU/CUDA completa per i tre modi.
- [x] Asset Windows CPU e coppia server/runtime CUDA 13.3 verificati coi digest pubblicati; matrice
  completa per i tre modi, inclusa vision CPU/CUDA.
- [x] Salute 503/200, `/v1/models`, `/v1/chat/completions`, metriche, UI on/off, MTP, sampling,
  log e stop conservati come output grezzi.
- [x] `benchmark/v1`: prompt/richiesta con SHA-256, un warm-up escluso e cinque misure esatte da 256
  token per ciascuna delle dodici combinazioni OS/backend/modo.
- [x] `CUDA_VISIBLE_DEVICES=0` e ambiente padre verificati sulle macchine a GPU singola. La selezione
  fra GPU fisiche multiple non è dimostrabile su questo hardware: la 0.1 dovrà bloccare CUDA su host
  multi-GPU finché il caso non sarà collaudato.
- [x] Evidenza attiva sotto `docs/spike-0/` coperta da SHA-256; archivio iniziale immutato e verificato.
- [x] Decisione finale esplicita: `GO`, senza derivare profili o assetti da RAM, VRAM o tok/s.

### Step 1 — dettaglio

- [x] Scaffold `src/` senza moduli segnaposto degli step successivi.
- [x] `pyproject.toml`, Python `>=3.12,<3.13`, `.python-version` `3.12.13`, `uv_build`, entry point,
  Ruff, pytest, versione `0.1.0.dev0` e `uv.lock` frozen.
- [x] `paths.py` con directory Linux/Windows e nessuna creazione automatica; corretta la simulazione
  XDG su host Windows.
- [x] `config.py` con chiavi 0.1, precedenza ambiente > file > default e validazione severa.
- [x] Helper `importlib.resources` basati su `Traversable`, context manager e controllo percorsi
  assoluti indipendente dall'OS host.
- [x] `engine.lock` creato copiando esclusivamente il contratto verificato dello Spike 0;
  `assets_complete=false` resta intenzionalmente riservato allo Step 4.
- [x] CLI minima con `--version` e `doctor` esplicitamente limitato allo Step 1.
- [x] MIT, `.gitignore`, README, CONTRIBUTING, changelog, CODEOWNERS e template PR.
- [x] Workflow CI Ubuntu/Windows scritto con action a SHA completo, uv/Python appuntati e lock frozen.
- [x] Suite locale Windows: sync frozen, lint, format e 41 test superati con CPython 3.12.13.
- [x] Wheel e sdist costruite su Windows; import, risorse, `engine.lock` e `--version` verificati in
  un ambiente Windows isolato.
- [x] Suite locale Linux precedente: lint, format e 39 test superati; wheel precedente verificata in
  ambiente Linux isolato prima dell'aggiunta di `engine.lock`.
- [ ] Eseguire la matrice CI GitHub Ubuntu/Windows e ricontrollare su Ubuntu gli artefatti aggiornati;
  richiede pubblicare i commit e non è autorizzato implicitamente.
- [x] Preparare il commit locale iniziale Conventional Commits.
- [x] Remote `origin` GitHub configurato.
- [ ] Pubblicare i commit con push (attività umana; non autorizzata implicitamente).
- [ ] Abilitare branch protection e code-owner review (attività umana dopo CI verde).

### Prossima azione obbligatoria

Non iniziare lo Step 2. Per chiudere formalmente lo Step 1, Tommaso deve autorizzare il push, far
eseguire la matrice CI GitHub Ubuntu/Windows e, a CI verde, abilitare branch protection e revisione
code owner. Se la CI rileva differenze, le sole correzioni ammesse restano nel perimetro Step 1.

---

> **Stato:** documento normativo centrale, pronto a guidare l'implementazione per step.  
> **Data di consolidamento:** 14 luglio 2026; revisione sequenziale v3.1 approvata prima dello Step 0.  
> **Sostituisce:** `PIANO_IMPLEMENTAZIONE_v2.md`, le due revisioni successive e la v3 non corretta.  
> **Regola d'uso:** una sessione di sviluppo esegue un solo step, nell'ordine indicato. Prima di
> modificare il repository, l'esecutore legge comunque l'intero documento e applica tutti i
> contratti trasversali. Nessuno step autorizza implicitamente push, tag, pubblicazioni o modifiche
> remote.

Questo file riunisce in un'unica fonte coerente:

1. visione e perimetro del prodotto;
2. decisioni architetturali;
3. contratti normativi e di sicurezza;
4. protocollo di esecuzione per l'agente AI;
5. sequenza operativa delle milestone 0.1 e 0.2;
6. criteri di accettazione e attività manuali.

Il documento è deliberatamente unico. Le decisioni durevoli vengono registrate nella sezione
«Registro delle decisioni» di questo stesso file; il codice e i lock restano le fonti eseguibili.

---

## 1. Prodotto, principi e perimetro

### 1.1 Cosa stiamo costruendo

`qwen-launcher` è una distribuzione locale attorno al modello predefinito
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`. Il pacchetto:

- rileva l'hardware;
- sceglie parametri calibrati tramite profili dichiarativi;
- usa una release precisa e collaudata di `llama.cpp`;
- avvia e governa `llama-server`;
- espone tre modi (`coding`, `studio`, `vstudio`);
- rende estendibili contenuti e profili senza rendere estendibile arbitrariamente il core;
- nella 0.2 aggiunge skill, router deterministico, Open WebUI gestita, sincronizzazione e benchmark.

Non è un generico gestore di modelli, un framework di plugin o un orchestratore multi-backend.

### 1.2 Principio costituzionale

I territori sono separati:

- `src/qwen_launcher/resources/schemas/`: contratti JSON Schema versionati;
- `src/qwen_launcher/resources/content/`: dati contribuiti conformi agli schemi;
- restante `src/qwen_launcher/`: core mantenuto dal proprietario;
- file lock sotto `src/qwen_launcher/resources/`: versioni e compatibilità esterne appuntate.

Gli schemi garantiscono la forma; i test comportamentali garantiscono il comportamento. Estendere il
contenuto significa aggiungere dati che passano `qwen-launcher validate`, non eseguire codice
arbitrario.

### 1.3 Milestone

| Milestone | Contenuto | Step |
|---|---|---:|
| 0.1 | pacchetto, config, risorse, schemi, hardware, profili, CLI, processi, motore, tre modi, installer, documentazione, release | 0–6B |
| 0.2 | skill e router a frasi, Open WebUI gestita, sync, benchmark, doctor definitivo, release | 7–10B |

### 1.4 Piattaforme supportate

- Ubuntu 22.04 o superiore, architettura x86-64;
- Windows 11, architettura x86-64;
- backend `cuda` NVIDIA e `cpu`;
- una sola GPU CUDA usata dal processo, scelta e imposta esplicitamente.

### 1.5 Fuori perimetro

macOS; altre distribuzioni Linux come target garantito; ARM; Vulkan; ROCm; multi-GPU distribuita;
auto-update in background; GUI nativa; plugin Python; modi utente fuori dal pacchetto; cancellazione o
gestione automatica della cache Hugging Face; migrazione automatica di tutte le skill storiche; sync
Open WebUI via API prima che la sua superficie sia verificata sulla versione appuntata.

---

## 2. Gerarchia delle fonti di verità

In caso di conflitto prevale la prima fonte applicabile nell'ordine seguente:

1. lock versionati e artefatti strutturati dello spike (`engine.lock`, in 0.2
   `open-webui.lock`, `docs/spike-0.json`);
2. output reali (`--help`, `--version`, endpoint e asset) della versione appuntata, conservati o
   descritti nello spike;
3. schemi e test già presenti nel repository;
4. questo documento;
5. documentazione ufficiale riferita esattamente alla versione appuntata;
6. documentazione ufficiale corrente, solo per strumenti non ancora appuntati o per procedure
   operative come GitHub Actions e PyPI;
7. assunzioni dell'esecutore.

Regole conseguenti:

- vietato usare `latest` in un file committato;
- per `llama.cpp`, modello e Open WebUI non si correggono flag o comportamenti usando il ramo
  corrente se la versione è già appuntata;
- una contraddizione non si risolve silenziosamente: si interrompe soltanto lo step interessato e si
  descrivono fonti, differenza e impatto;
- l'esecutore non cambia una versione appuntata senza istruzione esplicita del manutentore;
- la documentazione online può confermare una scelta, non scavalcare un lock.

---

## 3. Registro delle decisioni

| ID | Decisione normativa | Motivazione |
|---|---|---|
| D-001 | Python `>=3.12,<3.13` per la 0.1 | evita interpreti futuri non collaudati; il range si allarga solo con CI dedicata |
| D-002 | gestione progetto e lock con `uv`; build backend `uv_build` | un solo tool e backend puro Python con layout `src/` |
| D-003 | dipendenze runtime 0.1: `typer`, `rich`, `psutil`, `httpx`, `jsonschema`; dev: `pytest`, `ruff` | perimetro minimo e controllabile |
| D-004 | `pyyaml` entra solo allo Step 7 | serve al frontmatter delle skill, non alla 0.1 |
| D-005 | risorse dentro la wheel; helper in `qwen_launcher.resources.__init__` | elimina il conflitto `resources.py`/`resources/` |
| D-006 | modi = comportamento; profili = prestazioni per modello, motore, hardware e modo | nessuna precedenza ambigua nella fusione |
| D-007 | un profilo può coprire un sottoinsieme dei modi | aggiungere un modo non invalida tutti i profili |
| D-008 | una sola GPU; `CUDA_VISIBLE_DEVICES` è impostata solo nell'ambiente del figlio | rende reale e stabile la scelta della GPU; va verificato nello spike |
| D-009 | il ripiego rigido di memoria vale solo per il modello predefinito calibrato | non si applicano numeri ignoti a modelli diversi |
| D-010 | `coding` senza UI; `studio` e `vstudio` con UI, sempre tramite flag espliciti verificati | nessuna dipendenza dai default esterni |
| D-011 | router 0.2 a sole frasi normalizzate, senza regex | comportamento sicuro, deterministico e validabile |
| D-012 | release divisa in preparazione, cancello umano e finalizzazione | separa lavoro locale da operazioni remote |
| D-013 | tutte le azioni GitHub di terzi sono appuntate a SHA completo | riferimenti immutabili nei workflow |
| D-014 | `uv.lock` è committato e la CI usa `--frozen` | dipendenze riproducibili |
| D-015 | server legati solo a `127.0.0.1` | nessuna esposizione di rete implicita |
| D-016 | il protocollo manuale `benchmark/v1` nasce nello Step 0; lo Step 9 automatizza lo stesso protocollo | rende utilizzabili nello Step 2 le misure dello spike senza ridefinizioni retroattive |
| D-017 | `engine.lock` contiene un contratto semantico macchina oltre alla lista dei flag | impedisce al builder di associare significati ai flag tramite assunzioni o hardcode non verificato |
| D-018 | le installazioni motore sono directory versionate; `current.json` è il puntatore sostituito atomicamente | evita di promettere una sostituzione atomica di directory non portabile su Windows |
| D-019 | sviluppo e CI usano CPython `3.12.13`, mantenendo il metadato pacchetto `>=3.12,<3.13` | usa la patch di sicurezza più recente disponibile tramite uv 0.11.28 su Linux e Windows x86-64 |
| D-020 | anche la 0.2 usa preparazione locale, cancello umano e finalizzazione | nessuna milestone pubblicabile resta senza procedura di release e autorizzazione esplicita |
| D-021 | percorsi OS e variabili ambiente pubbliche sono fissati prima dello scaffold | evita migrazioni successive di config, dati, cache e stato |
| D-022 | Open WebUI usa ambienti versionati e un manifest di attivazione atomico | applica anche al secondo servizio gestito la portabilità richiesta su Windows |

Le sole decisioni lasciate allo spike sono: release esatta di `llama.cpp`, nomi esatti dei flag per
quella release, forma reale della salute, asset ufficiali disponibili, compatibilità della UI e
funzionamento del pinning GPU. Le sole decisioni lasciate allo Step 8 sono quelle specifiche della
versione di Open WebUI approvata dal manutentore.

---

## 4. Architettura e struttura obiettivo

### 4.1 Responsabilità dei moduli

| Modulo | Responsabilità |
|---|---|
| `cli.py` | comandi, presentazione Rich, mappatura errori/exit code; nessuna logica di piattaforma |
| `paths.py` | directory per OS; nessun'altra logica |
| `config.py` | lettura, precedenze e validazione della configurazione |
| `hardware.py` | RAM/CPU/GPU, unità GiB, selezione GPU |
| `profiles.py` | caricamento dati, matching, ripiego, costruzione `LaunchPlan` |
| `engine.py` | lock, ricerca, compatibilità, download/build, installazione sicura e attivazione atomica |
| `process.py` | processi, segnali, stato, lock d'avvio, salute, log, stop/status |
| `resources/__init__.py` | accesso a risorse di pacchetto tramite `importlib.resources` |
| `validation.py` | validazione schemi e controlli semantici incrociati |
| `routing.py` (0.2) | normalizzazione e scoring puro delle skill |
| `webui.py` (0.2) | lock, ambiente, installazione e processo Open WebUI |
| `benchmark.py` (0.2) | protocollo e misure riproducibili |

Solo quattro moduli possono diramarsi sul sistema operativo:

- percorsi in `paths.py`;
- processi e segnali in `process.py`;
- rilevamento in `hardware.py`;
- asset, eseguibili e build in `engine.py`.

Nessun altro modulo usa `platform.system()`, `os.name` o equivalenti per cambiare comportamento.

### 4.2 Albero a fine 0.1

```text
qwen-launcher/
├── install.sh
├── install.ps1
├── pyproject.toml
├── .python-version
├── uv.lock
├── IMPLEMENTATION_SPEC.md          # unico documento normativo nel repository
├── src/qwen_launcher/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── engine.py
│   ├── hardware.py
│   ├── paths.py
│   ├── process.py
│   ├── profiles.py
│   ├── validation.py
│   └── resources/
│       ├── __init__.py
│       ├── engine.lock
│       ├── schemas/
│       │   ├── mode.v1.json
│       │   └── profile.v1.json
│       └── content/
│           ├── modes/{coding,studio,vstudio}.json
│           └── profiles/*.json
├── docs/
│   ├── spike-0.md
│   ├── spike-0.json
│   ├── spike-0/                    # prompt benchmark e output grezzi verificati
│   ├── engine-lock.md
│   ├── benchmarks.md
│   └── anatomy/{mode,profile}.md
├── scripts/verify_wheel.py
├── tests/
│   ├── fakes/
│   └── ...
├── .github/
│   ├── CODEOWNERS
│   ├── pull_request_template.md
│   └── workflows/{ci,release}.yml
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

### 4.3 Risorse di pacchetto

Le funzioni di accesso vivono in `src/qwen_launcher/resources/__init__.py` e usano
`importlib.resources.files()`. Una risorsa resta un `Traversable`: si usa `read_text()` o
`read_bytes()` quando basta; `as_file()` soltanto dentro un context manager quando una API richiede
un vero percorso. È vietato presumere che una risorsa della wheel sia sempre un `Path` fisico.

Importare `qwen_launcher` non effettua rete, non crea directory, non scrive file e non avvia processi.

---

## 5. Contratti normativi trasversali

### 5.1 Stack, packaging e dipendenze

- Python del pacchetto: `>=3.12,<3.13`.
- Python appuntato per sviluppo e CI: CPython `3.12.13`, registrato in `.python-version`; la CI lo
  installa tramite uv `0.11.28`, che ne dispone per Linux e Windows x86-64.
- Layout: `src/`.
- Build backend iniziale:

  ```toml
  [build-system]
  requires = ["uv_build>=0.11.28,<0.12"]
  build-backend = "uv_build"
  ```

- Versione di `uv` registrata in `pyproject.toml`/`uv.toml` e usata identica in CI; valore iniziale
  approvato per lo scaffold: `0.11.28`.
- `uv.lock` sempre committato; ogni modifica a dipendenze dirette aggiorna il lock nello stesso
  commit; CI con `uv sync --frozen` e comandi `uv run --frozen`.
- Dipendenze di sviluppo in `[dependency-groups]`.
- Wheel e sdist devono contenere schemi, contenuti e lock.
- `scripts/verify_wheel.py` individua esattamente una wheel senza glob dipendenti dalla shell e crea
  un ambiente isolato. Nello Step 1 verifica import, lettura risorse e `--version`; dallo Step 2
  verifica anche `validate` dall'installazione.
- Le GitHub Actions sono appuntate a SHA completo e commentate con la versione umana corrispondente.

### 5.2 Configurazione

I percorsi pubblici sono determinati senza creare directory:

| Funzione | Linux | Windows |
|---|---|---|
| `config_dir()` | `${XDG_CONFIG_HOME:-$HOME/.config}/qwen-launcher` | `%APPDATA%\\qwen-launcher` |
| `data_dir()` | `${XDG_DATA_HOME:-$HOME/.local/share}/qwen-launcher` | `%LOCALAPPDATA%\\qwen-launcher\\data` |
| `cache_dir()` | `${XDG_CACHE_HOME:-$HOME/.cache}/qwen-launcher` | `%LOCALAPPDATA%\\qwen-launcher\\cache` |
| `state_dir()` | `${XDG_STATE_HOME:-$HOME/.local/state}/qwen-launcher` | `%LOCALAPPDATA%\\qwen-launcher\\state` |

Una variabile XDG assente, vuota o non assoluta usa il fallback indicato, come richiesto dalla XDG
Base Directory Specification. Su Windows, se `APPDATA` o `LOCALAPPDATA` sono eccezionalmente assenti,
vuote o non assolute, si usano rispettivamente
`~/AppData/Roaming` e `~/AppData/Local`. I test simulano gli OS senza dipendere dall'host.

File: `config_dir()/config.toml`. Le chiavi TOML sono alla radice. Precedenza: ambiente > file >
default nel codice. Le sole variabili pubbliche della 0.1 sono:

| Chiave | Variabile ambiente |
|---|---|
| `model` | `QWEN_LAUNCHER_MODEL` |
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` |

Configurazione 0.1:

| Chiave | Default | Vincolo |
|---|---|---|
| `model` | modello predefinito | stringa non vuota |
| `llama_port` | `8080` | intero 1–65535 |
| `engine_path` | `None` | percorso opzionale; `~` espansa |
| `open_browser` | `true` | booleano |

`webui_port` non esiste fino allo Step 8.

Regole:

- chiavi TOML sconosciute = input invalido;
- il file intero viene validato prima di creare `Config`;
- booleani ambiente ammessi, senza distinzione maiuscole/minuscole: `true/false`, `1/0`, `yes/no`,
  `on/off`;
- `QWEN_LAUNCHER_ENGINE_PATH` vuota = `None`;
- tutte le altre variabili presenti ma vuote o invalide = errore, non fallback;
- file assente = default; TOML malformato = errore chiaro su stderr senza traceback;
- il launcher non modifica mai automaticamente `config.toml`.

### 5.3 Schemi dei modi e dei profili

Tutti gli oggetti usano JSON Schema 2020-12, `additionalProperties: false`, descrizione per ogni campo
e identificatori `^[a-z0-9-]+$`.

`mode/v1` possiede soltanto:

- `schema`, costante `mode/v1`;
- `id`, uguale al nome del file senza estensione;
- `description`, stringa non vuota;
- `services.ui` e `services.vision`, booleani obbligatori;
- `sampling.temp`, numero `>= 0`;
- `sampling.top_p`, numero `> 0` e `<= 1`;
- `sampling.top_k`, intero `>= 0`.

`profile/v1` possiede soltanto:

- `schema`, costante `profile/v1`;
- `id`, uguale al nome del file;
- `model`, identificatore completo del modello calibrato;
- `engine`, release esatta usata nel benchmark;
- `measured_on`, descrizione non vuota della macchina;
- `benchmark_protocol`, inizialmente `benchmark/v1`, definito manualmente nello Step 0 e
  automatizzato senza variazioni nello Step 9;
- `match.backend`, `cuda` o `cpu`;
- `match.vram_gib` e `match.ram_gib`, coppie `[min, max]`, con `min >= 0`, `max` numero o
  `null`, estremi inclusivi e controllo semantico `min <= max`;
- `match.os`, opzionale, almeno un valore unico fra `linux` e `windows`;
- `modes`, oggetto con almeno un modo; ogni busta contiene `ctx` intero `>= 1024`, `tok_s` opzionale
  `{min, median, max}` con numeri `>= 0` e controllo semantico `min <= median <= max`; `n_cpu_moe`
  è un intero `>= 0` obbligatorio per profili CUDA e vietato per profili CPU, tramite controllo
  semantico incrociato col backend.

Un profilo può coprire solo alcuni modi. `validate` segnala come errore un modo citato ma inesistente;
non segnala come errore un modo non coperto. Sampling e servizi non possono comparire nei profili;
parametri di memoria non possono comparire nei modi.

Le dataclass gelate costituiscono il modello runtime. Gli eventuali default sono applicati dai
caricatori, mai da `jsonschema`.

### 5.4 Hardware e unità

`HardwareInfo` contiene almeno:

```text
os_name
cpu_cores
ram_total_gib
ram_available_gib
backend
gpu_count
gpu_index
gpu_name
vram_total_gib
vram_free_gib
```

Conversioni: byte / `1024³`; MiB / `1024`. Il suffisso `_gib` è obbligatorio nel codice e negli
schemi.

Per NVIDIA si invoca `nvidia-smi` senza shell, timeout 5 secondi, chiedendo indice, nome, memoria
totale e libera. Si sceglie la GPU con più VRAM totale; parità → indice numerico minore. Output
assente, fallito o non interpretabile → backend CPU con warning diagnostico, non crash.

In presenza di più GPU, il launcher avvisa e imposta `CUDA_VISIBLE_DEVICES=<gpu_index>` soltanto
nell'ambiente del processo figlio. Non modifica l'ambiente del processo padre. Lo spike deve
dimostrare che la release appuntata usa esclusivamente quella GPU; se la prova fallisce, la 0.1
blocca l'avvio CUDA multi-GPU con errore operativo invece di promettere un isolamento non reale.

### 5.5 Matching, buste e ripiego

Un profilo è calibrato soltanto se coincidono modello, release del motore, backend, OS quando
specificato, intervalli hardware e modo richiesto.

Spareggio fra profili calibrati, con estremi inclusivi:

```text
CUDA:
  1. intervallo VRAM più stretto
  2. intervallo RAM più stretto
  3. profilo limitato all'OS corrente prima di uno generico
  4. id alfabetico

CPU:
  1. intervallo RAM più stretto
  2. profilo limitato all'OS corrente prima di uno generico
  3. id alfabetico
```

Un massimo `null` vale infinito e produce un intervallo meno specifico di qualunque intervallo finito
con lo stesso minimo. Un pareggio risolto dall'id genera un warning in `doctor`.

Gate di memoria per il solo modello predefinito:

```python
DEFAULT_MODEL_MIN_TOTAL_GIB = 28.0
DEFAULT_MODEL_MIN_AVAILABLE_GIB = 24.0
```

Se una delle soglie non è raggiunta, l'avvio si ferma prima di qualunque download. `--force` bypassa
esclusivamente questo gate; non bypassa config invalida, OS non supportato, motore assente o
incompatibile, porta occupata, checksum, contenuti invalidi o lock.

Dopo il gate:

1. profilo calibrato per il modo → usa la sua busta;
2. hardware/modo non calibrato ma modello predefinito con memoria sufficiente → preset prudente
   (`ctx=16384`; `n_cpu_moe=48` su CUDA, assente su CPU), warning e invito a contribuire;
3. modello diverso dal predefinito → nessun profilo del modello predefinito viene usato; preset
   prudente con warning rafforzato, senza gate rigido basato su numeri non calibrati.

`LaunchPlan` è la fusione non ambigua di modo + busta + config + identità del profilo/fallback +
backend/GPU. Un modo inesistente è input CLI invalido e mostra l'elenco dei modi validi.

### 5.6 Contratto del comando motore

I nomi dei flag non sono definiti dalla memoria dell'esecutore né dal ramo corrente di `llama.cpp`.
Lo Step 0 li verifica sulla release scelta e li registra in `engine.lock` come `verified_flags` e
come template nel contratto semantico macchina `command_contract`. Il builder espande soltanto i
placeholder dichiarati dal lock; non associa nel codice un significato a un flag non descritto.

Il costruttore di argomenti deve rappresentare esplicitamente:

- modello/repository;
- contesto;
- sampling;
- host `127.0.0.1` e porta;
- metriche;
- template/Jinja e impostazioni MTP/cache/flash/mmap richieste dal modello, se confermate;
- UI abilitata o disabilitata, senza affidarsi al default esterno;
- mmproj/vision abilitato o disabilitato, senza affidarsi al default esterno;
- CUDA: GPU layers e `n_cpu_moe` solo se previsti dal contratto verificato; l'eventuale valore GPU
  layers è fisso nel lock per modello/release, mentre il profilo fornisce `n_cpu_moe`. Se lo spike
  dimostra che anche GPU layers deve variare per hardware, il gate resta chiuso finché schema e piano
  non vengono aggiornati esplicitamente;
- CPU: nessun `n_cpu_moe`; lo spike/lock stabilisce esplicitamente se il backend CPU richiede un
  flag «GPU off» verificato oppure l'assenza documentata degli argomenti CUDA.

Si preferiscono nomi lunghi se la release li supporta. Un test obbligatorio estrae ogni token
opzione, cioè ogni token che inizia con `-`, da tutti gli array di argomenti del lock e dagli
argomenti emessi dal builder e verifica che appartenga a `verified_flags`. Il test deve fallire se lock o codice
introducono un flag non collaudato. Sono ammessi nei template soltanto placeholder enumerati e
validati; un placeholder sconosciuto rende invalido il lock.

### 5.7 Motore e `engine.lock`

Formato minimo del lock; i nomi reali dei flag e i valori fissi arrivano esclusivamente dallo spike:

```json
{
  "schema": "engine-lock/v1",
  "project": "ggml-org/llama.cpp",
  "release": "<scelta nello spike>",
  "source_commit": "<sha verificato>",
  "default_model": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M",
  "verified_flags": ["<flag esatti>"],
  "version_contract": {
    "args": ["<flag versione verificato>"],
    "exit_code": 0,
    "output_contains": ["<frammenti esatti e stabili osservati>"]
  },
  "help_contract": {
    "args": ["<flag help verificato>"],
    "exit_code": 0,
    "must_list_verified_flags": true
  },
  "command_contract": {
    "model_args": ["<flag>", "{model}"],
    "context_args": ["<flag>", "{ctx}"],
    "sampling_args": {
      "temp": ["<flag>", "{temp}"],
      "top_p": ["<flag>", "{top_p}"],
      "top_k": ["<flag>", "{top_k}"]
    },
    "network_args": ["<flag>", "127.0.0.1", "<flag>", "{port}"],
    "metrics_args": ["<flag o sequenza verificata>"],
    "fixed_args": ["<template/Jinja/MTP/cache/flash/mmap verificati>"],
    "ui_args": {"enabled": ["<sequenza>"], "disabled": ["<sequenza>"]},
    "vision_args": {"enabled": ["<sequenza>"], "disabled": ["<sequenza>"]},
    "backend_args": {
      "cuda": ["<sequenza con valore GPU layers fisso ed eventuale {n_cpu_moe}>"],
      "cpu": ["<sequenza CPU verificata, anche vuota>"]
    }
  },
  "api_contract": {
    "base_path": "<path verificato>",
    "chat_completions_path": "<path verificato>",
    "ui_path": "<path verificato o null>"
  },
  "health_contract": {
    "path": "/health",
    "transient_statuses": [503],
    "ready_status": 200,
    "ready_json": {"status": "<valore verificato>"}
  },
  "assets_complete": false,
  "assets": [
    {
      "os": "windows",
      "backend": "cuda",
      "role": "server",
      "filename": "<nome>",
      "url": "https://...",
      "sha256": "<64 hex>",
      "archive": "zip",
      "executable": "bin/llama-server.exe"
    }
  ]
}
```

Le sequenze mostrate fra parentesi angolari sono segnaposto della specifica e non valori ammessi in
un lock prodotto. `docs/spike-0.json` e `engine.lock` devono contenere dati reali; un comportamento
non applicabile usa una sequenza vuota o `null` soltanto dove il contratto lo consente, con la
motivazione nello spike.

Ruoli ammessi almeno: `server`, `cuda-runtime`, `source`. Asset e checksum possono essere vuoti nello
Step 1 con `assets_complete=false`; dallo Step 2 `validate` emette un warning ed `engine install`
rifiuta di procedere. Lo Step 4 completa gli asset, verifica tutte le combinazioni supportate e
imposta `assets_complete=true`. La procedura di aggiornamento e rigenerazione checksum vive in
`docs/engine-lock.md`, non in commenti JSON.

Ordine di ricerca del motore:

1. `engine_path` esplicito;
2. eseguibile nel `PATH`;
3. installazione gestita indicata da `data_dir()/engine/current.json`.

`current.json` contiene schema, release, backend e percorso relativo dell'eseguibile dentro una
directory immutabile sotto `data_dir()/engine/installations/`. Il percorso viene risolto e verificato
come discendente della directory gestita prima dell'uso. Ogni candidato deve soddisfare
`version_contract` e `help_contract`, esporre tutti i `verified_flags` e corrispondere alla release
del lock. Un
candidato incompatibile non viene usato silenziosamente.

### 5.8 Processi, stato, salute e log

Lo stato vive in `state_dir()/services.json`, versione 1. Ogni servizio conserva almeno:

```json
{
  "label": "llama-server",
  "pid": 123,
  "create_time": 0.0,
  "executable": "...",
  "port": 8080,
  "started_at": "...",
  "log_path": "...",
  "mode": "coding",
  "model": "...",
  "engine_release": "...",
  "profile_id": null,
  "ctx": 16384,
  "n_cpu_moe": 48,
  "backend": "cuda",
  "gpu_index": 0
}
```

`n_cpu_moe` è `null` per un piano CPU. Gli altri campi specifici del piano possono essere `null` per
servizi diversi da llama-server. Identità di processo = `pid + create_time`; mai terminare un
processo se non coincidono.

Regole di stato:

- scritture atomiche con file temporaneo nella stessa directory, flush e `Path.replace()`;
- file assente o nessun servizio vivo: `status` e `stop` exit 0;
- voci morte o con PID riusato: rimosse con warning;
- JSON malformato: rinomina atomica in `services.corrupt-<timestamp>.json`, warning e ricostruzione
  vuota;
- nessuna directory o file viene creato durante il semplice import.

Concorrenza:

- prima del controllo stato si acquisisce `state_dir()/start.lock` con creazione esclusiva
  `O_CREAT | O_EXCL`;
- il lock registra `pid + create_time` del proprietario;
- lock vivo → secondo avvio rifiutato;
- lock sicuramente obsoleto → rimosso e acquisizione ritentata una volta;
- rimozione in `finally` soltanto dal proprietario.

Avvio:

- controllo preventivo della porta;
- `Popen` senza shell; su Windows nuovo process group;
- ambiente del figlio costruito esplicitamente;
- stdout e stderr nello stesso log UTF-8 timestampato in
  `state_dir()/logs/<servizio>-YYYYMMDD-HHMMSS.log`;
- nessuna rotazione in 0.1; il percorso del log è sempre mostrato in caso di errore.

Salute:

- timeout HTTP per richiesta: 2 secondi;
- intervallo polling: 1 secondo;
- timeout totale caricamento: 15 minuti;
- connessione rifiutata, timeout, status di caricamento e 5xx dichiarati transitori → nuovo tentativo;
- risposta pronta = status e corpo esatti verificati nello spike/lock;
- `200` con corpo incompatibile o 4xx → errore immediato di incompatibilità/configurazione;
- morte del processo → errore immediato con percorso del log.

Stop:

- verifica identità;
- terminate e attesa fino a 10 secondi;
- kill e attesa fino a 5 secondi se necessario;
- pulizia atomica dello stato;
- `Ctrl-C` esegue la stessa pulizia e termina con 130.

### 5.9 Installazione sicura del motore

- mai `shell=True`, `sudo`, `apt`, elevazione PowerShell o modifiche di sistema automatiche;
- prerequisiti mancanti: elenco chiaro e comando suggerito da copiare, poi exit 1;
- download HTTPS in file `.part` dentro la cache gestita;
- checksum prima di estrarre;
- estrazione che rifiuta path assoluti, drive Windows, `..`, symlink/hardlink pericolosi e uscite
  dalla directory destinazione;
- preparazione in directory temporanea gestita, sullo stesso filesystem della destinazione;
- verifica dell'eseguibile e della compatibilità prima dell'attivazione;
- promozione dello staging in una nuova directory immutabile sotto `engine/installations/`;
- scrittura e sostituzione atomica del file `engine/current.json`, mai sostituzione atomica promessa
  per una directory non vuota;
- installazione precedente e vecchio manifest intatti fino alla riuscita della promozione; una
  pulizia successiva può riguardare soltanto directory gestite non più attive;
- stesso release/backend già valido = no-op, salvo `engine install --force`;
- cambio backend = nuova installazione completa e attivazione atomica tramite manifest;
- TLS e checksum non possono essere disabilitati;
- cancellazioni limitate a `data_dir()/engine` e `cache_dir()/llama.cpp` dopo verifica del percorso;
- per Ubuntu CUDA si usa l'asset sorgente appuntato e verificato dal lock; niente clone di un tag
  mobile e niente installazione automatica di pacchetti.

### 5.10 Errori ed exit code

| Caso | Exit code |
|---|---:|
| successo | 0 |
| errore operativo atteso | 1 |
| input CLI o configurazione invalida | 2 |
| interruzione `Ctrl-C` | 130 |
| `status` senza servizi | 0 |
| `stop` senza servizi | 0 |
| `validate` con soli warning | 0 |
| `validate` con errori | 1 |
| `doctor` con warning | 0 |
| `doctor` con errore bloccante | 1 |

Gli errori attesi vanno su stderr, sono azionabili e non mostrano traceback. Le eccezioni operative
non vengono catturate e ignorate: vengono trasformate in un errore esplicito oppure propagate come
bug inatteso.

### 5.11 Divieti globali

È vietato:

- usare `shell=True`, `eval()` o `exec()`;
- ascoltare su `0.0.0.0`;
- effettuare rete nei test o durante l'import del package;
- creare file o directory durante l'import;
- cambiare uno schema in modo incompatibile senza nuova versione;
- ridurre le asserzioni dei test per farli passare;
- aggiungere fallback non descritti qui;
- modificare configurazione utente o cache Hugging Face;
- cancellare file fuori dalle directory gestite;
- disabilitare TLS o verifiche checksum;
- eseguire comandi amministrativi o richiedere elevazione automatica;
- fare push, tag, release, pubblicazioni o modifiche remote senza autorizzazione esplicita nella
  sessione corrente;
- anticipare feature di step successivi o aggiungere supporto «per completezza»;
- introdurre plugin, `async` non necessario, astrazioni monouso o framework di configurazione.

---

## 6. Protocollo obbligatorio per ogni step

### 6.1 Prima delle modifiche

1. Leggi l'intero documento, non soltanto lo step corrente.
2. Leggi `docs/spike-0.md`, `docs/spike-0.json`, lock, schemi e test pertinenti già presenti.
3. Esegui `git status` e conserva tutte le modifiche preesistenti dell'utente.
4. Esegui lint e test prima di modificare.
5. Se il punto di partenza non è verde, non occultare il problema: stabilisci se è causato dallo
   step precedente o da modifiche estranee e riferisci il blocco quando non è aggirabile.
6. Elenca internamente i file autorizzati dallo step.
7. Conserva le interfacce pubbliche introdotte in precedenza.
8. Non rinominare, spostare o generalizzare componenti senza richiesta esplicita.

Eccezione di bootstrap: nello Step 0, se esistono soltanto la specifica e nessun repository Git o
progetto Python, si inizializza Git localmente e si registrano come non applicabili i controlli su
lock, schemi, lint e test inesistenti. Questa eccezione non autorizza remote, push o codice prodotto.

### 6.2 Durante lo step

- implementa soltanto il perimetro descritto;
- una scelta locale e reversibile non coperta può ricevere un commento `# DECISIONE LOCALE:`;
- una scelta architetturale o durevole richiede aggiornamento esplicito del «Registro delle
  decisioni» e approvazione del manutentore;
- una contraddizione fra fonti ferma lo step interessato;
- nessuna rete nei test; processi, GPU e server reali sono simulati.

### 6.3 Prima di concludere

1. Esegui i test specifici dello step.
2. Esegui `uv run --frozen ruff check .`.
3. Esegui `uv run --frozen ruff format --check .`.
4. Esegui `uv run --frozen pytest`.
5. Esegui `qwen-launcher validate` quando esiste.
6. Costruisci e verifica la wheel quando lo step modifica packaging o risorse.
7. Mostra `git status`; il commit locale deve contenere solo lo step.
8. Nel resoconto finale indica file modificati, comportamento, test, verifiche manuali residue,
   decisioni e conflitti.

Un commit locale Conventional Commits per step è autorizzato solo se la sessione lo richiede o il
repository segue già questo piano. Push e tag non lo sono.

---

## 7. Piano di implementazione — Milestone 0.1

### Step 0 — Spike tecnico e contratto macchina

**Responsabile:** Tommaso con esecuzione e assistenza dell'agente. **Nessun codice prodotto.**
L'agente conduce ricerca, prove Ubuntu e redazione; Tommaso approva la release e svolge o supervisiona
le prove Windows reali che l'ambiente dell'agente non può attestare.

**Obiettivo:** dimostrare la fattibilità sulla release scelta prima dello scaffold.

**Protocollo manuale `benchmark/v1`, già normativo per i profili dello Step 2:**

- prompt testuale fisso in `docs/spike-0/benchmark-v1-prompt.txt` e template della richiesta in
  `docs/spike-0/benchmark-v1-request.json`, entrambi identificati dal loro SHA-256 nello spike JSON;
- 256 completion token esatti per misura; il meccanismo verificato per evitare una chiusura
  anticipata e l'eventuale seed sono registrati nel template. Se la release non consente misure
  valide da 256 token, il protocollo viene corretto prima del `GO`, non retroattivamente;
- un warm-up completo escluso e cinque misurazioni valide per ogni combinazione OS/backend/modo
  effettivamente dichiarata calibrata;
- nessun client concorrente;
- tok/s dalle metriche della release se lo spike ne dimostra l'affidabilità, altrimenti conteggio
  token/tempo con metodo e punti temporali documentati;
- registrazione di misure singole, minimo, mediana e massimo, oltre a OS, hardware, modello, motore,
  modo e parametri; la media facoltativa non sostituisce la mediana.

Lo Step 9 trasferisce lo stesso prompt e template richiesta nelle risorse di pacchetto e automatizza
questo protocollo senza cambiarne semantica o numeri. Una modifica futura richiede `benchmark/v2`.

**Attività:**

1. Se necessario, inizializza il repository Git soltanto in locale e registra il punto di partenza.
2. L'agente identifica release precise candidate alla selezione di `ggml-org/llama.cpp`, confronta
   stabilità, supporto al modello e asset, e formula una raccomandazione motivata; Tommaso approva esplicitamente
   una release precisa prima dei download e benchmark pesanti.
3. Prima delle prove si verificano preliminarmente esistenza e licenza del modello, licenza e
   redistribuibilità del motore e degli asset, nonché disponibilità indicativa dei nomi
   `qwen-launcher` su PyPI e GitHub. Nessun controllo di disponibilità costituisce prenotazione; il
   controllo umano finale dello Human Gate 0.1 resta obbligatorio.
4. Si registrano tag/release, commit sorgente, output versione, help completo e asset ufficiali per:
   Windows x64 CUDA, Windows x64 CPU, Ubuntu x64 CPU e sorgente Ubuntu CUDA.
5. Si parte dai parametri prudenti già dichiarati nel piano e si registrano per ogni prova `ctx`,
   GPU layers, `n_cpu_moe` e motivazione di ogni variazione. Una busta entra in un profilo soltanto se
   è stata realmente provata con quella combinazione.
6. Su Windows 11 e Ubuntu si provano i tre modi col modello predefinito, usando soltanto flag presenti
   nell'help della release. La matrice proposta da collaudare è: coding UI off/vision off e sampling
   `(0.6, 0.95, 20)`; studio UI on/vision off e `(0.7, 0.8, 20)`; vstudio UI on/vision on e
   `(0.7, 0.8, 20)`. Ogni correzione viene motivata nello spike.
7. Si verificano: caricamento, salute, API, MTP, sampling, UI on/off esplicita, mmproj/immagini,
   metriche, CPU senza flag CUDA, CUDA, `CUDA_VISIBLE_DEVICES`, stop e log.
8. Si esegue `benchmark/v1`; nessun numero viene inventato e nessun profilo viene dichiarato per una
   combinazione non misurata.
9. Si verifica il comportamento esatto della salute: status di caricamento, risposta pronta e corpo.
10. Si produce il contratto macchina con version/help probe, associazione semantica dei flag, API,
    salute, UI/vision e backend CPU/CUDA, non soltanto una lista di opzioni osservate.

**Output obbligatori:**

- `docs/spike-0.md`, leggibile dall'umano, con comandi esatti, limiti ed esiti;
- `docs/spike-0.json`, strutturato, con release, commit, modello, `version_contract`, `help_contract`,
  flag verificati, `command_contract`, `api_contract`, `health_contract`, asset, piattaforme, comandi,
  protocollo e misure;
- `docs/spike-0/` con prompt benchmark e output grezzi completi di help/versione necessari a
  riprodurre il contratto;
- decisione `GO` o `NO-GO` per la 0.1.

**Gate:** con `NO-GO` il piano viene corretto prima dello Step 1. Un `GO` richiede i risultati reali
Ubuntu e Windows previsti; un test non eseguibile viene dichiarato mancante e non trasformato in un
esito positivo. Nessun flag ipotetico passa allo scaffold.

**Commit locale suggerito:** `docs: registra spike tecnico e contratto llama.cpp`

Dopo questo primo commit Tommaso può creare e collegare il repository GitHub. Creazione del remote e
push restano attività umane e non sono parte implicita dello Step 0.

### Step 1 — Scaffold installabile, config, risorse e CI

**Precondizione:** Step 0 `GO` e artefatti completi.

**Obiettivo:** repository con la sola specifica e gli artefatti dello Step 0 → wheel installabile e
verificata su Ubuntu e Windows.

**Perimetro:** packaging, `paths.py`, `config.py`, `resources/__init__.py`, CLI minima, CI, test relativi,
documenti dello spike.

**Attività:**

1. Crea lo scaffold necessario allo Step 1, senza moduli segnaposto degli step successivi, e rinomina
   questo documento in `IMPLEMENTATION_SPEC.md`, che resta l'unica copia normativa nel repository.
2. Configura Python `>=3.12,<3.13`, `.python-version` `3.12.13`, `uv_build`, dipendenze, entry point
   `qwen-launcher = "qwen_launcher.cli:app"`, Ruff (linea 100, target py312), pytest, `uv.lock` e
   versione `0.1.0.dev0`.
3. Implementa `paths.py` con la mappa esatta della sezione 5.2, senza side effect all'import.
4. Implementa il contratto config 0.1 completo.
5. Implementa l'accesso risorse dentro il package con `files()`/`as_file()`.
6. Crea `engine.lock` iniziale copiando release, commit, modello, `version_contract`,
   `help_contract`, flag, `command_contract`, API e salute da `docs/spike-0.json`; `assets` può
   restare incompleto fino allo Step 4, marcato esplicitamente con `assets_complete=false`.
7. Crea CLI con `--version` da `importlib.metadata` e `doctor` segnaposto.
8. Aggiungi MIT attribuita a Tommaso Novelli, `.gitignore`, README/CONTRIBUTING provvisori e
   CODEOWNERS globale `* @tommasonovelli`.
9. CI su Ubuntu e Windows: action appuntate a SHA; uv `0.11.28` e Python `3.12.13` appuntati; sync
   frozen; lint; test; build; ambiente isolato; verifica wheel.
10. Conclusi test e commit locali, Tommaso collega il repository remoto se non lo ha già fatto e
    pubblica il commit dello Step 1. Lo Step 1 resta aperto finché la matrice CI Ubuntu/Windows non è
    verde; eventuali correzioni restano nel perimetro dello Step 1.
11. A CI verde Tommaso abilita branch protection: CI obbligatoria e revisione code owner
    obbligatoria.

**Test obbligatori:** percorsi per OS; precedenze config; chiavi/porte/booleani invalidi; file assente
e TOML malformato; lettura risorse dalla wheel; smoke CLI; verifica wheel multipiattaforma.

**Definition of Done:** CI verde sui due OS; import, risorse e `--version` verificati
nell'installazione isolata. `validate` entra nella verifica wheel soltanto allo Step 2.

**Commit locale suggerito:**
`chore: scaffold installabile con config, risorse e CI riproducibile`

### Step 2 — Schemi, contenuti, validazione e hardware

**Obiettivo:** costituzione dati v1 e rilevamento affidabile della macchina.

**Attività:**

1. Implementa `mode.v1.json` e `profile.v1.json` secondo la sezione 5.3.
2. Crea i modi `coding`, `studio`, `vstudio` con valori collaudati nello spike. Valori iniziali di
   sampling: coding `(0.6, 0.95, 20)`; studio/vstudio `(0.7, 0.8, 20)`, salvo correzione documentata
   dallo spike.
3. Crea profili soltanto per combinazioni realmente misurate. Ogni profilo dichiara OS, modello,
   release, macchina e buste effettive; non si riusa automaticamente un benchmark Linux su Windows.
4. Implementa dataclass gelate, caricatori e `validation.py`.
5. `validate` mostra file, percorso del campo e motivo; esegue anche controlli semantici, riferimenti
   tra modi/profili, coerenza modello/motore e ordinamento tok/s.
6. Divergenza `profile.engine != engine.lock.release` = warning e profilo non calibrato a runtime;
   contenuto malformato o riferimento a modo inesistente = errore.
7. Implementa `HardwareInfo`, rilevamento NVIDIA, RAM disponibile e politica GPU.
8. Estendi `doctor` con OS, CPU, RAM totale/disponibile, GPU, VRAM, backend, versione e percorsi.
9. Aggiungi `validate` sia alla CI sorgente sia alla verifica della wheel installata.

**Test obbligatori:** esempi validi; ogni classe di errore schema; controlli semantici; profilo
parziale valido; motore divergente; `nvidia-smi` presente/assente/fallito/corrotto; due GPU e spareggio;
conversioni GiB.

**Definition of Done:** tutti i contenuti viaggiano nella wheel e `validate` restituisce gli exit code
contrattuali.

**Commit locale suggerito:**
`feat: aggiungi schemi v1, validate e rilevamento hardware`

### Step 3 — Vertical slice `coding`, stato, stop e status

**Obiettivo:** usare un motore dello spike già presente e ottenere un prodotto funzionante end-to-end.

**Attività:**

1. Implementa matching e ripiego secondo 5.5, inclusi modello e modo.
2. Implementa `LaunchPlan` e builder CPU/CUDA con flag esatti del lock.
3. Aggiungi il test di coerenza: ogni flag emesso appartiene a `verified_flags`.
4. Implementa `engine.locate()` con ordine e compatibilità di 5.7.
5. Implementa stato, lock d'avvio, log, porta, salute, timeout, identità processo e stop secondo 5.8.
6. L'ambiente figlio CUDA include la sola GPU scelta se lo spike ne ha confermato l'efficacia.
7. Implementa `coding --force`: detect → gate memoria → resolve → locate → start → salute → endpoint
   API → foreground.
8. `coding` applica esplicitamente UI off e vision off.
9. Implementa `stop` e `status` idempotenti.
10. Crea `tests/fakes/fake_server.py` con salute ritardata, 503, risposta incompatibile e crash.

**Test obbligatori:** matching CUDA/CPU; modello diverso; profilo senza modo; RAM totale o disponibile
bassa; perimetro di `--force`; builder CPU/CUDA e UI/vision; flag-lock; ready; timeout; crash; porta
occupata; doppio avvio; lock obsoleto; stato corrotto; PID riusato; stop/status senza servizi;
Ctrl-C.

**Verifica manuale:** su entrambe le macchine, `coding` col motore dello spike; modello servito, tok/s
compatibili col profilo, GPU corretta, stop pulito.

**Definition of Done:** `coding` è usabile e nessun processo estraneo può essere terminato tramite
stato obsoleto.

**Commit locale suggerito:**
`feat: completa vertical slice coding con lifecycle sicuro`

### Step 4 — Asset lock e attivazione atomica del motore

**Obiettivo:** preparare una macchina senza motore tramite `qwen-launcher engine install`.

**Attività:**

1. Completa `engine.lock` con asset reali dello spike, ruoli, URL HTTPS, SHA-256, formato archivio,
   percorso eseguibile e sorgente/commit per Ubuntu CUDA; dopo la verifica imposta
   `assets_complete=true`.
2. Documenta in `docs/engine-lock.md` come aggiornare volontariamente release, asset, checksum,
   spike e benchmark.
3. Implementa download in streaming `.part`, checksum, estrazione sicura, staging, promozione in
   directory versionata e attivazione atomica tramite `current.json`.
4. Windows CUDA/CPU e Ubuntu CPU usano prebuilt solo se verificati nello spike.
5. Ubuntu CUDA usa sorgente appuntata e verificata; controlla prerequisiti, stampa i comandi di
   installazione mancanti, non li esegue, poi configura e compila il solo server senza shell.
6. Implementa `engine install [--force]` ed `engine status` con release attiva, backend, percorso,
   compatibilità e differenze dal lock.
7. Estendi `doctor` con la sezione motore.

**Test obbligatori:** parsing lock; selezione asset per coppia OS/backend; hash corretto/errato;
download interrotto; path traversal e link pericolosi; staging fallito con installazione precedente
intatta; manifest interrotto/corrotto; no-op stessa release; cambio backend; locate
compatibile/incompatibile.

**Verifiche manuali:** installazione reale Windows CUDA/CPU, Ubuntu CPU e Ubuntu CUDA disponibili;
avvio `coding` dopo l'installazione.

**Commit locale suggerito:**
`feat: aggiungi installazione e attivazione atomica del motore da lock`

### Step 5 — `studio` e `vstudio` con UI integrata

**Obiettivo:** completare i tre modi senza introdurre Open WebUI nella 0.1.

**Attività:**

1. Usa esclusivamente il contratto UI/vision dello spike e del lock.
2. `studio`: UI on, vision off; dopo READY apre la radice locale se `open_browser=true`.
3. `vstudio`: UI on, vision on; abilita mmproj esattamente come verificato.
4. Se lo spike dimostra che la UI integrata non supporta l'immagine ma l'API sì, `vstudio` resta
   disponibile e lo dichiara chiaramente; non simula supporto inesistente.
5. Entrambi mostrano URL UI, endpoint API, modo, profilo/fallback, log e nota sull'interfaccia
   essenziale; Open WebUI e skill restano 0.2.

**Test obbligatori:** matrice argomenti dei tre modi; apertura browser mockata; browser disabilitato;
e2e studio/vstudio col fake; profilo parziale e fallback.

**Verifiche manuali:** chat studio sui due OS; immagine vstudio via UI o API come attestato dallo
spike; stop pulito.

**Commit locale suggerito:**
`feat: aggiungi studio e vstudio con interfaccia integrata`

### Step 6A — Preparazione locale della release 0.1

**Obiettivo:** produrre un release candidate completo senza pubblicare nulla.

**Attività:**

1. Crea `install.sh` e `install.ps1` piccoli e idempotenti: verificano prerequisiti, installano una
   versione appuntata di uv con procedura ufficiale e poi il tool. Prima della pubblicazione, il test
   usa esplicitamente un artefatto RC locale trasferito con hash verificato oppure un commit Git
   esatto, come percorso distinto e mai come default. Il one-liner principale punta a PyPI solo
   quando il pacchetto esiste e non dichiara installabile una versione non pubblicata.
2. Implementa `uninstall`: anteprima e conferma per dati gestiti, stato e config; non tocca mai la
   cache Hugging Face; ricorda come rimuovere il tool con uv.
3. Completa README, CONTRIBUTING, anatomy di modo/profilo, benchmark manuale, troubleshooting,
   requisiti, sicurezza e roadmap 0.2.
4. CONTRIBUTING impone: una PR tocca contenuto oppure core, non entrambi; profili con numeri
   misurati sulla release lock; approvazione personale del manutentore; branch protection.
5. Crea workflow release separato, least privilege, ambiente GitHub `pypi`, Trusted Publishing OIDC,
   actions a SHA completo e artefatti build/testati prima del job di pubblicazione.
6. Porta la versione a `0.1.0rc1`, aggiorna changelog e costruisce gli artefatti localmente.
7. Nessun tag, push, progetto PyPI, Trusted Publisher o upload viene creato dall'agente senza comando
   umano esplicito.

**Test obbligatori:** installer in ambienti temporanei dove possibile; uninstall confinato; build
wheel+sdist; installazione isolata; suite completa; ispezione contenuto artefatti.

**Commit locale suggerito:**
`chore: prepara release candidate 0.1.0`

### Human Gate 0.1

Tommaso esegue e approva esplicitamente, usando l'artefatto RC locale trasferito con hash verificato
finché la versione non esiste su PyPI:

- Ubuntu 22.04 pulito: installer, `--version`, `doctor`, `validate`, installazione motore compatibile;
- Windows Sandbox: stesso percorso;
- test reali dei tre modi;
- verifica dati, licenza, nomi progetto e account;
- creazione/configurazione ambiente GitHub `pypi` con approvatore;
- configurazione Trusted Publisher PyPI legata a repository, workflow e ambiente corretti;
- decisione `RELEASE` o `NO-RELEASE`.

### Step 6B — Finalizzazione locale della release 0.1

**Precondizione:** Human Gate `RELEASE` esplicito.

**Attività autorizzate all'agente:** versione `0.1.0`, changelog finale, documentazione senza riferimenti
RC, suite e build finali, commit locale.

**Non autorizzato implicitamente:** push, tag `v0.1.0`, release GitHub, upload PyPI, modifica
impostazioni remote. Tommaso esegue queste operazioni oppure le autorizza singolarmente nella
sessione corrente.

**Verifica post-pubblicazione umana:** one-liner da PyPI su Ubuntu e Windows, `--version`, `doctor`,
`validate`, metadati e hash artefatti.

**Commit locale suggerito:** `chore: finalize release 0.1.0`

---

## 8. Piano di implementazione — Milestone 0.2

La 0.2 parte soltanto dopo stabilizzazione della 0.1. Restano validi tutti i contratti precedenti.

### Step 7 — Skill e router deterministico a frasi

**Obiettivo:** contenuti instradabili senza regex o codice contribuito.

**Contratto `skill/v1`:** file Markdown con frontmatter YAML letto con `yaml.safe_load`; nome uguale al
file; descrizione; `routing.phrases` come coppie `[frase, peso]`; almeno tre `examples`; almeno un
`negative_example`; `co_activate` lista, anche vuota; body Markdown come contenuto della skill.

**Normalizzazione esatta:** tronca l'input a 20.000 caratteri; Unicode NFKD; rimuove caratteri
combining; `casefold()`; sostituisce ogni sequenza non alfanumerica con uno spazio; comprime spazi e
trim. Una frase normalizzata è una sequenza contigua di token e contribuisce al massimo una volta.

**Routing:** somma pesi; applica threshold; ordina score decrescente e poi nome alfabetico; `top_k`
limita le selezioni dirette; le co-attivazioni valide vengono aggiunte dopo, senza duplicati e senza
ricorsione, e possono superare `top_k`. Un esempio positivo deve avere la propria skill al primo
posto; un negativo non deve contenerla.

**Attività:**

1. porta la versione a `0.2.0.dev0`;
2. aggiungi `pyyaml` e aggiorna lock;
3. crea schema, parser sicuro e skill iniziali `epsilon-delta`, `math-solver`, `debug-systematic`,
   `linux-ops`;
4. implementa router puro e test comportamentali integrati in `validate`;
5. crea `mode/v2` con `prompt` e `skills` (`auto` o lista), mantenendo lettura v1; migra i modi del
   repository;
6. vieta regex in schema, parser e documentazione.

**Test obbligatori:** normalizzazione accenti/case/punteggiatura; phrase una volta; pareggi; threshold;
top_k e co-attivazioni; riferimenti mancanti; esempi positivi/negativi; frontmatter ostile non
eseguito; compatibilità mode v1/v2.

**Commit locale suggerito:**
`feat(0.2): aggiungi skill e router deterministico a frasi`

### Step 8 — Open WebUI gestita e `sync`

**Obiettivo:** esperienza web completa, isolata e riproducibile, con ripiego onesto.

**Precondizione umana:** Tommaso approva una versione precisa di Open WebUI dopo uno spike che verifica
Python supportato, dipendenze CPU-only, comando, salute, Functions, prompt e comportamento delle
variabili d'ambiente. Lo spike genera `resources/open-webui.lock`.

**Installazione:** ogni venv vive in una directory immutabile sotto
`data_dir()/open-webui/installations/`; lo staging temporaneo è sullo stesso filesystem. Versione,
import ed eseguibile sono verificati prima della promozione; `installed.json` resta dentro
l'installazione. `data_dir()/open-webui/current.json` viene sostituito atomicamente e seleziona
l'ambiente attivo tramite un percorso relativo verificato come discendente di `installations/`.
Installazione parziale o lock cambiato → ricostruzione completa in una nuova
directory; manifest e versione precedenti restano intatti fino al successo. La pulizia riguarda
soltanto ambienti gestiti non attivi.

**Config 0.2:** aggiunge `webui_port=8081` e `QWEN_LAUNCHER_WEBUI_PORT`, validati 1–65535; la porta
deve essere diversa da `llama_port`.

**Ambiente minimo, confermato sul lock:** data dir dedicata; host `127.0.0.1`;
`ENABLE_PERSISTENT_CONFIG=False`; autenticazione disabilitata solo per servizio locale e data dir
gestita; API Ollama disabilitata; endpoint OpenAI locale e chiave segnaposto. L'utente viene avvisato
che modifiche effettuate nelle impostazioni UI non persistono al riavvio quando la configurazione
persistente è disabilitata.

**Fallimento:** se llama-server è pronto ma Open WebUI fallisce, llama-server resta attivo, viene
mostrato il log WebUI, si apre automaticamente la UI integrata se consentito e disponibile, e il
comando continua in foreground con warning. Se nessuna UI è disponibile per un modo che la richiede,
il launcher ferma i servizi avviati e termina 1.

**Sync:** genera in `data_dir()/sync-out/` function e prompt più istruzioni d'importazione. Il template
Python è statico; regole e contenuti sono serializzati come JSON dati, mai interpolati come codice.
Nessuna scrittura API finché non è verificata e autorizzata in una versione futura.

**Test obbligatori:** installazione valida/parziale/aggiornata/fallita; promozione e manifest
interrotto/corrotto; config porte; ambiente; salute; fallback UI; stato multi-servizio; template
resistente a contenuto ostile; output sync riproducibile.

**Commit locale suggerito:**
`feat(0.2): aggiungi Open WebUI gestita e sync locale`

### Step 9 — Benchmark per modo e chiusura del ciclo

**Obiettivo:** produrre misure riproducibili e frammenti di profilo senza fingere di conoscere i
confini di un tier hardware.

`benchmark --mode <id>` richiede un server vivo e legge dallo stato modo, modello, release, profilo,
ctx e `n_cpu_moe`.

Protocollo `benchmark/v1`, identico a quello normativo dello Step 0:

- copia byte per byte nelle risorse prompt e template richiesta dello spike e ne verifica gli
  SHA-256 registrati;
- richiede ed esige 256 completion token per misura con il meccanismo già verificato nello spike;
- esclude un warm-up completo;
- raccoglie cinque misurazioni valide;
- richiede nessun client concorrente;
- ottiene tok/s dalle metriche della release se lo spike ne ha dimostrato l'affidabilità, altrimenti
  usa il medesimo conteggio token/tempo documentato nello spike;
- stampa singole misure, minimo, mediana e massimo; la media è facoltativa e non sostituisce la
  mediana;
- registra OS, hardware, modello, motore, modo e parametri.

Il comando stampa:

1. un frammento conforme per il solo modo misurato;
2. una bozza di profilo esplicitamente **non ancora validabile**, con intervalli `match` da completare
   a mano.

Non crea buste vuote dichiarandole conformi e non inventa i confini del tier.

Completa inoltre:

- `doctor` con stato ✅/⚠️/❌ e rimedio per ogni riga non verde;
- `docs/benchmarks.md`;
- template PR profilo con benchmark per ogni modo dichiarato;
- template PR skill con esempi positivi/negativi e suite verde.

**Test obbligatori:** server assente o stato incompatibile; warm-up escluso; cinque misure; mediana;
frammento conforme; bozza marcata non validabile; nessuna rete reale; metodo metriche/fallback;
metadata dallo stato.

**Commit locale suggerito:**
`feat(0.2): aggiungi benchmark riproducibile e doctor definitivo`

### Step 10A — Preparazione locale della release 0.2

**Obiettivo:** produrre un release candidate 0.2 completo senza pubblicare nulla.

**Attività:** completa documentazione e changelog 0.2; verifica upgrade da 0.1 e installazione pulita;
porta la versione a `0.2.0rc1`; esegue suite, build wheel+sdist, installazione isolata e ispezione
degli artefatti. Il workflow di release già introdotto viene verificato ma non eseguito. Nessun tag,
push, progetto remoto o upload è autorizzato implicitamente.

**Commit locale suggerito:** `chore(0.2): prepara release candidate 0.2.0`

### Human Gate 0.2

Tommaso prova e approva esplicitamente su Ubuntu e Windows: installazione pulita e upgrade dalla 0.1;
tre modi; router ed esempi skill; installazione e fallback Open WebUI; sync; benchmark; doctor;
validate; dati, licenze, nomi, artefatti e configurazione Trusted Publisher. Decide `RELEASE` o
`NO-RELEASE`.

### Step 10B — Finalizzazione locale della release 0.2

**Precondizione:** Human Gate 0.2 `RELEASE` esplicito.

**Attività autorizzate all'agente:** versione `0.2.0`, changelog finale, documentazione senza
riferimenti RC, suite e build finali, commit locale.

**Non autorizzato implicitamente:** push, tag `v0.2.0`, release GitHub, upload PyPI o modifiche remote.
Tommaso le esegue oppure le autorizza singolarmente nella sessione corrente.

**Verifica post-pubblicazione umana:** installazione e upgrade da PyPI sui due OS, `--version`,
`doctor`, `validate`, modi principali, metadati e hash artefatti.

**Commit locale suggerito:** `chore(0.2): finalize release 0.2.0`

---

## 9. Matrice finale di accettazione

### Milestone 0.1

- [ ] Spike `GO`, artefatto umano e JSON coerenti.
- [ ] Release motore, commit, versione, contratto semantico dei flag, API e salute appuntati.
- [ ] Python e dipendenze riproducibili; `uv.lock` committato.
- [ ] Wheel contiene tutte le risorse ed è provata isolatamente su Linux e Windows.
- [ ] Config severa, senza side effect o modifiche automatiche.
- [ ] Schemi e controlli semantici verdi.
- [ ] Profili legati a modello, release, OS e modo.
- [ ] RAM disponibile considerata; `--force` confinato.
- [ ] GPU scelta e realmente isolata oppure multi-GPU CUDA bloccato.
- [ ] Builder CPU/CUDA distinto; tutti i flag coperti dal lock.
- [ ] UI e vision applicate esplicitamente.
- [ ] Lifecycle, lock, stato corrotto, log, timeout e PID riusato coperti da test.
- [ ] Installazione motore sicura e attivazione atomica via manifest, con checksum e anti path traversal.
- [ ] `coding`, `studio`, `vstudio`, `stop`, `status`, `doctor`, `validate` verificati.
- [ ] Installer provati in Ubuntu pulito e Windows Sandbox.
- [ ] Release autorizzata tramite cancello umano; nessuna pubblicazione implicita.

### Milestone 0.2

- [ ] Router senza regex, normalizzazione e spareggi deterministici.
- [ ] Ogni skill porta test positivi e negativi.
- [ ] Open WebUI e dipendenze appuntate, attivazione atomica via manifest e fallback verificato.
- [ ] Utente informato che le impostazioni UI non persistono con config non persistente.
- [ ] Sync produce dati/artefatti locali senza eseguire contenuti contribuiti.
- [ ] Benchmark automatizza lo stesso `benchmark/v1` dello spike e produce un frammento realmente
  conforme.
- [ ] Versione 0.2 finalizzata soltanto dopo Human Gate; nessuna pubblicazione implicita.

---

## 10. Riferimenti ufficiali di processo

Questi riferimenti aiutano packaging e sicurezza, ma non prevalgono sui lock di versione del
progetto:

- Python 3.12, `importlib.resources`:
  <https://docs.python.org/3.12/library/importlib.resources.html>
- CPython 3.12.13: <https://www.python.org/downloads/release/python-31213/>
- uv 0.11.28: <https://github.com/astral-sh/uv/releases/tag/0.11.28>
- uv build backend: <https://docs.astral.sh/uv/concepts/build-backend/>
- uv in GitHub Actions: <https://docs.astral.sh/uv/guides/integration/github/>
- setup-uv ufficiale: <https://github.com/astral-sh/setup-uv>
- sicurezza delle GitHub Actions e pin a SHA:
  <https://docs.github.com/en/actions/reference/security/secure-use>
- PyPI Trusted Publishing: <https://docs.pypi.org/trusted-publishers/>
- sicurezza Trusted Publisher: <https://docs.pypi.org/trusted-publishers/security-model/>
- Open WebUI, variabili d'ambiente:
  <https://docs.openwebui.com/reference/env-configuration/>

Per `llama.cpp` si usa la documentazione e l'help della release scelta nello Step 0, non un link
mobile al ramo corrente.

---

## 11. Regola di chiusura

Lo step è concluso soltanto quando codice, test, documentazione e verifiche previste concordano. Un
risultato «funzionante sulla macchina dell'esecutore» non sostituisce la wheel installata, la matrice
CI o i collaudi manuali dichiarati. Un dubbio rilevante viene reso visibile; non diventa una scelta
silenziosa nel codice.
