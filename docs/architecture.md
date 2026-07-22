# Architettura

## Scopo del prodotto

`qwen-launcher` è un launcher specializzato, non un model manager generico. Governa una combinazione
precisa di:

- modello Qwen predefinito e proiettore vision;
- release verificata di `llama.cpp`;
- tre modi dichiarativi;
- rilevamento CPU/CUDA;
- calibrazione locale per modo;
- installazione e lifecycle sicuri del processo.

Il core decide **come** validare, misurare e governare. I JSON versionati dichiarano **quali** modi,
contratti e prove condivise sono disponibili. Nessun contenuto esegue codice arbitrario.

## Flusso di un avvio

```text
CLI
 └─ configurazione severa
     └─ rilevamento hardware
         └─ gate RAM e supporto GPU
             └─ catalogo dichiarativo validato
                 └─ risoluzione e verifica del modello
                     └─ record locale compatibile oppure baseline
                         └─ LaunchPlan immutabile
                             └─ risoluzione e probe del motore
                                 └─ comando espanso solo da engine.lock
                                     └─ stato + processo + health check
                                         └─ endpoint READY in foreground
```

Un errore interrompe il flusso nel punto in cui viene rilevato. Non esistono fallback silenziosi verso
modelli, release, flag, porte o asset diversi.

## Componenti del repository

| Area | Responsabilità corrente |
|---|---|
| `cli.py`, `_cli_*` | input Typer, presentazione Rich, conferme ed exit code |
| `paths.py` | calcolo delle quattro radici per OS, senza creazione |
| `config.py`, `_config_paths.py` | TOML, ambiente, precedenza e tipi |
| `hardware.py`, `_hardware_monitoring.py` | CPU/RAM, NVIDIA, processi GPU e telemetria |
| `profiles.py`, `_profile_*` | modi runtime, seed condivisi, gate e `LaunchPlan` |
| `engine.py`, `_engine_*` | lock, modello, asset, download/build, installazione e comando |
| `process.py`, `_process_*` | porta, lock di avvio, processo, salute, stato, status e stop |
| `calibration.py`, `_calibration_*` | laboratorio v1, ricerca v4, record, evidenza e riuso |
| `benchmark.py` | protocollo immutabile `benchmark/v1` usato dalla calibrazione |
| `validation.py`, `_validation_*` | JSON Schema e invarianti semantiche incrociate |
| `resources/` | lock, schemi, modi, policy, report, benchmark e notice nella wheel |
| `install.sh`, `install.ps1` | installazione del tool da una sorgente esplicita |
| `scripts/verify_wheel.py` | verifica esterna di wheel e sdist |
| `tests/` | suite offline con fake di server, processi, rete e hardware |
| `.github/workflows/` | CI multipiattaforma e pubblicazione da artefatti testati |
| `evidence/` | output misurati e manifest di provenienza, fuori dai manuali |

Solo `paths.py`, `process.py`, `hardware.py` ed `engine.py` possiedono diramazioni di piattaforma. I
moduli privati separano responsabilità interne senza creare una API plugin.

## Risorse dichiarative

Le risorse sono lette con `importlib.resources` come `Traversable`; il codice non presume che una
wheel sia estratta su disco. Gli schemi sono JSON Schema 2020-12 e vietano proprietà non dichiarate.

| Contratto | Ruolo attuale |
|---|---|
| `mode/v1` | servizi e sampling dei modi |
| `profile/v1` | compatibilità con evidenza a classi; nessuna busta di produzione distribuita |
| `calibration-policy/v1` | contratto del laboratorio esplicito |
| `calibration-report/v1` | bundle del laboratorio v1 |
| `calibration-policy/v2` | metodo pubblico storico v3, usato da v4 solo per seed |
| `calibration-report/v2` | evidenza v3 privacy-safe e seed di ordine |
| `calibration-record/v2` | record privato storico prodotto da v3 |
| `calibration-record/v3` | record privato corrente prodotto da v4 |
| `engine-lock/v1` | identità, comando, API, salute e asset del motore |

Il catalogo installato contiene tre modi, una policy v3 storica e un report di riferimento. Non contiene
profili `profile/v1` di produzione. Il report condiviso espone al runtime soltanto
`seed_n_cpu_moe`: contesto, hardware, tok/s e busta osservata non possono entrare nel piano di un
altro host.

`qwen-launcher validate` meta-valida gli schemi, valida i documenti e ricostruisce i legami che JSON
Schema non può esprimere, inclusi digest, dominio, riserve, candidati e compatibilità col lock.

## Modi e piano di lancio

Un modo contiene comportamento, non prestazioni:

| Modo | UI | Vision | Temperatura | top-p | top-k |
|---|---:|---:|---:|---:|---:|
| `coding` | no | no | 0,6 | 0,95 | 20 |
| `studio` | sì | no | 0,7 | 0,8 | 20 |
| `vstudio` | sì | sì | 0,7 | 0,8 | 20 |

`LaunchPlan` fonde senza ambiguità:

- modo e sampling;
- identità e percorso fisico del modello;
- porta;
- backend e indice GPU;
- `ctx` e `n_cpu_moe` dal record attivo o dalla baseline;
- riferimenti diagnostici e warning.

Il piano usa un record solo se è un `calibration-record/v2` o `/v3` attivo per quel modo,
semanticamente valido e compatibile con modello, digest, release/commit/contratto motore, OS,
backend, componenti, driver e memoria corrente. Nel confronto del totale RAM è tollerata una deriva
massima di 1 MiB; headroom RAM/VRAM usa la riserva registrata dal protocollo del record.

