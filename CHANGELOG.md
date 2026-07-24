# Changelog

Le modifiche rilevanti sono registrate qui per versione. I piani futuri non appartengono al
changelog: sono in `IMPLEMENTATION_SPEC.md`.

## [Unreleased]

## [0.1.3] - 2026-07-24

Release di correttezza e preparazione misurabile per il gate umano di `calibration/v6-lite`; il
protocollo v5 resta il default e v6 non è ancora implementata.

### Added

- Un pacchetto repository-only `scripts/spike_ctx/` prepara lo spike cross-context umano con
  quick-bench non cached, bisezione a esiti tipizzati, appendici MTP/reasoning, dry-run offline e
  template di evidenza. Non esegue il run reale né decide GO/NO-GO.

### Fixed

- Gli errori di monitoraggio RAM/VRAM scoperti durante il cleanup prevalgono ora sui fallimenti del
  workload e invalidano correttamente l'intero run.
- Le violazioni della riserva VRAM e il mancato rilascio post-stop hanno classi distinte, così i
  protocolli sperimentali non confondono un limite monotono con un errore ritentabile.

### Changed

- Il contratto motore rende MTP esplicito nel piano di lancio: `coding` e `studio` mantengono lo
  stesso argv, mentre `vstudio` usa prudentemente `speculative=disabled` insieme a `--mmproj`.
- Il contratto prepara, senza attivarli nei modi `mode/v1`, i flag verificati di sampling esteso e
  reasoning necessari a un eventuale `calibration/v6-lite`.
- Il nuovo digest del contratto rende incompatibili al riuso i record locali precedenti; i file
  restano leggibili e il rimedio è rieseguire `calibrate`.

## [0.1.2] - 2026-07-23

Release di stabilizzazione con `calibration/v5`, UX terminale uniforme, progresso della compilazione
Ubuntu CUDA e disinstallazione completa delle installazioni gestite da uv.

### Fixed

- I valori dinamici della CLI vengono resi come testo letterale: parentesi quadre e sequenze simili
  al markup Rich non vengono più nascoste, reinterpretate o trasformate in errori non gestiti.

### Changed

- `calibration/v5` aggiunge 96K (`98304`) e 48K (`49152`) alla scala automatica, porta il cap a 14
  probe e produce `calibration-record/v4`; i record v2/v3 storici restano leggibili.
- `doctor` mostra i parametri calibrati del record attivo valido (`ctx` e, su CUDA,
  `--n-cpu-moe`) invece della sola etichetta "valid".
- La CLI usa una presentazione Rich condivisa per stati, tabelle, errori e progresso, mantenendo
  etichette testuali leggibili anche senza colore.
- La compilazione Ubuntu CUDA mostra la percentuale reale letta dall'output CMake anziché un
  indicatore indeterminato.
- `uninstall` usa una sola conferma per rimuovere le radici gestite e la propria installazione
  `uv tool`, senza rimuovere uv o la cache Hugging Face.
- I workflow CI e release usano release Node 24 delle action, sempre appuntate a SHA completo.

### Known limitations

- La copertura di calibrazione resta `GATE-PARTIAL` finché manca hardware materialmente diverso.
- Il maintainer ha autorizzato la pubblicazione GitHub senza ripetere un Gate manuale multipiattaforma
  per `0.1.2`; PyPI resta indisponibile ed escluso.

## [0.1.1] - 2026-07-23

Release di stabilizzazione con `calibration/v4`, isolamento delle porte dei trial e progresso
visibile durante calibrazione e installazione del motore.

### Added

- `calibration-record/v3` registra esplicitamente `calibration/v4` e la sua riserva, mantenendo
  caricamento e ricostruzione semantica dei record v2 storici.

### Fixed

- L'installazione del motore mostra la fase corrente e, sui terminali, barre a byte con velocità ed
  ETA durante download ed estrazione; i probe restano limitati ma portano da 10 a 60 secondi il
  margine per il primo avvio lento dell'asset CUDA Windows.
- I server temporanei di calibrazione usano una porta loopback assegnata dal sistema quando
  `llama_port` è occupata; gli avvii normali continuano a richiedere la porta configurata.
