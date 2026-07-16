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
- accesso alle risorse compatibile con wheel/zip e test offline con server fake.

Lo **Spike 0 è completo** con decisione `GO`: `llama.cpp b10011`, il contratto macchina, la matrice
Ubuntu/Windows CPU/CUDA e il protocollo `benchmark/v1` sono verificati. Il contratto iniziale è
incluso nella wheel come `engine.lock`; gli asset restano intenzionalmente marcati incompleti fino
allo Step 4. Non esistono ancora profili di produzione e `coding` richiede un motore già presente.

Gli Step 1, 2A, 2B e 2C sono completi, inclusa la matrice CI Ubuntu/Windows. Lo Step 3 è implementato:
suite, build, wheel isolata, collaudo reale Ubuntu CUDA e matrice CI Ubuntu/Windows sono verdi;
resta aperto soltanto fino al collaudo reale Windows. Il catalogo profili vuoto è valido: `coding`
usa la baseline dello spike
senza presentarla come profilo ottimizzato. Il piano normativo e il tracker sono in
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
uv run --frozen qwen-launcher coding
uv run --frozen qwen-launcher status
uv run --frozen qwen-launcher stop
```

`coding` richiede già disponibili il modello e un `llama-server` compatibile con `engine.lock`: lo
Step 4 aggiungerà l'installazione gestita, quindi non viene ancora effettuato alcun download. Il
modello predefinito è risolto alla revisione snapshot appuntata nella cache Hugging Face e verificato
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