Se il record manca o non è riusabile, la baseline è `ctx=8192` e, su CUDA, `n_cpu_moe=48`. È sempre
presentata come non ottimizzata. Le vecchie classi hardware e i report condivisi non producono
nearest-match.

## Hardware

Il rilevamento legge CPU e memoria tramite `psutil`. Per NVIDIA esegue senza shell, con timeout di 5
secondi:

```text
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader,nounits
```

Con più dispositivi sceglie quello con maggiore VRAM totale e, a parità, indice minore; l'avvio CUDA
viene comunque bloccato perché l'isolamento multi-GPU non è verificato. Su un host CUDA supportato
`CUDA_VISIBLE_DEVICES=<indice>` viene aggiunta soltanto all'ambiente figlio. L'ambiente del launcher
non viene modificato.

RAM e VRAM sono sempre GiB binari. Per il modello predefinito il gate richiede 28 GiB totali e 22
GiB disponibili. Modelli diversi non ricevono soglie inventate dal modello predefinito.

## Motore e modello

Il contratto corrente è:

```text
llama.cpp release: b10011
source commit:      bf2c86ddc0685f580595954056c2e77ebabfab4f
modello:            unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M
```

`engine.lock` è sia lock di asset sia linguaggio macchina del comando. Contiene:

- probe `--version` e `--help`;
- vocabolario completo dei flag ammessi;
- template per modello, contesto, sampling, rete, UI, vision e backend;
- endpoint API e risposta health esatta;
- URL HTTPS, ruoli, formati, eseguibili e SHA-256 degli asset.

Il builder espande solo placeholder noti. Il comando corrente fissa host `127.0.0.1`, metriche,
Jinja, flash attention, mmap, un solo slot, MTP e CORS `localhost`; abilita o disabilita UI e vision
esplicitamente. CUDA usa `-ngl 99`, il `n_cpu_moe` del piano e cache K/V `q8_0`; CPU non riceve
argomenti CUDA. I pesi restano `UD-Q4_K_M`: Q8 riguarda la cache KV.

Il modello predefinito è letto dallo snapshot della revisione appuntata e verificato per nome,
dimensione e digest. Non viene usato `--hf-repo`, quindi il launcher non risolve branch remoti e non
scrive nella cache Hugging Face.

### Installazione gestita

Gli asset vengono scaricati in file `.part` univoci sotto la cache gestita. L'estrazione rifiuta
percorsi assoluti, drive, `..`, file speciali e link in fuga. I soli symlink ammessi sono quelli
relativi, confinati e presenti nel tar Ubuntu verificato.

Ogni risultato passa da staging a una directory nuova sotto:

```text
data_dir()/engine/installations/
```

L'attivazione sostituisce atomicamente `data_dir()/engine/current.json`, che contiene un percorso
relativo verificato come discendente. Un errore di download, hash, estrazione, build, probe o
attivazione lascia intatta l'installazione precedente.

## Processo e stato

Prima dell'avvio il launcher:

1. acquisisce `start.lock` con creazione esclusiva;
2. pulisce stato morto o con PID riutilizzato;
3. rifiuta un altro servizio gestito;
4. verifica che la porta configurata sia libera su loopback;
5. crea il log;
6. avvia `llama-server` senza shell e registra `pid + create_time`;
7. scrive `services.json` atomicamente;
8. rilascia il lock e attende READY.

Il polling health usa richieste da 2 secondi ogni secondo, fino a 15 minuti. Connessione rifiutata,
timeout, 503 e 5xx sono transitori. READY richiede HTTP 200 e corpo JSON esatto `{"status":"ok"}`;
4xx o un corpo 200 incompatibile falliscono immediatamente.

Lo stato ha versione 1 ed è sostituito tramite file temporaneo nella stessa directory, flush e
`replace`. Un JSON malformato viene rinominato, non sovrascritto. `status` e `stop` verificano sempre
`pid + create_time`; non terminano mai un processo basandosi sul solo PID.

## Calibrazione

La calibrazione usa gli stessi contratti di modello, comando, salute e workload del lancio, ma ogni
trial vive in uno stato isolato. La ricerca v4 monitora RAM e VRAM, usa processi freschi e produce
record privati atomici. Il benchmark non è un comando autonomo: è un componente interno eseguito su
ogni sessione di conferma.

Algoritmo, lifecycle dei record e limiti empirici sono descritti in
[Calibrazione](calibration.md).

## Confini di sicurezza e side effect

Importare `qwen_launcher` non usa rete, non crea directory, non scrive stato e non avvia processi.
Ogni side effect appartiene all'operazione che lo richiede.

Invarianti principali:

- nessun `shell=True`, `eval`, `exec`, `sudo` o elevazione automatica;
- nessun bind su `0.0.0.0`;
- TLS e checksum non disattivabili;
- cancellazioni limitate alle radici gestite;
- cache Hugging Face mai modificata o eliminata;
- config e record mai caricati in rete;
- processi estranei protetti dall'identità completa;
- test senza rete, GPU, modello o server reali.

Gli artefatti sotto [`evidence/`](../evidence/README.md) documentano ciò che è stato misurato; non
allargano il perimetro supportato oltre i lock e i claim espliciti.

**Successivo:** [Calibrazione locale](calibration.md)
