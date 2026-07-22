# Changelog

Le modifiche rilevanti sono registrate qui per versione. I piani futuri non appartengono al
changelog: sono in `IMPLEMENTATION_SPEC.md`.

## [Unreleased]

### Fixed

- I server temporanei di calibrazione usano una porta loopback assegnata dal sistema quando
  `llama_port` è occupata; gli avvii normali continuano a richiedere la porta configurata.
- Il riuso di un record tollera al massimo 1 MiB di variazione nel totale RAM riportato, mantenendo
  invariati identità dei componenti e controlli di headroom RAM/VRAM.

### Changed

- La calibrazione v3 mostra trial in corso, avanzamento live ed ETA per fase sui terminali, conserva
  output lineare quando rediretta e riepiloga motivazione della selezione e headroom misurato.
- La documentazione è stata riscritta come percorso lineare per nuovi utenti e descrive soltanto il
  comportamento corrente.
- Le prove misurate sono state separate dai manuali sotto `evidence/`; audit e design superati sono
  stati rimossi.
- `IMPLEMENTATION_SPEC.md` conserva lo stato sintetico e il solo lavoro ancora da realizzare, senza
  i piani dettagliati delle milestone concluse.

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
