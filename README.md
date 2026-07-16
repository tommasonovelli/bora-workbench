# qwen-launcher

Distribuzione locale e riproducibile in sviluppo attorno a
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M` e a una release verificata di `llama.cpp`.

## Stato

Il repository contiene il vertical slice locale del modo `coding`:

- package Python 3.12 con layout `src/` e build `uv_build`;
- percorsi Linux/Windows senza side effect e configurazione severa;
- schemi, modi, report e profili validati semanticamente;
- rilevamento CPU, RAM e GPU NVIDIA senza modificare l'ambiente padre;
- matching esatto dei profili e baseline verificata ma non ottimizzata;
- risoluzione read-only del modello appuntato e verifica dell'eseguibile `llama-server`;
- builder governato esclusivamente da `engine.lock`;
- lifecycle con lock d'avvio, salute, stato atomico, log, `status` e `stop` sicuro;
- installazione motore da asset verificati, estrazione sicura e attivazione atomica via manifest;
- accesso alle risorse compatibile con wheel/zip e test offline con server fake.

Lo **Spike 0 è completo** con decisione `GO`: `llama.cpp b10011`, il contratto macchina, la matrice
Ubuntu/Windows CPU/CUDA e il protocollo `benchmark/v1` sono verificati. Il contratto e la matrice
completa degli asset sono inclusi nella wheel come `engine.lock`. Non esistono ancora profili di
produzione; `coding` può usare un motore esplicito, dal `PATH` o installato in modo gestito.

Gli Step 1, 2A, 2B, 2C e 3 sono completi. Suite, build, wheel isolata, matrice CI Ubuntu/Windows e
collaudi reali Ubuntu/Windows CUDA del vertical slice `coding`, `status` e `stop` sono verdi. Il
catalogo profili vuoto è valido: `coding` usa la baseline dello spike senza presentarla come profilo
ottimizzato. Lo Step 4 è implementato e resta aperto per i collaudi reali multipiattaforma e la CI;
non è iniziato lo Step 5. Il piano normativo e il tracker sono in
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
`--force` bypassa esclusivamente le soglie RAM del modello predefinito.

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
