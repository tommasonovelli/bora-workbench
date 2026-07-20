# qwen-launcher — Specifica centrale di implementazione (v4.7)

## 0. Tracker di avanzamento — aggiornato al 20 luglio 2026

> Questo blocco registra lo stato reale del repository. Questo è il documento normativo
> `IMPLEMENTATION_SPEC.md` alla radice, unica copia normativa nel repository come previsto dallo
> Step 1. Gli output grezzi verificati dello spike sono conservati sotto `docs/spike-0/`. `[x]`
> significa completato e verificato; `[~]` parziale; `[ ]` ancora da eseguire. Una voce parziale
> **non** soddisfa il gate dello step salvo una decisione normativa esplicita che la riclassifichi
> come follow-up non bloccante, come D-047.

### Stato sintetico

- [x] **Step 0 — Spike tecnico:** `llama.cpp b10011`, commit
  `bf2c86ddc0685f580595954056c2e77ebabfab4f`, ha completato la matrice Ubuntu 24.04 e Windows 11
  CPU/CUDA dei tre modi. Salute, API, metriche, UI esplicita, vision, MTP, sampling, stop/log e
  `benchmark/v1` con warm-up più cinque misure sono verificati. La coppia Windows CUDA 13.3 e i
  termini MIT/NVIDIA sono registrati. `docs/spike-0.md/json` dichiarano `GO`.
- [x] **Step 1 — Scaffold:** implementazione completa, incluso `engine.lock`; commit pubblicati,
  matrice CI GitHub verde su Ubuntu/Windows e branch protection attiva con CI e revisione code owner
  obbligatorie per i contributori.
- [x] **Step 2A — Contratti dichiarativi e modi.**
- [x] **Step 2B — Validazione, modelli runtime e hardware.**
- [x] **Step 2C — Contratto artefatto modello.**
- [x] **Step 3 — Vertical slice `coding`, stato, stop e status.**
- [x] **Step 4 — Asset lock e attivazione atomica del motore.**
- [x] **Step 5 — `studio` e `vstudio`:** implementazione, collaudi reali Ubuntu/Windows e matrice CI
  multipiattaforma conclusi.
- [x] **Step 5A — Calibrazione assistita:** `calibration/v1`, bundle, Q8, dominio degli assi e
  `calibration/v2` sono storicamente completati. Il successore `calibration/v3` (D-041–D-046) è
  implementato con conferma ABBA, riserva RAM, telemetria, record `calibration-record/v2`, lifecycle
  candidato/attivo, identità WDDM a scope di run, evidenza locale, 314 test offline e matrici CI
  Ubuntu/Windows verdi. Il Gate v3 locale Windows CUDA del 19 luglio ha prodotto tre candidati validi
  e inattivi.
- [x] **Calibration Gate locale — autorizzazione Step 5B:** il run v2 del 18 luglio resta
  `CALIBRATION-REJECTED` per il protocollo. Il run v3 pulito del 19 luglio è
  `CALIBRATION-ACCEPTED` per Windows 11/CUDA nei modi coding, studio e vstudio. Il Gate empirico
  complessivo resta `GATE-PARTIAL` perché manca hardware eterogeneo, ma D-047 accetta esplicitamente
  questa copertura come sufficiente per procedere; la prova eterogenea è un follow-up futuro non
  bloccante e nessun candidato è stato attivato.
- [x] **Step 5B — Policy di ricerca approvata, evidenza e flusso pubblico:** contratti pubblici v2,
  policy del metodo v3, report Windows privacy-safe, digest, seed di solo ordine, guida e verifica
  wheel completati. Nessun profilo finale è distribuito e la copertura resta `GATE-PARTIAL`.
- [x] **Step 6A — Preparazione locale release 0.1:** RC `0.1.0rc1`, installer espliciti,
  disinstallazione confinata, documentazione, workflow OIDC e artefatti locali completati senza
  pubblicazione. La correzione pre-Gate D-049 porta a 22 GiB il gate RAM disponibile su tutti i
  target, mantenendo 28 GiB totali e la riserva dinamica v3 di 2 GiB. D-050 aggiunge `98304` ai soli
  target contesto esperti senza cambiare la scala automatica o invalidare i record v2 esistenti.
- [ ] **Human Gate 0.1 — Collaudi puliti e decisione `RELEASE`/`NO-RELEASE`.**
- [ ] **Step 6B — Finalizzazione locale release 0.1:** bloccato fino a `RELEASE` esplicito.
- [ ] **Step 7 — Skill e router.**
- [ ] **Step 8 — Open WebUI e sync.**
- [ ] **Step 9 — Benchmark autonomo e doctor definitivo.**
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
- [x] Evidenza sotto `docs/spike-0/` coperta dai manifest SHA-256 verificati.
- [x] Decisione finale esplicita: `GO`, senza derivare profili o assetti da RAM, VRAM o tok/s. La
  busta `ctx=8192` e `n_cpu_moe=48` dimostra fattibilità, non ottimalità, e non è un profilo
  calibrato.

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
- [x] Matrice CI GitHub sul commit `db21e26`: lint, format, 41 test, build e wheel isolata verdi su
  Ubuntu 22.04 e Windows Server 2022.
- [x] Preparare il commit locale iniziale Conventional Commits.
- [x] Remote `origin` GitHub configurato.
- [x] Commit dello Step 1 pubblicato su `origin/main`.
- [x] Repository pubblico e branch protection attiva: CI Ubuntu/Windows e revisione code owner
  obbligatorie per i contributori; bypass amministratore mantenuto per l'unico maintainer.

### Step 2A — dettaglio

- [x] Schemi JSON Schema 2020-12 `mode/v1`, `profile/v1`, `calibration-policy/v1` e
  `calibration-report/v1` creati secondo i contratti della sezione 5.3.
- [x] Modi `coding`, `studio` e `vstudio` creati con servizi e sampling verificati nello Spike 0.
- [x] Nessun profilo, policy o report di produzione derivato impropriamente dalle misure di
  fattibilità dello spike.
- [x] Schemi e modi validati come JSON UTF-8 e verificati nella wheel e nella sdist.

### Step 2B — dettaglio

- [x] Dataclass gelate e loader per modi e profili; catalogo profili assente o vuoto valido.
- [x] Validazione schema e semantica di modi, profili, policy e report, inclusi riferimenti, digest,
  candidati, hardware, intervalli e compatibilità col lock.
- [x] Rilevamento CPU, RAM e NVIDIA con fallback CPU diagnosticato, selezione GPU deterministica e
  nessuna mutazione dell'ambiente padre.
- [x] Comandi `validate` e `doctor`, exit code contrattuali e diagnostica «nessun profilo calibrato».
- [x] Suite locale, build e `validate` dalla wheel isolata verdi.
- [x] Commit `e137916` pubblicato; matrice CI Ubuntu/Windows verde, incluso `validate` dalla sorgente
  e dalla wheel isolata.

### Step 2C — dettaglio

- [x] Separata l'identità dichiarativa `model` dal percorso locale opzionale `model_path`.
- [x] Copiati nel lock revisione, filename, dimensione e SHA-256 verificati di GGUF e mmproj.
- [x] Corretto il template macchina da `{model}` a `{model_path}` senza aggiungere flag.
- [x] Validati artefatti, placeholder e copertura completa tramite `verified_flags`.
- [x] Suite locale, build e `validate` dalla wheel isolata verdi.
- [x] Commit `1b89a27` e `5cdfec2` pubblicati; matrice CI Ubuntu/Windows verde, inclusi
  `validate`, build e verifica wheel isolata.

### Step 3 — dettaglio

- [x] Matching v1, gate RAM, fallback non ottimizzato e blocco CUDA multi-GPU implementati; D-034
  ha poi riclassificato il matching condiviso come seed e ne ha vietato l'uso diretto nel piano.
- [x] Risoluzione read-only del modello, verifica artefatti, locate e builder lock-only implementati.
- [x] Lifecycle `coding`, salute, log, stato atomico, lock d'avvio, `status` e `stop` coperti da test
  offline col server fake.
- [x] Sync frozen, lint, format, 137 test, `validate`, build e verifica wheel isolata verdi su Ubuntu
  con uv 0.11.28 e CPython 3.12.13.
- [x] Collaudo reale Ubuntu CUDA col motore b10011 ricostruito dall'archivio del commit e checksum
  dello spike: modello appuntato verificato, baseline `ctx=8192`/`n_cpu_moe=48`, UI e vision off
  esplicite, salute, `/v1/models`, chat con MTP, GPU 0, stato e stop pulito verificati.
- [x] Collaudo reale Windows 11 CUDA con la coppia b10011 CUDA 13.3 verificata dai digest del lock:
  un solo server e stato baseline esatto; salute 200, modello con `n_ctx=8192`, UI 404 e chat valida
  con 5 completion token e MTP `draft_n=4`/`draft_n_accepted=4`; PID sulla GPU 0 e ambiente padre
  invariato; stop 0 idempotente, stato vuoto, porta/PID/GPU puliti e log completo.
- [x] Matrice CI GitHub Ubuntu 22.04/Windows Server 2022 verde sul commit `7689e83` (run
  `29487698370`), inclusi test, `validate`, build e verifica wheel isolata.

### Step 4 — dettaglio

- [x] Matrice asset reale dello spike completata nel lock e `assets_complete=true`; avvisi MIT e
  NVIDIA verificati inclusi nelle risorse installabili.
- [x] Download HTTPS in streaming `.part`, SHA-256 obbligatorio, estrazione confinata, staging,
  promozione immutabile e attivazione atomica tramite `current.json` implementati.
- [x] Prebuilt Ubuntu CPU e Windows CPU/CUDA selezionati per coppia esatta; build Ubuntu CUDA dal
  commit appuntato con prerequisiti espliciti e solo target `llama-server`.
- [x] Comandi `engine install [--force]` ed `engine status`, diagnostica doctor e procedura
  `docs/engine-lock.md` implementati con test offline.
- [x] Sync frozen, lint, format, 168 test, `validate`, build e verifica wheel isolata verdi su
  Ubuntu con uv 0.11.28 e CPython 3.12.13.
- [x] Matrice CI GitHub Ubuntu 22.04/Windows Server 2022 verde sul commit `f7c463b` (run
  `29494925651`), inclusi 168 test, `validate`, build e verifica wheel isolata.
- [x] Installazioni reali Ubuntu CUDA dal sorgente e Ubuntu CPU dal prebuilt con digest del lock;
  `engine status`, `coding`, salute 200, modelli, chat da 5 token con MTP, Ctrl-C 130 e pulizia di
  stato, porta, processo e GPU verificati. Il percorso CPU è stato isolato rimuovendo soltanto
  `nvidia-smi` dal `PATH` del processo di collaudo.
- [x] Installazioni reali Windows 11 CUDA 13.3 e CPU verificate dai tre archivi con digest del lock,
  avvisi richiesti e manifest atomico. Entrambi i backend hanno avviato `coding` con baseline
  esatta, salute e modelli 200, UI 404, chat da 5 token con MTP e pulizia completa di stato, porta e
  processo; CUDA ha usato il PID sulla GPU 0 senza mutare l'ambiente padre, mentre il prebuilt CPU
  non ha elencato dispositivi CUDA. Un primo probe a freddo CUDA è scaduto dopo 10 secondi ed è stato
  ripulito senza attivazione parziale; il retry, il cambio backend e la riattivazione sono riusciti.