- Il riuso di un record tollera al massimo 1 MiB di variazione nel totale RAM riportato, mantenendo
  invariati identità dei componenti e controlli di headroom RAM/VRAM.

### Changed

- `calibration/v4` sostituisce l'esecuzione v3 mantenendone scala, ricerca e conferma ABBA, ma usa
  0,3 GiB di riserva VRAM; al riuso ogni record conserva la propria riserva originaria.
- La calibrazione v4 mostra trial in corso, avanzamento live ed ETA per fase sui terminali, conserva
  output lineare quando rediretta e riepiloga motivazione della selezione e headroom misurato.
- La documentazione è stata riscritta come percorso lineare per nuovi utenti e descrive soltanto il
  comportamento corrente.
- Le prove misurate sono state separate dai manuali sotto `evidence/`; audit e design superati sono
  stati rimossi.
- `IMPLEMENTATION_SPEC.md` conserva lo stato sintetico e il solo lavoro ancora da realizzare, senza
  i piani dettagliati delle milestone concluse.

### Known limitations

- I Gate reali Ubuntu e Windows sono stati attestati dal maintainer, ma la copertura resta
  `GATE-PARTIAL` finché manca hardware materialmente diverso; il Gate Ubuntu non rende
  `n_cpu_moe=36` sicuro.
- `0.1.1` è pubblicata soltanto su GitHub Releases; PyPI resta fuori da questa pubblicazione.

## [0.1.0] - 2026-07-20

Prima release pubblica di `qwen-launcher`.

### Added

- Installazione esplicita del tool su Ubuntu e Windows con uv `0.11.28`, CPython `3.12.13` e verifica
  SHA-256 della wheel.
- Modello Qwen e proiettore vision appuntati per revisione, filename, dimensione e digest, letti
  senza modificare la cache Hugging Face.
- Contratto `llama.cpp b10011` con flag, API, health check e asset CPU/CUDA verificati.
- Installazione sicura del motore con download HTTPS, estrazione confinata, directory immutabili e
  attivazione atomica tramite manifest.
- Modi `coding`, `studio` e `vstudio`, con UI e vision applicate esplicitamente.
- Lifecycle in foreground, porta loopback, log, health polling, stato atomico, lock di avvio,
  `status` e `stop` basati su `pid + create_time`.
- Configurazione TOML severa con precedenza ambiente > file > default e directory Linux/Windows
  definite.
- Rilevamento CPU, RAM e NVIDIA; selezione GPU deterministica e ambiente CUDA confinato al figlio.
- Calibrazione locale v3 con ricerca adattiva, monitoraggio RAM/VRAM, conferma ABBA,
  `benchmark/v1`, record candidato/attivo/previous e diagnostica di riuso.
- Policy e report pubblici v2 usati soltanto come evidenza e seed d'ordine, mai come busta remota.
- Validazione JSON Schema e semantica di lock, modi, policy, report e bundle.
- `doctor`, `validate`, `engine install`, `engine status`, `uninstall` e installer senza elevazione.
- CI e workflow release multipiattaforma con action a SHA completo e pubblicazione PyPI OIDC.

### Changed

- Gate RAM disponibile del modello predefinito fissato a 22 GiB, mantenendo 28 GiB totali e riserva
  dinamica di calibrazione da 2 GiB.
- Target contesto esperto `98304` disponibile tramite `--target-ctx`, separato dalla scala automatica.
- Cache K/V `q8_0` fissata sul ramo CUDA con mmap; ramo CPU invariato.

### Known limitations

- L'evidenza della calibrazione è `GATE-PARTIAL`: manca una ripetizione su hardware materialmente
  diverso.
- CUDA è bloccato su host multi-GPU.
- I pesi non sono distribuiti né scaricati dal launcher.
- PyPI attende la configurazione del Trusted Publisher; gli artefatti GitHub sono pubblici.
- La serie 0.1 non garantisce stabilità di CLI, configurazione, record, procedure, prestazioni o
  compatibilità futura.
