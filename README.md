# qwen-launcher

Distribuzione locale e riproducibile in sviluppo attorno a
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M` e a una release verificata di `llama.cpp`.

## Stato

Il repository contiene i tre modi locali `coding`, `studio` e `vstudio`:

- package Python 3.12 con layout `src/` e build `uv_build`;
- percorsi Linux/Windows senza side effect e configurazione severa;
- schemi, modi, report e profili validati semanticamente;
- rilevamento CPU, RAM e GPU NVIDIA senza modificare l'ambiente padre;
- profili v1 validabili ma solo come seed; baseline verificata e non ottimizzata per l'avvio;
- risoluzione read-only del modello appuntato e verifica dell'eseguibile `llama-server`;
- builder governato esclusivamente da `engine.lock`;
- lifecycle con lock d'avvio, salute, stato atomico, log, `status` e `stop` sicuro;
- UI integrata esplicita per `studio` e `vstudio`, con mmproj appuntato per la vision;
- installazione motore da asset verificati, estrazione sicura e attivazione atomica via manifest;
- accesso alle risorse compatibile con wheel/zip e test offline con server fake.

Lo **Spike 0 è completo** con decisione `GO`: `llama.cpp b10011`, il contratto macchina, la matrice
Ubuntu/Windows CPU/CUDA e il protocollo `benchmark/v1` sono verificati. Il contratto e la matrice
completa degli asset sono inclusi nella wheel come `engine.lock`. Non esistono ancora profili di
produzione; ogni modo può usare un motore esplicito, dal `PATH` o installato in modo gestito.

Gli Step 1–4 sono completi. Suite, build, wheel isolata, matrice CI Ubuntu/Windows e collaudi reali
previsti dai relativi gate sono verdi. Il catalogo profili vuoto è valido: i tre modi usano la
baseline dello spike senza presentarla come profilo ottimizzato. Lo Step 5 è completo: chat e vision
sono collaudate realmente su Ubuntu e Windows CUDA e la matrice CI Ubuntu/Windows è verde. Lo Step
5A conserva il protocollo di laboratorio `calibration/v1` e implementa ora `calibration/v2`: ricerca
locale adattiva a zero input tecnici obbligatori, monitoraggio RAM/VRAM, conferma dei finalisti e
record locale riutilizzabile soltanto sulla macchina e sui contratti che lo hanno misurato. Il
mini-spike Ubuntu e lo smoke Windows CUDA 13.3 hanno dato GO a cache KV Q8 con `--mmap` (NO-GO a
`--no-mmap`) e il contratto CUDA del lock ora la imposta; il dominio di `n_cpu_moe` sul modello
appuntato è verificato (`[0, 41]`). Progettazione e vincoli del v2 sono in
[`docs/calibration-v2-design.md`](docs/calibration-v2-design.md) (D-038/D-039). Lo Step 5B resta
chiuso fino al Calibration Gate reale e ad almeno un esito `CALIBRATION-ACCEPTED`. Il piano
normativo e il tracker sono in
[`IMPLEMENTATION_SPEC.md`](IMPLEMENTATION_SPEC.md); l'evidenza verificata dello spike è sotto
[`docs/spike-0/`](docs/spike-0/).

## Sviluppo

Prerequisiti: CPython 3.12.13 e uv 0.11.28.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher --version
uv run --frozen qwen-launcher validate
uv run --frozen qwen-launcher doctor
uv run --frozen qwen-launcher engine install
uv run --frozen qwen-launcher engine status
uv run --frozen qwen-launcher coding
uv run --frozen qwen-launcher studio
uv run --frozen qwen-launcher vstudio
uv run --frozen qwen-launcher calibrate --mode coding
uv run --frozen qwen-launcher validate --path <bundle>
uv run --frozen qwen-launcher status
uv run --frozen qwen-launcher stop
```

`engine install` scarica tramite HTTPS esclusivamente gli asset del lock per OS/backend rilevato,
verifica SHA-256, conserva gli avvisi di terze parti e attiva un'installazione immutabile tramite
`current.json`. Su Ubuntu CUDA controlla i prerequisiti e compila il solo server dal commit
appuntato, senza installare pacchetti. Dettagli e procedura di aggiornamento sono in
[`docs/engine-lock.md`](docs/engine-lock.md). Il modello predefinito è risolto alla revisione snapshot
appuntata nella cache Hugging Face e verificato
per nome, dimensione e SHA-256. Un modello diverso richiede `model_path` esplicito. CUDA su host
multi-GPU resta bloccato perché lo Spike 0 ha verificato soltanto una macchina a GPU singola.
`--force` bypassa esclusivamente le soglie RAM del modello predefinito. `studio` abilita la UI
integrata testuale; `vstudio` abilita anche il mmproj verificato. Entrambi mostrano URL UI/API e log
e aprono la UI dopo READY quando `open_browser=true`. `calibrate --mode <id|all>` usa per default
`calibration/v2`, cerca localmente e salva un record privato per modo; `--protocol v1` mantiene il
laboratorio con candidati e criteri espliciti e genera soltanto una bozza condivisibile. I dati
condivisi restano seed o evidenza, mai una busta finale trasferita per classe. Il modello resta
`UD-Q4_K_M`: il ramo CUDA del lock usa cache KV Q8 con mmap dopo i GO Ubuntu e Windows;
`--no-mmap` è stato rifiutato dalle misure. Protocollo, sintassi, record e privacy sono descritti in
[`docs/calibration.md`](docs/calibration.md). Open WebUI non fa parte della 0.1.

Build e verifica isolata:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
```

## Configurazione 0.1

File: `config_dir()/config.toml`. Le chiavi sono alla radice e la precedenza è ambiente, file,
default nel codice.

| Chiave | Variabile |
|---|---|
| `model` | `QWEN_LAUNCHER_MODEL` |
| `model_path` | `QWEN_LAUNCHER_MODEL_PATH` |
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` |

`model` è l'identità stabile usata dai profili; `model_path` è un eventuale file GGUF locale. Per il
modello predefinito il percorso viene risolto nello Step 3 dalla revisione snapshot appuntata nel
lock, senza rete né modifiche alla cache Hugging Face. Il launcher non crea né modifica
automaticamente il file di configurazione.

## Licenza

Il progetto è distribuito con licenza [MIT](LICENSE). Le installazioni gestite del motore
conservano gli avvisi di terze parti richiesti: il testo MIT di `llama.cpp` e, solo su Windows
CUDA, la NVIDIA CUDA Toolkit EULA. Il modello resta sotto la propria licenza Apache-2.0 e non
viene redistribuito dal launcher.