### Step 5 — dettaglio

- [x] Comandi `studio` e `vstudio` implementati riusando il lifecycle esistente e soltanto i
  contratti UI/vision, sampling e mmproj appuntati nel lock.
- [x] URL UI/API, profilo o baseline, log e natura essenziale dell'interfaccia integrata mostrati;
  apertura browser eseguita solo dopo READY e solo con `open_browser=true`.
- [x] Matrice argomenti CPU/CUDA dei tre modi, browser abilitato/disabilitato, fallback da profilo
  parziale ed end-to-end col server fake coperti da test offline.
- [x] Sync frozen, lint, format, 180 test, `validate`, build e verifica wheel isolata verdi su Ubuntu
  con uv 0.11.28 e CPython 3.12.13.
- [x] Collaudo reale Ubuntu 24.04 CUDA: `studio` con UI, modelli e chat 200; `vstudio` con UI, modelli
  e vision 200 tramite mmproj, risposta `Rosso`; entrambi con baseline dichiarata, Ctrl-C 130 e
  pulizia completa di stato, processo e GPU.
- [x] Collaudo reale Windows 11 build 10.0.26200 CUDA col motore gestito b10011: `studio` con UI,
  modelli e chat 200, risposta esatta `OK STUDIO WINDOWS`; `vstudio` con UI, modelli e vision 200
  tramite mmproj verificato, risposta `Rosso`; MTP attivo, PID sulla GPU 0, ambiente padre invariato
  e stop con pulizia completa di stato, porta, processo e GPU.
- [x] Matrice CI GitHub Ubuntu 22.04/Windows Server 2022 verde sul commit `18dfe87` (run
  `29500119988`), inclusi 180 test, `validate`, build e verifica wheel isolata.

### Step 5A — dettaglio

- [x] Risorse `benchmark/v1` copiate byte per byte dallo spike e verificate tramite SHA-256; un
  warm-up escluso, cinque misure esatte, token, `finish_reason` e timing ricontrollati offline.
- [x] `calibrate --mode <id|all>` richiede candidati, contesti, avvii e riserva espliciti senza policy;
  mostra preflight e rischio e richiede conferma prima di avviare prove.
- [x] Processi freschi e stato isolato per candidato, carichi coding/studio/vstudio, polling VRAM
  complessivo a 250 ms, scarti e selezione deterministica implementati con test senza GPU o rete.
- [x] Bundle draft atomico con report, benchmark, proposta non distribuibile, log redatti, manifest,
  anteprima e `validate --path` implementato; nessuna policy o profilo reale aggiunto.
- [x] Sync frozen, lint, format, 210 test, `validate`, build e verifica wheel isolata verdi su Ubuntu
  con uv 0.11.28 e CPython 3.12.13.
- [x] Matrice CI GitHub Ubuntu 22.04/Windows Server 2022 verde sul commit `eb0f13c` (run
  `29505535712`), inclusi 210 test, `validate`, build e verifica wheel isolata. Il primo run ha
  rilevato correttamente la conversione CRLF dei protocolli su Windows; `.gitattributes` ora ne
  preserva i byte e i digest appuntati su entrambi gli OS.
- [x] Correzione dal primo run reale: rilascio VRAM ricampionato fino a 10 s con tolleranza
  esplicita; deriva fra avvii oltre tolleranza trasformata in scarto del candidato; campione finale
  registrato; report e fallback redatti; scanner privacy e riepilogo «tutti scartati» coperti da
  test offline e dalla matrice CI Ubuntu/Windows conclusiva dello Step 5A.
- [x] Mini-spike Ubuntu b10011: cache K/V Q8 con mmap GO su coding/studio/vstudio CUDA e smoke CPU;
  no-mmap NO-GO per caricamento, RAM, throughput e rilascio. Evidenza sotto
  `docs/mini-spike-kv-q8-ubuntu/`; nessuna promessa qualitativa deriva da `benchmark/v1`.
- [x] Audit portabilità core: il launcher vieta confronti fra contesti, candidati equivalenti o
  fuori ordine; `validate` ricostruisce riserva, rilascio, classe d'origine e selezione; i profili v1
  condivisi non entrano direttamente nel `LaunchPlan`. Il v2 ha completato monitoraggio RAM e ricerca
  versionata ma il suo Gate è respinto; il v3 e il Gate locale chiudono lo Step 5A. La prova empirica
  su hardware eterogeneo resta follow-up futuro non bloccante per D-047.
- [x] Smoke Windows 11 CUDA 13.3 b10011 con Q8+mmap (17 luglio 2026): GO su coding (48 e 38),
  studio (38) e vstudio (48 e 38) a ctx 131072 con benchmark/v1, MTP, UI, vision `Rosso`, stop e
  rilascio entro tolleranza; compatibilità CPU a ctx 8192. Cache Q8 adottata nel ramo CUDA del lock
  in modifica dichiarativa separata (D-033). Evidenza sotto `docs/mini-spike-kv-q8-windows/`; le
  misure Windows registrano onestamente il carico ambientale del desktop e la loro dispersione.
- [x] Dominio `n_cpu_moe` verificato sul modello appuntato: metadati GGUF (`block_count=41`,
  `expert_count=256`) più probe 48/49/41/40; dominio legale `[0, 41]`, valori superiori alias del
  massimo. Tre dei sette candidati storici (48, 44, 42) erano la stessa configurazione.
- [x] Progettazione `calibration/v2` registrata e approvata: D-038/D-039 e
  `docs/calibration-v2-design.md` (screening adattivo, finalisti, criterio di dominanza dal rumore
  misurato, record locale `calibration-record/v1`, invalidazione, headroom, seed come solo
  ordinamento).
- [x] Protocollo `calibration/v2` implementato (18 luglio 2026, CALIBRATE.md sezione 7, punti
  4–5): dominio predetto dai metadati GGUF del modello appuntato, screening adattivo per bisezione
  con verifica misurata della monotonia VRAM e degradazione lineare onesta, monitoraggio RAM a
  250 ms per tutti i backend, conferma dei finalisti con 2 avvii stabili, deriva limitata e
  `benchmark/v1`, selezione robusta per dominanza, scala contesti 131072→8192, conferma onesta
  della baseline CPU e seed condivisi come solo ordinamento dei probe. Il record locale
  `calibration-record/v1` (schema versionato nella wheel, record nella directory dati) è scritto
  atomicamente, rivalidato a ogni caricamento con ricostruzione della selezione e riusato dai
  lanci solo con identità coincidente (modello/digest, release/commit/contratto motore, OS,
  backend, hardware stabile, driver) e headroom misurato; ogni divergenza ripiega sulla baseline
  con diagnostica azionabile. `doctor` distingue record valido, assente, invalido, obsoleto e
  headroom insufficiente; `calibrate` esegue v2 a zero input e `--protocol v1` conserva il
  laboratorio esplicito. Verifica locale Linux iniziale: Ruff, 279 test offline deterministici,
  `validate`, build e wheel isolata verdi (CPython 3.12.3 di sistema: il download del 3.12.13
  appuntato era bloccato dal proxy). Revisione locale Windows con uv 0.11.28 e CPython 3.12.13:
  sync frozen, Ruff, 288 test, `validate`, build e wheel isolata verdi; la revisione ha inoltre reso
  conservativi i fabbisogni fra avvii, impedito selezioni dopo esaurimento del tetto, classificato i
  guasti monitor come invalidazione e legato contesto/headroom del record all'evidenza dei
  finalisti. Matrice CI GitHub Ubuntu 22.04/Windows Server 2022 verde sul commit `689c1d1` (run
  `29647535746`), inclusi 288 test, `validate`, build e verifica wheel isolata.
- [x] Primo Gate v2 eseguito sul modo `coding` il 18 luglio 2026: il record è formalmente coerente,
  ma il protocollo è `CALIBRATION-REJECTED` perché le finestre disgiunte, il benchmark su un solo
  avvio e la regola mediana-contro-massimo non separano candidato e deriva ambientale.
- [x] `calibration/v3` progettato e implementato (D-041–D-046, `docs/calibrate_v3.md`): round ABBA
  con benchmark completo su ogni avvio, dominanza per unanimità, deriva come degradazione onesta,
  riserva RAM 2,0 GiB, monotonia sui soli probe fattibili, split interpolato solo come ordinamento,
  telemetria GPU evidence-only, identità eseguibile WDDM a scope di run, `calibration-record/v2`
  per-avvio, log dell'ultimo run e lifecycle candidato→attivo→previous con
  `--no-activate`/`--activate`; `--target-ctx` resta facoltativo.
  I record v1 sono diagnosticati come superati e non guidano i lanci. Verifica locale Windows con
  uv 0.11.28 e CPython 3.12.13: sync frozen, Ruff, 314 test offline, `validate`, build e wheel
  isolata verdi; la baseline D-046 ha risolto 20/20 identità WDDM senza serializzare percorsi.
  Le matrici CI Ubuntu/Windows sono verdi sui commit `6f69d77` (run `29684539755`) e `2d4cc22`
  (run `29684866498`). Il Gate v3 pulito Windows CUDA del 19 luglio ha completato
  `--mode all --no-activate` in 27 minuti e 3 secondi: coding `37`, studio `37`, vstudio `39`, tutti a
  `ctx=131072`, con tre candidati v2 validi e nessuna attivazione. Il report è
  `docs/calibration-gate-v3-windows.md`. D-047 rinvia la prova su hardware materialmente diverso a un
  follow-up futuro non bloccante e chiude lo Step 5A.

### Step 6A — dettaglio

- [x] `install.sh` e `install.ps1` richiedono una sorgente esplicita: wheel RC con SHA-256, commit Git
  completo o versione PyPI già esistente; appuntano uv `0.11.28` e CPython `3.12.13` senza
  elevazione, default remoto o claim su una versione non pubblicata.
- [x] `uninstall` mostra le quattro radici gestite, rifiuta servizi vivi e radici alterate o symlink,
  richiede conferma e non include mai la cache Hugging Face.
- [x] README, CONTRIBUTING, troubleshooting, release, benchmark e anatomia modo/profilo completati;
  la sdist li include insieme agli installer.
- [x] Workflow release separato con matrice Ubuntu/Windows, action a SHA completo, artefatto testato,
  ambiente `pypi`, least privilege e Trusted Publishing OIDC; nessuna configurazione remota eseguita.
- [x] Versione `0.1.0rc1`, lock e changelog aggiornati; 351 test offline, Ruff, `validate`, build e
  verifica isolata degli artefatti verdi localmente su Windows con CPython `3.12.13` e uv `0.11.28`.
- [x] Correzione pre-Gate D-049: un preflight reale Windows con browser aperto è stato bloccato a
  circa 23,7 GiB disponibili prima di qualsiasi trial. Il gate statico comune scende da 24 a 22 GiB;
  restano invariati il minimo totale di 28 GiB, il monitoraggio a 250 ms e la riserva dinamica v3 di
  2 GiB. La suite, `validate`, build e verifica wheel sono stati ripetuti sul RC corretto.
- [x] Estensione esperta D-050: `--target-ctx 98304` è ammesso separatamente dalla scala automatica,
  che resta `131072 → 65536 → 32768 → 16384 → 8192`. L'enum additivo del record v2 conserva la
  validità dell'evidenza precedente e `validate` impone che il target coincida con la busta misurata.

### Prossima azione obbligatoria

Step 6A è concluso localmente senza tag, upload, release o modifica remota. La prossima milestone è
lo Human Gate 0.1: Tommaso deve usare l'artefatto RC rigenerato dopo D-049, verificarne il nuovo hash
su Ubuntu 22.04 pulito e Windows Sandbox e decidere esplicitamente `RELEASE` o `NO-RELEASE`; gli hash
RC precedenti alla correzione non sono più applicabili. Step 6B resta bloccato fino a `RELEASE`. La
ripetizione `calibration/v3 --no-activate` su hardware materialmente diverso resta un follow-up
futuro non bloccante e la copertura empirica resta `GATE-PARTIAL`.

---

> **Stato:** documento normativo centrale, pronto a guidare l'implementazione per step.  
> **Data di consolidamento:** 20 luglio 2026; la v4.7 registra D-050 e il target contesto esperto
> `98304`, separato dalla scala automatica. La v4.6 registrava D-049 e la correzione pre-Gate della
> RAM disponibile da 24 a 22 GiB, senza indebolire il minimo totale o la riserva dinamica v3. La v4.5
> registrava la conclusione locale dello Step 6A e il passaggio allo Human Gate 0.1, senza
> pubblicazione. La v4.4 registrava D-048 e la conclusione dello Step 5B con policy/report v2,
> evidenza Windows privacy-safe e seed di solo ordine. La v4.3 registrava D-047, che accetta il Gate
> locale Windows CUDA e rinvia la prova hardware eterogenea a un follow-up non bloccante. La v4.2
> registrava CI verde e il Gate v3 locale accettato per i tre modi; la v4.1 registrava il Gate v2
> respinto e `calibration/v3` implementato (D-041–D-046, `docs/calibrate_v3.md`).  
> **Sostituisce:** la v4.6, la v4.5, la v4.4, la v4.3, la v4.2, la v4.1, la v3.4, la v3.1,
> `PIANO_IMPLEMENTAZIONE_v2.md`, le due revisioni
> successive e la v3 non corretta.  
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
- calibra e conserva localmente i parametri sulla macchina dell'utente;
- usa profili e report condivisi soltanto come seed o evidenza, mai come sostituti della misura locale;
- usa una release precisa e collaudata di `llama.cpp`;
- avvia e governa `llama-server`;
- espone tre modi (`coding`, `studio`, `vstudio`);
- guida l'utente nella calibrazione locale e può generare un contributo riproducibile separato;
- rende estendibili contenuti e profili senza rendere estendibile arbitrariamente il core;
- nella 0.2 aggiunge skill, router deterministico, Open WebUI gestita e sincronizzazione.

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
| 0.1 | pacchetto, config, risorse, schemi, hardware, calibrazione assistita, profili, CLI, processi, motore, tre modi, installer, documentazione, release | 0–6B |
| 0.2 | skill e router a frasi, Open WebUI gestita, sync, benchmark autonomo, doctor definitivo, release | 7–10B |

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

1. lock versionati, report di calibrazione accettati e artefatti strutturati dello spike
   (`engine.lock`, contenuti `calibration-report/v2`; `calibration-report/v1` resta storico; in 0.2
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
| D-006 | modi = comportamento; record locali = prestazioni misurate; profili condivisi = seed/evidenza | nessuna precedenza ambigua e nessun trasferimento implicito dell'optimum |
| D-007 | un profilo può coprire un sottoinsieme dei modi | aggiungere un modo non invalida tutti i profili |
| D-008 | una sola GPU; `CUDA_VISIBLE_DEVICES` è impostata solo nell'ambiente del figlio | rende reale e stabile la scelta della GPU; va verificato nello spike |
| D-009 | il ripiego rigido di memoria vale solo per il modello predefinito calibrato | non si applicano numeri ignoti a modelli diversi |
| D-010 | `coding` senza UI; `studio` e `vstudio` con UI, sempre tramite flag espliciti verificati | nessuna dipendenza dai default esterni |
| D-011 | router 0.2 a sole frasi normalizzate, senza regex | comportamento sicuro, deterministico e validabile |
| D-012 | release divisa in preparazione, cancello umano e finalizzazione | separa lavoro locale da operazioni remote |
| D-013 | tutte le azioni GitHub di terzi sono appuntate a SHA completo | riferimenti immutabili nei workflow |
| D-014 | `uv.lock` è committato e la CI usa `--frozen` | dipendenze riproducibili |
| D-015 | server legati solo a `127.0.0.1` | nessuna esposizione di rete implicita |
| D-016 | il protocollo manuale `benchmark/v1` nasce nello Step 0; lo Step 5A lo automatizza dentro `calibration/v1` e lo Step 9 espone il comando autonomo | confronta i candidati senza cambiare il benchmark e non scambia la fattibilità dello spike per ottimalità |
| D-017 | `engine.lock` contiene un contratto semantico macchina oltre alla lista dei flag | impedisce al builder di associare significati ai flag tramite assunzioni o hardcode non verificato |
| D-018 | le installazioni motore sono directory versionate; `current.json` è il puntatore sostituito atomicamente | evita di promettere una sostituzione atomica di directory non portabile su Windows |
| D-019 | sviluppo e CI usano CPython `3.12.13`, mantenendo il metadato pacchetto `>=3.12,<3.13` | usa la patch di sicurezza più recente disponibile tramite uv 0.11.28 su Linux e Windows x86-64 |
| D-020 | anche la 0.2 usa preparazione locale, cancello umano e finalizzazione | nessuna milestone pubblicabile resta senza procedura di release e autorizzazione esplicita |
| D-021 | percorsi OS e variabili ambiente pubbliche sono fissati prima dello scaffold | evita migrazioni successive di config, dati, cache e stato |
| D-022 | Open WebUI usa ambienti versionati e un manifest di attivazione atomico | applica anche al secondo servizio gestito la portabilità richiesta su Windows |
| D-023 | `main` richiede CI e revisione code owner per i contributori; il bypass amministratore resta attivo finché esiste un solo maintainer | evita di bloccare l'unico code owner sulle proprie modifiche senza indebolire il flusso dei contributori |
| D-024 | i comandi e benchmark dello Spike 0 provano fattibilità e compatibilità, non una busta ottimale | un singolo candidato funzionante non dimostra che usi al meglio RAM, VRAM o tok/s |
| D-025 | decisione storica superata da D-034–D-037: `calibration/v1` lega ancora report e profilo, ma non autorizza contenuto di produzione | conserva la provenienza del contratto senza promuovere il vecchio matching |
| D-026 | gli intervalli RAM/VRAM riconoscono classi nominali non interpolate e non sovrapposte, usabili soltanto per ordinare seed | evita nearest-match senza confondere capacità con optimum locale |
| D-027 | hardware sopra il gate ma senza record locale usa una baseline verificata con warning e può avviare volontariamente `calibrate` | mantiene il prodotto usabile e riduce l'attrito della calibrazione locale |
| D-028 | `calibrate` è locale, esplicito, riproducibile e non pubblica né modifica il repository | prove pesanti e possibili fallimenti restano sotto controllo dell'utente |
| D-029 | il primo uso guidato su 8 GiB VRAM e 32 GiB RAM è un caso locale del Gate, non la base sufficiente di una policy portabile | conserva evidenza reale senza trasformare un host nel dominio del prodotto |
| D-030 | identità `model` e percorso eseguibile `model_path` sono distinti; il modello predefinito si risolve in sola lettura alla revisione e ai digest appuntati | `llama-server -m` accetta un percorso, mentre `--hf-repo` risolve un branch mobile e può modificare la cache Hugging Face |
| D-031 | `calibration/v1` ricampiona il rilascio VRAM ogni 250 ms per massimo 10 s e usa una tolleranza GiB esplicita, applicata anche alla deriva fra avvii | rende operativo «vicino alla baseline» senza soglie hardware inventate; prima di policy/report accettati, i contratti v1 vengono corretti e le vecchie bozze locali devono essere rigenerate |
| D-032 | ogni bundle redige ricorsivamente i JSON e i log, usa riferimenti log relativi e passa uno scanner privacy automatico oltre alla revisione umana | impedisce che messaggi operativi correttamente dettagliati trasferiscano percorsi o identità nei file condivisibili |
| D-033 | il modello resta `UD-Q4_K_M`; cache KV Q8 e `--no-mmap` entrano nel lock soltanto dopo mini-spike GO su b10011 e in una modifica dichiarativa separata | distingue quantizzazione dei pesi e della cache e impedisce di appuntare prestazioni o compatibilità non misurate |
| D-034 | una busta ottima è un risultato locale; una classe RAM/VRAM e l'host di provenienza non autorizzano ad applicarla come calibrata a componenti diversi | capacità uguali non implicano lo stesso rapporto CPU/GPU, driver, pressione memoria o massimo prestazionale |
| D-035 | report e profili condivisi sono seed/evidenza; il runtime usa come calibrato soltanto un record locale compatibile con modello, contratto motore, modo, backend e hardware correnti | consente a ogni PC supportato di misurare il proprio optimum senza nearest-match o fingerprint distribuiti |
| D-036 | la policy pubblica governa un dominio di ricerca verificato e indipendente dalla macchina 32/8; ogni confronto mantiene fisso il contesto e misura localmente risorse e prestazioni | impedisce che una lista costruita attorno al confine della RTX 2060 SUPER diventi il dominio implicito del prodotto |
| D-037 | `calibration/v1` resta protocollo di laboratorio del Gate; prima della calibrazione pubblica 0.1 serve un protocollo successivo con screening, finalisti, monitoraggio RAM, record locale e invalidazione | estendere v1 silenziosamente o inventare limiti/criteri senza spike violerebbe versionamento ed evidenza |
| D-038 | decisione storica superata da D-041–D-046: `calibration/v2` introdusse ricerca adattiva locale, record v1 e riuso, ma la conferma misurava i finalisti in finestre disgiunte e usava mediana-contro-massimo | conserva la provenienza del primo protocollo local-first e del Gate respinto senza lasciarlo attivo (`docs/calibration-v2-design.md`) |
| D-039 | le costanti comuni del successore — riserva VRAM 0,5 GiB, tolleranza rilascio/deriva 0,125 GiB, 2 round, tetto 12 probe per modo, scala contesti 131072→8192 e riserva RAM 2,0 GiB — hanno provenienza dichiarata; il Gate Windows CUDA del 19 luglio le ha sostenute localmente e il Gate eterogeneo deve ancora provarne la portabilità. Il dominio deriva dai metadati verificati (`block_count=41`) | distingue costanti universali revisionabili al Gate da soglie per-macchina e àncora il dominio al modello reale |
| D-040 | su WDDM i PID già presenti nel campione iniziale di `--query-compute-apps` sono trattati come contesti grafici ambientali e inclusi nella baseline aggregata; un PID nuovo diverso dal processo gestito invalida il run, mentre fuori da WDDM qualunque PID iniziale resta bloccante | il driver Windows 610.47 riporta come compute anche i contesti inevitabili della shell; VRAM aggregata, riserva e stabilità conservano il carico ambientale reale |
| D-041 | il protocollo pubblico è `calibration/v3`: due round accoppiati A→B/B→A, `benchmark/v1` completo su ogni avvio e dominanza solo per unanimità delle mediane di sessione; la deriva oltre tolleranza disabilita la dominanza ma non scarta finalisti che rispettano le riserve assolute | equilibra la posizione temporale dei candidati, resiste ai burst senza soglie statistiche inventate e conserva un fallback prudente (`docs/calibrate_v3.md`) |
| D-042 | ogni trial v3 richiede almeno 2,0 GiB di RAM disponibile; una violazione rende il probe non fattibile o scarta il finalista, e il riuso richiede fabbisogno RAM misurato più la stessa riserva | impedisce di accettare buste vicine alla paginazione con semantica simmetrica alla riserva VRAM; il valore è sostenuto localmente ma la validazione eterogenea resta follow-up D-047 |
| D-043 | `calibration-record/v2` nasce come `<modo>.candidate.json`, viene promosso atomicamente per default ad attivo e conserva un solo `<modo>.previous.json`; `--no-activate` ferma la promozione e `--activate` la esegue senza nuove prove | un solo comando serve l'utente normale, mentre il Gate non rende operativo un risultato sperimentale; i record v1 sono superati e inerti senza migrazione automatica |
| D-044 | telemetria GPU (utilizzo, clock, temperatura, potenza, throttle driver) è best-effort ed evidence-only; valori o campi non supportati sono `null` e non invalidano un run | aiuta a spiegare regimi ambientali senza introdurre soglie termiche o prestazionali non misurate |
| D-045 | la monotonia VRAM usa soltanto probe fattibili; i picchi OOM troncati non la contraddicono. Dopo due picchi fattibili, l'interpolazione può ordinare il prossimo punto solo dentro la staffa e ripiega sul punto medio; non restringe mai il dominio | evita degradazioni lineari spurie e riduce il costo medio senza indebolire la prova misurata o il tetto di 12 probe |
| D-046 | `calibration/v3` raffina D-040 su WDDM con una baseline immutabile per l'intero run: ogni contesto usa l'istanza `pid + create_time` e un'identità opaca del file eseguibile (`st_dev + st_ino`); un respawn dello stesso file è ammesso entro la molteplicità iniziale e contato solo come evidenza, mentre file nuovi, identità illeggibili, molteplicità aggiuntiva e riciclo del PID gestito invalidano ancora il run. I gap fra trial non sono campionati, ma un contesto persistente viene confrontato con la baseline di run; nessun percorso o identificatore file entra nel record | due tentativi reali del Gate sono stati invalidati dal respawn di un contesto desktop già ammesso, mostrando che il PID era un proxy asimmetrico del lifecycle e non dell'attività compute; il file-id rende uniforme la popolazione ammessa senza soglie, allowlist per-processo o indebolimento di riserve, ABBA e telemetria |
| D-047 | il Gate Windows 11/CUDA accettato localmente per coding, studio e vstudio è sufficiente per chiudere Step 5A e iniziare Step 5B anche se la copertura empirica complessiva resta `GATE-PARTIAL`; la prova su hardware materialmente diverso è rinviata a un follow-up futuro non bloccante. Policy, report e documentazione devono dichiarare il perimetro misurato e non presentare le costanti come validate empiricamente su componenti diversi | il maintainer non dispone attualmente di hardware eterogeneo; bloccare indefinitamente il metodo local-first non aggiunge evidenza. Ogni utente misura comunque la propria busta, i seed non diventano `LaunchPlan`, le riserve restano conservative e il fallback rimane disponibile |
| D-048 | la policy pubblica di `calibration/v3` usa `calibration-policy/v2` e l'evidenza condivisa usa `calibration-report/v2`; il loader proietta da un report soltanto `n_cpu_moe` come suggerimento d'ordine per modello, motore, backend e modo esatti, senza esporre al piano contesto, hardware o busta osservata | i contratti v1 sono storici e il record v2 è privato; nuovi contratti espliciti impediscono di fingere v1 e rendono strutturale il divieto D-047 di trasferire l'optimum 32/8 |
| D-049 | il gate statico del modello predefinito richiede 28 GiB di RAM totale e 22 GiB disponibili su tutti i target supportati; il monitor v3 continua a imporre almeno 2 GiB disponibili durante ogni trial e il riuso conserva il fabbisogno misurato più la stessa riserva | il preflight reale Windows si è fermato a circa 23,7 GiB con un browser aperto prima di poter misurare, rendendo 24 GiB troppo restrittivi per un desktop idoneo. La soglia comune evita diramazioni OS non autorizzate e non sostituisce le protezioni dinamiche; la copertura eterogenea resta il follow-up D-047 |
| D-050 | `98304` è un target contesto esperto ammesso da `--target-ctx` e dal record `calibration-record/v2`, ma non entra nella scala automatica `131072 → 65536 → 32768 → 16384 → 8192`; il confronto resta a contesto fisso e il target serializzato deve coincidere con la busta misurata | consente al maintainer di misurare esplicitamente coding a 96 Ki token senza cambiare l'obiettivo contesto-prima, la policy pubblica, il report accettato o la validità dei record v2 precedenti; l'estensione degli enum è additiva e l'esito resta candidato inattivo finché non viene autorizzato separatamente |

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
| `profiles.py` | caricamento di seed condivisi, ripiego e costruzione `LaunchPlan`; nessun seed è calibrato localmente |
| `calibration.py` | ricerca locale, record compatibile, selezione e bundle di contribuzione; nessuna logica OS |
| `benchmark.py` | `benchmark/v1` puro e misure riproducibili riusate dalla calibrazione |
| `engine.py` | lock, ricerca, compatibilità, download/build, installazione sicura e attivazione atomica |
| `process.py` | processi, segnali, stato, lock d'avvio, salute, log, stop/status |
| `resources/__init__.py` | accesso a risorse di pacchetto tramite `importlib.resources` |
| `validation.py` | validazione schemi e controlli semantici incrociati |
| `routing.py` (0.2) | normalizzazione e scoring puro delle skill |
| `webui.py` (0.2) | lock, ambiente, installazione e processo Open WebUI |

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
│   ├── benchmark.py
│   ├── calibration.py
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
│       │   ├── calibration-policy.v1.json      # contratto storico di laboratorio
│       │   ├── calibration-policy.v2.json      # metodo pubblico calibration/v3
│       │   ├── calibration-report.v1.json      # evidenza storica di laboratorio
│       │   ├── calibration-report.v2.json      # evidenza v3 privacy-safe e seed di solo ordine
│       │   ├── mode.v1.json
│       │   ├── profile.v1.json                 # contratto storico; nessuna busta finale 0.1
│       │   └── calibration-record.v2.json      # record locale v3 con evidenza per avvio e lifecycle
│       └── content/
│           ├── calibration-policy.json
│           ├── calibrations/*.json
│           ├── modes/{coding,studio,vstudio}.json
│           └── profiles/*.json
├── docs/
│   ├── spike-0.md
│   ├── spike-0.json
│   ├── spike-0/                    # prompt benchmark e output grezzi verificati
│   ├── engine-lock.md
│   ├── benchmarks.md
│   ├── calibration.md
│   ├── calibrations/*/             # evidenza accettata e manifest dei seed condivisi
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

D-048 approva i successori pubblici v2 dopo lo spike e il Gate richiesti da D-037; ogni ulteriore
schema deve essere versionato esplicitamente e aggiornare questo albero nello stesso step che lo
approva. Il record locale vive nella directory dati gestita e non nelle risorse della wheel.

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
  un ambiente isolato. Nello Step 1 verifica import, lettura risorse e `--version`; dallo Step 2B
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
| `model_path` | `QWEN_LAUNCHER_MODEL_PATH` |
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` |

Configurazione 0.1:

| Chiave | Default | Vincolo |
|---|---|---|
| `model` | modello predefinito | identità stringa non vuota usata da profili e stato |
| `model_path` | `None` | percorso locale opzionale del GGUF; `~` espansa |
| `llama_port` | `8080` | intero 1–65535 |
| `engine_path` | `None` | percorso opzionale; `~` espansa |
| `open_browser` | `true` | booleano |

`webui_port` non esiste fino allo Step 8.

Regole:

- chiavi TOML sconosciute = input invalido;
- il file intero viene validato prima di creare `Config`;
- booleani ambiente ammessi, senza distinzione maiuscole/minuscole: `true/false`, `1/0`, `yes/no`,
  `on/off`;
- `QWEN_LAUNCHER_MODEL_PATH` e `QWEN_LAUNCHER_ENGINE_PATH` vuote = `None`;
- tutte le altre variabili presenti ma vuote o invalide = errore, non fallback;
- file assente = default; TOML malformato = errore chiaro su stderr senza traceback;
- il launcher non modifica mai automaticamente `config.toml`.

### 5.3 Schemi di contenuto e calibrazione

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

`profile/v1` descrive il contratto storico a classi implementato prima dell'audit D-034. Resta
validabile per fixture ed evidenza pre-Gate, ma non può diventare contenuto di produzione 0.1 né
essere presentato come calibrazione portabile. Possiede soltanto:

- `schema`, costante `profile/v1`;
- `id`, uguale al nome del file;
- `model`, identificatore completo del modello calibrato;
- `engine`, release esatta usata nella calibrazione;
- `measured_on`, descrizione non vuota della macchina;
- `calibration_protocol`, inizialmente costante `calibration/v1`;
- `calibration_report`, id del report accettato incluso nella wheel;
- `calibration_report_sha256`, digest SHA-256 dei byte UTF-8 esatti del report distribuito;
- `benchmark_protocol`, inizialmente costante `benchmark/v1`;
- `match.backend`, `cuda` o `cpu`;
- `match.vram_gib` e `match.ram_gib`, coppie `[min, max]`, con `min >= 0`, `max` numero o
  `null`, estremi inclusivi e controllo semantico `min <= max`;
- `match.os`, opzionale, almeno un valore unico fra `linux` e `windows`;
- `modes`, oggetto con almeno un modo; ogni busta contiene `ctx` intero `>= 1024`, `tok_s` opzionale
  `{min, median, max}` con numeri `>= 0` e controllo semantico `min <= median <= max`; `n_cpu_moe`
  è un intero `>= 0` obbligatorio per profili CUDA e vietato per profili CPU, tramite controllo
  semantico incrociato col backend.

`calibration-policy/v1` è il contratto esplicito del laboratorio Step 5A. Non è la policy pubblica
hardware-indipendente richiesta da D-036/D-037. Possiede soltanto:

- `schema`, costante `calibration-policy/v1`;
- `benchmark_protocol`, costante `benchmark/v1`;
- `gpu_poll_interval_ms`, costante `250`, e `gpu_release_stabilization_ms`, costante `10000`, per
  `calibration/v1`;
- `policies`, array non vuoto di policy con id unico. Ogni policy contiene `id`, `model`, `engine`,
  `backend`, lista `os`, `stable_start_runs`; `minimum_calibration_vram_gib`,
  `minimum_free_vram_gib` e `vram_release_tolerance_gib` sono obbligatori per CUDA e vietati per
  CPU; seguono `modes` e `hardware_classes`;
- ogni voce `modes.<id>` contiene una lista ordinata e non vuota `candidates`; ogni candidato ha id
  unico, `ctx` e `n_cpu_moe`, obbligatorio su CUDA e vietato su CPU;
- ogni classe contiene id unico e finestre inclusive `ram_gib` e `vram_gib` con le regole dei
  profili; classi della stessa policy non si sovrappongono.

`calibration-policy/v1` non riceve un file di produzione. Prima del Gate lo Step 5A usa gli stessi
campi come parametri espliciti e non inventa default mancanti; soltanto la policy del protocollo
successivo approvato occuperà `resources/content/calibration-policy.json`.

`calibration-report/v1` conserva l'evidenza del laboratorio e non autorizza da solo un record locale
o una busta trasferibile. Possiede soltanto:

- `schema`, costante `calibration-report/v1`; `id`, uguale al nome del file; `created_at` UTC;
  `decision`, uno fra `draft`, `accepted`, `rejected`; `launcher_version`; `model`; `engine`;
  `engine_source_commit`; `calibration_protocol`, costante `calibration/v1`; e
  `benchmark_protocol`, costante `benchmark/v1`;
- `policy`, con id o `null`, polling, finestra di stabilizzazione, avvii stabili, riserva VRAM,
  tolleranza di rilascio e lista ordinata dei candidati usati;
- `hardware`, con OS/versione, CPU, core, RAM totale/disponibile, backend, GPU indice/nome/driver e
  VRAM totale/libera; i campi GPU sono `null` su CPU e non esistono hostname, username o percorsi;
- `hardware_class`, id approvato o `null` per una classe nuova ancora proposta;
- `modes`, oggetto non vuoto; ogni modo contiene `candidates` e `selected_candidate_id`, che è `null`
  finché il modo non viene accettato;
- ogni risultato candidato ripete id, `ctx` ed eventuale `n_cpu_moe`, registra `outcome`, motivo di
  scarto opzionale, avvii riusciti, baseline/picco/minimo libero/campione finale VRAM nullable su CPU, warm-up,
  esattamente cinque misure valide, `{min, median, max}` e digest dei log relativi;
- `selection_rule`, costante della regola in sezione 5.6; `privacy_reviewed`, booleano che deve essere
  `true` per `decision=accepted`; e `evidence_manifest`, percorso relativo del manifest del bundle.

Condizionali JSON Schema e controlli semantici vietano misure o selezioni fittizie nei candidati
scartati e richiedono cinque misure, riepilogo coerente e candidato selezionato per ogni modo di un
report accettato. La validazione ricostruisce il vincitore, riserva e rilascio VRAM, coerenza fra
picco/minimo libero/totale, policy approvata e appartenenza della macchina d'origine alla classe
nominata. Questi controlli provano coerenza dell'evidenza, non portabilità della busta.

`calibration-policy/v2` distribuisce il metodo pubblico di `calibration/v3`, non una lista di buste.
È legata a modello, digest artefatto, release/commit e digest del contratto motore; dichiara obiettivo,
modi, strategia CPU, dominio CUDA `[0, gguf.block_count]`, scala contesti, polling, rilascio, riserve,
tetto probe, round ABBA e selezione. `expected_maximum=41` ricontrolla i metadati del modello
appuntato, ma il runtime legge comunque il GGUF locale. La policy dichiara `GATE-PARTIAL`, elenca
l'unico scope realmente misurato, mantiene falso il collaudo su hardware materialmente diverso e
lega ogni report tramite percorso relativo e SHA-256 dei byte esatti.

`calibration-report/v2` è evidenza condivisa, revisionata e privacy-safe di `calibration/v3`. Ripete
identità e metodo, registra hardware senza hostname/username/percorsi, esito locale e limite del Gate,
probe, finalisti, busta osservata e risorse per modo, più riferimenti riproducibili. La busta resta
esplicitamente locale. Il loader costruisce soltanto un seed `n_cpu_moe` per modello, motore, backend
e modo esatti; non carica dal report `ctx`, hardware o valori prestazionali nel piano. Eliminare o
ignorare il seed lascia invariati dominio, contesti, tetto e selezione della ricerca locale completa.

`calibration-record/v2` è il record privato locale di `calibration/v3`. Registra identità completa
di modello, motore, OS/backend e hardware; obiettivo lessicografico; busta; fabbisogni conservativi;
costante di ricerca e riserve; probe in ordine; finalisti e due sessioni per finalista con round,
posizione ABBA, timestamp, RAM, VRAM, durata del rilascio, benchmark completo e telemetria opzionale;
vincitore di ogni round, deriva e regola di selezione. `validate` a ogni caricamento ricostruisce
mediane, ordine ABBA, unanimità, deriva, tie-break, minimi e aggregati. Il filename determina il
lifecycle: `.candidate.json`, attivo `.json`, rollback `.previous.json`; soltanto l'attivo può
entrare in `LaunchPlan`. `calibration-record/v1` è superato e riceve diagnosi azionabile, non una
migrazione implicita.

Un profilo può coprire solo alcuni modi. `validate` segnala come errore un modo citato ma inesistente;
non segnala come errore un modo non coperto. Sampling e servizi non possono comparire nei profili;
parametri di memoria non possono comparire nei modi. Un profilo è invalido se report o digest
mancano, se la busta non coincide col candidato selezionato, se modello/motore/hardware divergono,
se finestre e OS non copiano esattamente classe approvata e OS misurato o se la sua finestra si
sovrappone a un'altra classe applicabile allo stesso OS, backend e modo. Anche un profilo v1 valido
resta evidenza/seed e non una calibrazione locale per un'altra macchina, come stabilito da D-034.

Lo Step 2A crea schemi e modi; lo Step 2B aggiunge fixture sintetiche soltanto nei test. Nessuno dei
due crea profili di produzione: i risultati dello Spike 0 non soddisfano una calibrazione. Dopo
D-037, lo Step 5B può distribuire policy e sola evidenza del protocollo successivo; la busta usata
dal runtime nasce invece dalla calibrazione locale dell'utente.

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

Un record è calibrato per l'avvio soltanto quando è l'attivo `calibration-record/v2` prodotto
localmente da `calibration/v3` e coincidono modello/artefatto, release/commit e contratto del motore,
modo, backend e identità hardware stabile. La RAM disponibile deve coprire il fabbisogno misurato
più 2,0 GiB; su CUDA la VRAM libera deve coprire il fabbisogno misurato più 0,5 GiB. Candidato,
previous, schema superato o divergenza usano baseline o nuova calibrazione; non esiste nearest-match.

Le finestre RAM/VRAM di `profile/v1` riconoscono capacità nominali e possono ordinare seed condivisi,
ma D-034 vieta di usarle come prova che il vincitore dell'host d'origine sia calibrato localmente.
Non autorizzano interpolazione, estrapolazione o selezione della busta più vicina.

Spareggio difensivo fra seed condivisi, con estremi inclusivi:

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
con lo stesso minimo. I seed distribuiti non possono avere finestre sovrapposte per lo stesso modello,
motore, backend, OS e modo; `validate` le rifiuta. Lo spareggio ordina soltanto il lavoro del
calibratore e non produce
un `LaunchPlan` calibrato. Un pareggio risolto dall'id genera un warning in `doctor`.

Gate di memoria per il solo modello predefinito:

```python
DEFAULT_MODEL_MIN_TOTAL_GIB = 28.0
DEFAULT_MODEL_MIN_AVAILABLE_GIB = 22.0
```

D-049 applica la soglia disponibile comune a Linux e Windows: il gate statico non deve impedire a un
desktop idoneo di raggiungere il monitoraggio reale. `calibration/v3` continua a campionare la RAM
ogni 250 ms e scarta qualsiasi trial che scenda sotto la riserva dinamica di 2,0 GiB.

Se una delle soglie non è raggiunta, l'avvio si ferma prima di qualunque download. `--force` bypassa
esclusivamente questo gate; non bypassa config invalida, OS non supportato, motore assente o
incompatibile, porta occupata, checksum, contenuti invalidi o lock.

Dopo il gate:

1. record locale compatibile per il modo e con headroom corrente sufficiente → usa la sua busta;
2. nessun record locale valido ma modello predefinito con memoria sufficiente → baseline verificata
   nello spike (`ctx=8192`; `n_cpu_moe=48` su CUDA, assente su CPU), warning che non è ottimizzata e
   invito a eseguire la calibrazione locale; gli eventuali seed condivisi ordinano soltanto la ricerca;
3. modello diverso dal predefinito → nessun dato del modello predefinito viene usato; baseline
   con warning rafforzato, senza gate rigido basato su numeri non calibrati e senza dichiararla
   calibrata per il modello diverso.

Il valore precedente `ctx=16384` non è usato come ripiego perché lo Spike 0 ha misurato `ctx=8192`.
Il ripiego mantiene il prodotto usabile, ma non genera report, profilo o promessa di prestazioni.

`LaunchPlan` è la fusione non ambigua di modo + busta + config + identità del record locale/fallback
+ backend/GPU. Conserva separatamente l'identità `model`, usata per compatibilità e stato, e il
`model_path` fisico passato al motore. Un modo inesistente è input CLI invalido e mostra l'elenco dei
modi validi.

### 5.6 Calibrazione assistita e contribuzione

`calibration/v1` è distinto da `benchmark/v1`: confronta candidati espliciti, verifica VRAM e
stabilità e usa `benchmark/v1` su ciascun candidato valido. Lo Spike 0 ha provato un solo candidato e
quindi non è una calibrazione. Dopo l'audit D-034, anche `v1` resta un protocollo di laboratorio: non
conosce un dominio portabile, non monitora la RAM durante il trial e non produce un record locale
riutilizzabile, quindi non può alimentare profili di produzione.

`qwen-launcher calibrate --mode <id|all>` è un'operazione locale, esplicita e potenzialmente lunga.
Non parte durante un normale lancio, non modifica config o sorgenti, non crea commit, non usa API
GitHub e non effettua upload. Richiede modello e motore compatibili già disponibili, hardware sopra
il gate RAM e sopra la VRAM minima della policy per l'avvio automatico oppure il valore confermato
esplicitamente nel primo run guidato, nessun servizio gestito concorrente e conferma dell'utente dopo
avere mostrato durata,
spazio, log e rischio di scarto/crash del solo processo di prova.

Protocollo iniziale:

1. registra hardware, VRAM totale/libera e consumo GPU complessivo prima della prova; fuori da WDDM
   un PID compute iniziale rende la misura invalida. Su WDDM, dove il driver 610.47 verificato include
   anche contesti grafici inevitabili, v3 cattura una sola popolazione iniziale di file eseguibili:
   un respawn dello stesso file entro la molteplicità iniziale è evidence-only, mentre file nuovi,
   identità illeggibili o istanze aggiuntive invalidano il run. Il processo gestito coincide soltanto
   per `pid + create_time`; l'utente chiude comunque workload GPU intensivi prima della prova;
2. usa la policy approvata oppure, esclusivamente nello Step 5A prima del Calibration Gate, candidati,
   riserva e contesti forniti esplicitamente da Tommaso;
3. parte dalla baseline più prudente approvata e varia soltanto `n_cpu_moe` per CUDA; il codice
   impone un solo `ctx` per run, valori unici ordinati dal più prudente al più aggressivo e, su CPU,
   un solo candidato finché non esiste un asse verificato; la lista esplicita serve al Gate e non è
   una policy per hardware diverso; non prova flag fuori da `engine.lock`;
4. avvia un processo nuovo per ogni candidato, attende READY, esegue il carico reale del modo e
   campiona la VRAM complessiva tramite `nvidia-smi` ogni 250 ms;
5. `coding` e `studio` eseguono la richiesta testuale verificata; `vstudio` esegue anche la richiesta
   vision con mmproj; raggiungere READY da solo non rende valido un candidato;
6. dopo lo stop CUDA ricampiona ogni 250 ms fino a 10 s e accetta appena la memoria usata è entro
   `baseline + vram_release_tolerance_gib`; morte, OOM, salute incompatibile, risposta invalida,
   margine violato o rilascio fuori soglia scartano il candidato e conservano il log; la stessa
   tolleranza limita l'intervallo fra baseline degli avvii e una deriva maggiore scarta il candidato,
   mentre carico compute concorrente, cambio driver o monitor guasto invalidano l'intero run;
7. ogni candidato rimasto supera il numero di avvii stabili e `benchmark/v1`; la selezione
   massimizza la mediana tok/s fra i candidati che rispettano stabilità e riserva, poi preferisce
   maggiore VRAM libera e infine l'ordine prudente; `validate` ricostruisce questa scelta, che resta
   il migliore fra i candidati provati e non una prova di optimum globale;
8. genera report, profilo proposto, risultati benchmark, manifest SHA-256 e guida di contribuzione in
   `data_dir()/calibrations/<id>/` con scritture atomiche; i motivi puntano ai log relativi copiati,
   tutti i campi stringa e log sono redatti e `validate --path` rifiuta identità locali o pattern di
   percorsi assoluti POSIX/Windows prima della revisione umana;
9. valida il bundle localmente e richiede conferma umana: un output non confermato resta una bozza e
   non può entrare nei contenuti distribuiti.

Riserva e tolleranza VRAM, dominio degli assi, avvii e criterio statistico non vengono dedotti dal
ricordo di prove precedenti. Il run 8/32 produce evidenza sul proprio host, non valori universali.
Una policy pubblica richiede il protocollo successivo previsto da D-037: dominio legale verificato
nel lock o in contenuto approvato, screening locale, finalisti, RAM e VRAM durante il trial, criterio
robusto e record atomico compatibile con la macchina corrente. Contesto e modi restano separati.
`calibration/v2` ha soddisfatto questi requisiti strutturali ma il Gate ne ha respinto la conferma;
il design resta storico in `docs/calibration-v2-design.md`. Il protocollo attivo è
`calibration/v3` (D-041–D-046, `docs/calibrate_v3.md`): mantiene scala e screening misurato, verifica
la monotonia sui soli probe fattibili e usa l'interpolazione soltanto per scegliere un punto interno
alla staffa. Ogni trial rispetta 2,0 GiB RAM e, su CUDA, 0,5 GiB VRAM. I finalisti eseguono due round
A→B/B→A con benchmark completo per avvio; la dominanza richiede lo stesso vincitore in entrambi i
round, mentre discordanza, parità o deriva oltre 0,125 GiB usano margine e prudenza. Telemetria GPU è
solo evidenza. Il dominio `n_cpu_moe` resta `[0, 41]`, verificato dai metadati e dai probe reali.

Il v3 scrive prima il record candidato; per default lo promuove atomicamente all'attivo e conserva
un previous, mentre `--no-activate` e `--activate` separano Gate e promozione. `--target-ctx` può
fissare un contesto esperto approvato senza cambiare il default contesto-prima; D-050 aggiunge
`98304` mantenendolo fuori dalla scala automatica. I log privati dell'ultimo run
vivono in un solo slot ruotato; bundle e pubblicazione restano separati.

Un utente idoneo senza record locale continua con la baseline oppure calibra uno o più modi. Un
record parziale vale solo per i modi provati. Nessun seed «più vicino» viene usato come busta finale e
hardware fuori dalle vecchie classi non viene escluso dalla ricerca locale. Il bundle condivisibile
resta separato dal record privato; pubblicazione e revisione restano manuali.

### 5.7 Contratto del comando motore

I nomi dei flag non sono definiti dalla memoria dell'esecutore né dal ramo corrente di `llama.cpp`.
Lo Step 0 li verifica sulla release scelta e li registra in `engine.lock` come `verified_flags` e
come template nel contratto semantico macchina `command_contract`. Il builder espande soltanto i
placeholder dichiarati dal lock; non associa nel codice un significato a un flag non descritto.

Il costruttore di argomenti deve rappresentare esplicitamente:

- percorso fisico del modello risolto dall'identità configurata;
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

### 5.8 Motore e `engine.lock`

Formato minimo del lock; i nomi reali dei flag e i valori fissi arrivano esclusivamente dallo spike:

```json
{
  "schema": "engine-lock/v1",
  "project": "ggml-org/llama.cpp",
  "release": "<scelta nello spike>",
  "source_commit": "<sha verificato>",
  "default_model": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M",
  "default_model_artifact": {
    "repository": "<repository verificato>",
    "revision": "<commit modello verificato>",
    "filename": "<GGUF verificato>",
    "size_bytes": 1,
    "sha256": "<64 hex>",
    "mmproj": {"filename": "<mmproj>", "size_bytes": 1, "sha256": "<64 hex>"}
  },
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
    "model_args": ["<flag>", "{model_path}"],
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

Il contratto attivo mantiene i pesi `UD-Q4_K_M`, la cache predefinita verificata e `--mmap`. Il
mini-spike Ubuntu b10011 definito in `CALIBRATE.md` ha confrontato contratto attuale, cache K/V
`q8_0` con mmap e cache K/V `q8_0` con `--no-mmap`: Q8+mmap è GO, no-mmap è NO-GO. Salute, MTP, UI,
vision, stop, RAM, VRAM e `benchmark/v1` sono registrati in `docs/mini-spike-kv-q8-ubuntu/`.
`benchmark/v1` non misura qualità semantica. Il lock globale resta invariato fino allo smoke Windows;
con GO Windows, la PR dichiarativa aggiunge `--cache-type-k` e `--cache-type-v` soltanto agli
argomenti CUDA, conserva `--mmap`, lascia il ramo CPU invariato e resta separata dalle correzioni core.

Il modello predefinito viene risolto senza rete e senza scritture alla directory snapshot della
revisione appuntata, rispettando la precedenza delle directory cache osservata nel sorgente della
release lock. Filename, dimensione e SHA-256 devono coincidere prima dell'avvio. `model_path`
esplicito consente un artefatto locale per un'identità diversa, che resta non calibrata e riceve il
warning rafforzato della sezione 5.5. Il launcher non usa `--hf-repo`: nella release lock quel
percorso consulta il branch remoto corrente e può creare o modificare ref, blob, snapshot e symlink
nella cache Hugging Face.

Ruoli ammessi almeno: `server`, `cuda-runtime`, `source`. Asset e checksum possono essere vuoti nello
Step 1 con `assets_complete=false`; dallo Step 2B `validate` emette un warning ed `engine install`
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

### 5.9 Processi, stato, salute e log

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

### 5.10 Installazione sicura del motore

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
- per Ubuntu CUDA, coppia che nessun prebuilt CUDA per Linux copre nella release appuntata, si usa
  l'asset sorgente appuntato e verificato dal lock; niente clone di un tag mobile e niente
  installazione automatica di pacchetti.

### 5.11 Errori ed exit code

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

### 5.12 Divieti globali

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

**Protocollo manuale `benchmark/v1`, normativo come misura di fattibilità e riusato da
`calibration/v1`:**

- prompt testuale fisso in `docs/spike-0/benchmark-v1-prompt.txt` e template della richiesta in
  `docs/spike-0/benchmark-v1-request.json`, entrambi identificati dal loro SHA-256 nello spike JSON;
- 256 completion token esatti per misura; il meccanismo verificato per evitare una chiusura
  anticipata e l'eventuale seed sono registrati nel template. Se la release non consente misure
  valide da 256 token, il protocollo viene corretto prima del `GO`, non retroattivamente;
- un warm-up completo escluso e cinque misurazioni valide per ogni combinazione OS/backend/modo
  provata nello spike;
- nessun client concorrente;
- tok/s dalle metriche della release se lo spike ne dimostra l'affidabilità, altrimenti conteggio
  token/tempo con metodo e punti temporali documentati;
- registrazione di misure singole, minimo, mediana e massimo, oltre a OS, hardware, modello, motore,
  modo e parametri; la media facoltativa non sostituisce la mediana.

Lo Step 5A trasferisce lo stesso prompt e template richiesta nelle risorse di pacchetto e automatizza
questo protocollo dentro la calibrazione senza cambiarne semantica o numeri; lo Step 9 espone anche il
comando benchmark autonomo. Una modifica futura richiede `benchmark/v2`.

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
   GPU layers, `n_cpu_moe` e motivazione di ogni variazione. Queste prove verificano la fattibilità:
   senza confronto fra candidati e `calibration/v1` nessuna busta entra in un profilo.
6. Su Windows 11 e Ubuntu si provano i tre modi col modello predefinito, usando soltanto flag presenti
   nell'help della release. La matrice proposta da collaudare è: coding UI off/vision off e sampling
   `(0.6, 0.95, 20)`; studio UI on/vision off e `(0.7, 0.8, 20)`; vstudio UI on/vision on e
   `(0.7, 0.8, 20)`. Ogni correzione viene motivata nello spike.
7. Si verificano: caricamento, salute, API, MTP, sampling, UI on/off esplicita, mmproj/immagini,
   metriche, CPU senza flag CUDA, CUDA, `CUDA_VISIBLE_DEVICES`, stop e log.
8. Si esegue `benchmark/v1`; nessun numero viene inventato e i risultati non sono presentati come
   ottimizzazione o profilo calibrato.
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
nell'installazione isolata. `validate` entra nella verifica wheel soltanto allo Step 2B.

**Commit locale suggerito:**
`chore: scaffold installabile con config, risorse e CI riproducibile`

### Step 2A — Contratti dichiarativi e modi

**Obiettivo:** costituire i contratti dati v1 senza promuovere la baseline dello spike a profilo
ottimizzato e senza mescolare contenuto e core nella stessa PR.

**Perimetro dichiarativo:** schemi JSON e modi; nessun modulo Python, test core o profilo reale.

**Attività:**

1. Implementa `mode.v1.json`, `profile.v1.json`, `calibration-policy.v1.json` e
   `calibration-report.v1.json` secondo la sezione 5.3.
2. Crea i modi `coding`, `studio`, `vstudio` con valori collaudati nello spike. Valori iniziali di
   sampling: coding `(0.6, 0.95, 20)`; studio/vstudio `(0.7, 0.8, 20)`, salvo correzione documentata
   dallo spike.
3. Non creare profili, policy o report di produzione: le dodici misure dello spike provano
   compatibilità ma non hanno confrontato candidati.
4. Verifica che i JSON siano UTF-8 validi, che le risorse entrino in wheel/sdist e che non esista una
   seconda copia normativa degli schemi.

**Definition of Done:** schemi e modi viaggiano negli artefatti; nessun dato dello spike è etichettato
come profilo calibrato. Lo Step 2A non introduce comportamento runtime.

**Commit locale suggerito:**
`feat(content): definisci schemi v1 e modi verificati dallo spike`

### Step 2B — Validazione, modelli runtime e hardware

**Precondizione:** Step 2A concluso e artefatti dichiarativi invariati salvo correzioni necessarie a
contraddizioni emerse implementando i test; una correzione schema torna in una PR dichiarativa 2A.

**Obiettivo:** rendere eseguibili i contratti dello Step 2A e rilevare affidabilmente la macchina.

**Perimetro core:** dataclass, caricatori, `validation.py`, `hardware.py`, CLI, CI, verifica wheel e
test; nessun contenuto di produzione.

**Attività:**

1. Implementa dataclass gelate e caricatori; un catalogo profili assente o vuoto è valido e prepara
   il ripiego dello Step 3. Le fixture sintetiche vivono soltanto nei test.
2. `validate` mostra file, percorso del campo e motivo; esegue controlli semantici, riferimenti fra
   modi/profili/report, digest, candidato selezionato, coerenza modello/motore, finestre non
   sovrapposte e ordinamento tok/s.
3. Divergenza `profile.engine != engine.lock.release` = warning e profilo non calibrato a runtime;
   report mancante o incoerente, contenuto malformato o modo inesistente = errore.
4. Implementa `HardwareInfo`, rilevamento NVIDIA, RAM disponibile e politica GPU; conserva valori
   esatti in GiB senza trasformarli automaticamente in classi nominali.
5. Estendi `doctor` con OS, CPU, RAM totale/disponibile, GPU, VRAM totale/libera, backend, versione,
   percorsi e stato «nessun profilo calibrato» senza presentarlo come errore bloccante.
6. Aggiungi `validate` sia alla CI sorgente sia alla verifica della wheel installata.

**Test obbligatori:** esempi sintetici validi; ogni classe di errore schema; controlli semantici;
profilo parziale con report valido; report/digest/candidato incoerenti; finestre sovrapposte; motore
divergente; catalogo vuoto; `nvidia-smi` presente/assente/fallito/corrotto; due GPU e spareggio;
conversioni GiB.

**Definition of Done:** `validate` restituisce gli exit code contrattuali dalla sorgente e dalla
wheel, `doctor` descrive la macchina e nessun profilo di produzione è stato presunto.

**Commit locale suggerito:**
`feat(validation): applica contratti v1 e rileva hardware senza profili presunti`

### Step 2C — Correzione del contratto artefatto modello

**Obiettivo:** rimuovere l'ambiguità emersa fra l'identità Hugging Face configurata e il percorso
fisico richiesto dal flag `-m`, senza introdurre flag non verificati o modificare la cache Hugging
Face.

**Perimetro:** estensione additiva di `engine.lock`, configurazione `model_path`, validazione del lock,
test e documentazione normativa. Nessun matching, processo o comando di avvio dello Step 3.

**Attività:**

1. Copia da `docs/spike-0.json` revisione, filename, dimensioni e SHA-256 esatti di modello e mmproj.
2. Correggi il placeholder del contratto macchina in `{model_path}`, mantenendo il flag `-m` già
   verificato su entrambi gli OS/backend.
3. Mantieni `model` come identità stabile e aggiungi il percorso opzionale `model_path` con la stessa
   precedenza severa della configurazione 0.1.
4. Valida struttura degli artefatti, digest, placeholder ammessi e copertura di ogni flag emesso.
5. Verifica dalla wheel che il contratto corretto resti disponibile e valido.

**Definition of Done:** configurazione e lock non confondono più identità e percorso; nessuna rete o
scrittura nella cache Hugging Face; suite e matrice CI Ubuntu/Windows verdi.

**Commit locali suggeriti:**
`fix(content): appunta gli artefatti modello verificati nel lock` e
`fix(config): separa identità modello e percorso eseguibile`

### Step 3 — Vertical slice `coding`, stato, stop e status

**Precondizione:** Step 2C concluso e matrice CI verde.

**Obiettivo:** usare un motore dello spike già presente e ottenere un prodotto funzionante end-to-end.

**Attività:**

1. Implementa matching e ripiego secondo 5.5, inclusi modello e modo.
2. Risolvi il modello predefinito dalla revisione appuntata in sola lettura e verificane filename,
   dimensione e SHA-256; per un'identità diversa usa soltanto il `model_path` esplicito, richiede un
   file GGUF leggibile e non attribuirgli un digest o una calibrazione non dichiarati.
3. Implementa `LaunchPlan` e builder CPU/CUDA con flag esatti del lock, passando a `-m` soltanto il
   percorso risolto.
4. Aggiungi il test di coerenza: ogni flag emesso appartiene a `verified_flags`.
5. Implementa `engine.locate()` con ordine e compatibilità di 5.8.
6. Implementa stato, lock d'avvio, log, porta, salute, timeout, identità processo e stop secondo 5.9.
7. L'ambiente figlio CUDA include la sola GPU scelta se lo spike ne ha confermato l'efficacia.
8. Implementa `coding --force`: detect → gate memoria → resolve → locate → start → salute → endpoint
   API → foreground.
9. `coding` applica esplicitamente UI off e vision off.
10. Implementa `stop` e `status` idempotenti.
11. Crea `tests/fakes/fake_server.py` con salute ritardata, 503, risposta incompatibile e crash.

**Test obbligatori:** matching CUDA/CPU con report valido; catalogo vuoto; nessun profilo più vicino;
modello diverso; profilo senza modo; risoluzione snapshot appuntata, digest errato, artefatto assente e
`model_path` esplicito; RAM totale o disponibile bassa; perimetro di `--force`; builder CPU/CUDA e
UI/vision; flag-lock; ready; timeout; crash; porta occupata; doppio avvio; lock obsoleto;
stato corrotto; PID riusato; stop/status senza servizi; Ctrl-C.

**Verifica manuale:** su entrambe le macchine, `coding` col motore dello spike e catalogo reale ancora
vuoto; modello servito con baseline dichiarata non ottimizzata, GPU corretta e stop pulito.

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

### Step 5A — Calibrazione assistita e generazione del bundle

**Obiettivo:** prima conservare una procedura di laboratorio riproducibile, poi completarla come
calibrazione realmente locale e riutilizzabile su PC supportati diversi, senza trasferire l'optimum
della macchina del maintainer.

**Perimetro core:** `benchmark.py`, `calibration.py`, CLI, monitoraggio tramite i moduli esistenti,
risorse immutabili di `benchmark/v1`, test e documentazione tecnica minima. Nessun profilo reale e
nessuna policy finale entrano in questo step, così la PR core resta separata dal contenuto.

**Attività:**

1. Copia byte per byte nelle risorse prompt e template di `benchmark/v1` dello spike e verifica i
   relativi SHA-256; implementa warm-up escluso, cinque misure esatte, min/mediana/max e controlli su
   token e `finish_reason` senza rete nei test.
2. Implementa `qwen-launcher calibrate --mode <id|all>`. In assenza della policy approvata il comando
   richiede interattivamente o tramite opzioni esplicite contesti, candidati `n_cpu_moe`, riserva
   VRAM, tolleranza di rilascio e numero di avvii; non sceglie default dalla memoria dell'autore.
3. Mostra preflight, baseline, candidati, durata indicativa e destinazione; richiede conferma prima di
   avviare processi e consente annullamento pulito con exit 130.
4. Esegue il protocollo della sezione 5.6 riusando builder, lifecycle, salute e stop di produzione;
   ogni candidato ha processo e log separati e un fallimento non altera stato o profilo attivo.
5. In `calibration/v1` campiona VRAM complessiva e libera, non soltanto quella attribuita al PID;
   registra baseline, minimo libero, picco e campione finale. Dopo lo stop usa finestra e tolleranza
   di 5.6; deriva oltre soglia scarta il candidato, contaminazione o monitor inaffidabile invalidano
   il run. Il successore deve campionare anche RAM disponibile per tutti i backend.
6. Genera un bundle locale con report, risultati, bozza profilo, digest e guida PR. La bozza non passa
   come profilo distribuibile finché policy, finestra e selezione non sono approvate.
7. Implementa `validate --path <bundle>` senza modificare la validazione predefinita delle risorse
   installate. Nessun comando crea branch, commit, push, issue o PR.
8. Rimuove dai file condivisibili hostname, username e percorsi assoluti tramite riferimenti log
   relativi e redazione ricorsiva; lo scanner privacy di `validate --path` protegge anche bundle
   altrui e la CLI mostra l'anteprima esatta dei dati da condividere.
9. Se nessun candidato è valido, conserva exit 0 per la procedura riuscita ma lo dichiara
   esplicitamente per ogni modo.
10. Correzione D-034: vieta contesti misti, `n_cpu_moe` duplicati/fuori ordine e finti candidati CPU;
    ricostruisce in `validate` riserva, rilascio, coerenza VRAM, classe d'origine e vincitore.
11. Prima del Gate successivo verifica il dominio legale di ogni asse sul modello/motore lock e
    definisce tramite spike screening, finalisti e trattamento del rumore; il nuovo contratto usa una
    versione successiva, non altera retroattivamente `calibration/v1`.
12. Implementa monitoraggio RAM, policy hardware-indipendente, ricerca per modo, record locale
    atomico, compatibilità, controllo headroom e invalidazione. I dati condivisi possono soltanto
    ordinare i seed e non vengono passati direttamente a `LaunchPlan`.

**Test obbligatori:** policy assente; sintassi CPU/CUDA; annullamento; ordine candidati; candidato
valido, crash, OOM simulato, timeout, margine violato, carico concorrente; rilascio lento, entro/fuori
tolleranza e oltre finestra; deriva fra avvii entro/oltre soglia; processo distinto; warm-up escluso;
cinque misure; mediana e spareggi; coding/studio/vstudio; interruzione; bundle atomico; digest;
riferimenti relativi, redazione JSON/log/fallback e scanner privacy POSIX/Windows; contesto misto;
policy fuori ordine; selezione manomessa; riserva/rilascio incoerenti; dominio e finalisti del nuovo
protocollo; monitor RAM; record locale valido/obsoleto/senza headroom; seed su hardware differente;
nessuna rete o GPU reale.

**Definition of Done:** un utente su qualunque macchina nel perimetro supportato può avviare la
ricerca senza conoscere flag interni, ottenere una busta locale misurata e riutilizzarla in sicurezza;
un PC con capacità simili ma componenti diversi non eredita automaticamente il vincitore di un
report condiviso. Il bundle di contribuzione resta separato e non pubblicato.

**Commit locale suggerito:**
`feat(calibration): automatizza prove hardware e genera bundle riproducibili`

### Calibration Gate 0.1 — Prima calibrazione locale e prova di portabilità

Tommaso usa personalmente lo Step 5A corretto sulla macchina dello spike. Il run 32/8 è il primo caso
locale, non il template del prodotto. Il gate:

- verifica che dominio e strategia derivino da contratto/spike, non dal confine della RTX 2060 SUPER;
- mantiene il contesto fisso per confronto e prova separatamente coding, studio e vstudio;
- osserva RAM e VRAM durante caricamento, workload, benchmark e rilascio;
- verifica screening, monotonia sui soli fattibili, ABBA, benchmark per avvio, unanimità, deriva,
  riserve RAM/VRAM, telemetria best-effort, MTP e vision;
- usa `--no-activate` e ricostruisce il candidato `calibration-record/v2`; soltanto dopo la
  conclusione del Gate lo promuove e riusa, poi lo invalida simulando cambi di motore, modello,
  hardware e headroom insufficiente;
- verifica che un seed 32/8 proveniente da CPU/GPU diverse non diventi direttamente un `LaunchPlan`;
- registra un secondo caso reale materialmente diverso quando disponibile; per D-047 la sua assenza
  mantiene la copertura `GATE-PARTIAL` ma non blocca Step 5B, purché il limite sia dichiarato;
- per CPU approva un asse di tuning verificato oppure dichiara onestamente il backend come baseline
  auto-configurata dal motore, non come optimum prodotto dal launcher;
- controlla privacy e separazione fra record locale privato e bundle condivisibile;
- decide `CALIBRATION-ACCEPTED` o `CALIBRATION-REJECTED` per OS, backend e modo provati.

Un esito rifiutato mantiene la baseline e torna allo Step 5A. Non si trasformano a mano risultati
incompleti né si allargano finestre per simulare generalizzazione.

**Stato al 19 luglio 2026:** il run Windows 11/CUDA `--mode all --no-activate` è accettato localmente
per coding, studio e vstudio e ha lasciato tre candidati validi ma inattivi. La ricostruzione a
freddo, il lifecycle e `doctor` sono verificati sul commit `2d4cc22`; CI Ubuntu/Windows è verde.
Manca il secondo caso hardware materialmente diverso, quindi il Gate empirico resta `GATE-PARTIAL`.
D-047 accetta esplicitamente questo limite per la progressione: Step 5B è autorizzato, mentre
promozione/riuso dei candidati restano azioni separate e non sono state eseguite. Evidenza:
`docs/calibration-gate-v3-windows.md`.

### Step 5B — Policy di ricerca approvata, evidenza e flusso pubblico

**Precondizione:** almeno un risultato locale del Gate corretto è `CALIBRATION-ACCEPTED`, CI è
verde e il limite della copertura empirica è dichiarato secondo D-047. La prova su hardware
materialmente diverso non è bloccante.

**Perimetro dichiarativo:** policy del nuovo protocollo, report di riferimento, checksum e guida di
contribuzione. Correzioni core tornano allo Step 5A e non vengono mescolate nella stessa PR.

**Attività:**

1. Crea la policy con gli esatti valori sostenuti dal Gate locale e un dominio derivato dal modello,
   non costruito sulla sola capacità RAM/VRAM. Dichiara che le costanti non sono ancora validate
   empiricamente su hardware materialmente diverso.
2. Include soltanto report revisionati e privi di dati privati come evidenza/seed; nessuna mediana
   viene presentata come promessa su componenti diversi.
3. Non pubblica profili `profile/v1` come buste finali. Ogni utente genera il proprio record locale;
   i seed condivisi possono soltanto modificare l'ordine della stessa ricerca completa.
4. Attiva `qwen-launcher calibrate --mode <id|all>` tramite la policy senza richiedere conoscenza di
   flag o candidati interni.
5. CLI e `doctor` distinguono requisiti non soddisfatti, baseline non ottimizzata, record locale
   valido, record obsoleto e headroom corrente insufficiente.
6. Completa guida, naming del bundle, checklist e testo PR. La contribuzione richiede copia,
   validazione, suite e revisione; nessuna autenticazione o pubblicazione automatica.
7. Esegue `validate`, build e verifica wheel con policy ed evidenza installate.

**Test obbligatori:** policy e dominio approvati; seed di componenti diversi; ricerca invariata con e
senza seed; record locale parziale; modello/motore/driver/hardware divergenti; RAM/VRAM corrente
insufficiente; fallback senza nearest-match; output contribuzione; risorse dalla wheel.

**Verifiche manuali:** calibrazione e riuso locale sui casi reali del Gate; fallback su hardware senza
record; ispezione del bundle condivisibile; prova che cancellare il record non altera config o cache
Hugging Face.

**Definition of Done:** il pacchetto distribuisce un metodo di ricerca, non l'optimum del PC 32/8;
un utente idoneo calibra e usa localmente la propria busta senza conoscere `llama-server`, mentre il
contributo resta opzionale e manuale. Documentazione e contenuti mantengono visibile che l'evidenza
reale v3 copre per ora un solo hardware e che la validazione eterogenea è un follow-up.

**Stato al 19 luglio 2026:** completato con `calibration-policy/v2`, `calibration-report/v2`, policy
per i tre modi, evidenza Windows 11/CUDA privacy-safe, manifest, guida di contribuzione e seed
proiettati esclusivamente su `n_cpu_moe`. Nessun `profile/v1` di produzione è stato pubblicato.

**Commit locale suggerito:**
`feat(content): pubblica policy portabile ed evidenza per la calibrazione locale`

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
3. Completa README, CONTRIBUTING, anatomy di modo/profilo, guida calibrazione e bundle, benchmark,
   troubleshooting, requisiti, privacy, sicurezza e roadmap 0.2.
4. CONTRIBUTING impone: una PR tocca contenuto oppure core, non entrambi; ogni evidenza porta il
   protocollo approvato, numeri misurati sulla release lock, bundle validato e approvazione personale
   del manutentore; un report condiviso non diventa una busta finale remota; branch protection.
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
- hardware senza record locale: baseline, calibrazione, riuso locale e bundle separato senza upload;
- seed di altro hardware: nessuna applicazione diretta, ricerca locale e selezione deterministica;
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

### Step 9 — Benchmark autonomo e chiusura del ciclo

**Obiettivo:** esporre autonomamente il `benchmark/v1` già usato da `calibrate`, confrontare una
busta attiva con l'evidenza accettata e completare la diagnostica 0.2.

`benchmark --mode <id>` richiede un server vivo e legge dallo stato modo, modello, release, record
locale o fallback, ctx e `n_cpu_moe`. Riusa senza duplicazioni prompt, template, controlli e calcolo
introdotti nello Step 5A: warm-up escluso, cinque misure esatte da 256 token, nessun client concorrente,
min/mediana/max e metadata completi.

Il comando produce un risultato benchmark conforme e, quando esiste un record locale, mostra la
differenza rispetto alla sua mediana senza modificarlo. Senza record non genera una busta calibrata:
indirizza a `calibrate`, perché un singolo benchmark non confronta candidati né verifica stabilità.

Completa inoltre:

- `doctor` con stato ✅/⚠️/❌ e rimedio per ogni riga non verde;
- `docs/benchmarks.md` con distinzione fra benchmark, calibrazione e regressione;
- verifica di regressione ripetibile per report accettati, senza soglie inventate;
- template PR evidenza basato sul bundle del protocollo locale approvato;
- template PR skill con esempi positivi/negativi e suite verde.

**Test obbligatori:** server assente o stato incompatibile; warm-up escluso; cinque misure; mediana;
record locale presente/assente; confronto con report; nessuna modifica ai contenuti; nessuna rete
reale; metodo metriche/fallback; metadata dallo stato.

**Commit locale suggerito:**
`feat(0.2): esponi benchmark autonomo e completa doctor`

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

- [x] Spike `GO`, artefatto umano e JSON coerenti.
- [x] Release motore, commit, versione, contratto semantico dei flag, API e salute appuntati.
- [x] Python e dipendenze riproducibili; `uv.lock` committato.
- [x] Wheel contiene tutte le risorse ed è provata isolatamente su Linux e Windows.
- [x] Config severa, senza side effect o modifiche automatiche.
- [x] Schemi, report, digest e controlli semantici verdi.
- [x] Nessuna misura di fattibilità dello spike è presentata come profilo ottimizzato.
- [x] Record locali legati a modello/artefatto, contratto motore, OS, backend, hardware e modo.
- [x] Seed condivisi mai applicati direttamente; nessuna interpolazione o nearest-match.
- [x] RAM disponibile considerata; `--force` confinato.
- [x] GPU scelta e realmente isolata oppure multi-GPU CUDA bloccato.
- [x] Builder CPU/CUDA distinto; tutti i flag coperti dal lock.
- [x] UI e vision applicate esplicitamente.
- [x] Lifecycle, lock, stato corrotto, log, timeout e PID riusato coperti da test.
- [x] Installazione motore sicura e attivazione atomica via manifest, con checksum e anti path traversal.
- [x] `coding`, `studio`, `vstudio`, `stop`, `status`, `doctor`, `validate` verificati.
- [x] Hardware idoneo senza record locale usa baseline dichiarata non ottimizzata e riceve un rimedio.
- [x] `calibrate` cerca localmente nel dominio approvato, misura RAM/VRAM, verifica finalisti con
  `benchmark/v1`, salva un record compatibile e genera separatamente un bundle condivisibile.
- [x] Calibration Gate eseguito da Tommaso e accettato localmente per Windows CUDA; D-047 autorizza
  la progressione con copertura `GATE-PARTIAL`. La policy governa il metodo e non distribuisce
  l'optimum 8/32 come busta finale.
- [~] Follow-up non bloccante: ripetere `calibration/v3 --no-activate` su hardware materialmente
  diverso e aggiornare l'evidenza senza reinterpretare retroattivamente il Gate locale.
- [ ] Installer provati in Ubuntu pulito e Windows Sandbox.
- [ ] Release autorizzata tramite cancello umano; nessuna pubblicazione implicita.

### Milestone 0.2

- [ ] Router senza regex, normalizzazione e spareggi deterministici.
- [ ] Ogni skill porta test positivi e negativi.
- [ ] Open WebUI e dipendenze appuntate, attivazione atomica via manifest e fallback verificato.
- [ ] Utente informato che le impostazioni UI non persistono con config non persistente.
- [ ] Sync produce dati/artefatti locali senza eseguire contenuti contribuiti.
- [ ] Benchmark autonomo riusa lo stesso `benchmark/v1` già automatizzato dalla calibrazione 0.1 e
  distingue misura, regressione e record locale calibrato.
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
