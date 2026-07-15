# qwen-launcher

Scaffold iniziale di una distribuzione locale e riproducibile attorno a
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M` e a una release verificata di `llama.cpp`.

## Stato

Il repository contiene per ora il fondamento indipendente dal motore:

- package Python 3.12 con layout `src/` e build `uv_build`;
- percorsi Linux/Windows senza side effect;
- configurazione TOML e ambiente con validazione severa;
- CLI minima con `--version` e `doctor`;
- accesso alle risorse compatibile con wheel/zip;
- test, lint e CI Linux/Windows.

Lo **Spike 0 è completo** con decisione `GO`: `llama.cpp b10011`, il contratto macchina, la matrice
Ubuntu/Windows CPU/CUDA e il protocollo `benchmark/v1` sono verificati. Il contratto iniziale è
incluso nella wheel come `engine.lock`; gli asset restano intenzionalmente marcati incompleti fino
allo Step 4. Schemi, profili e comandi di avvio entrano soltanto negli step successivi.

Lo Step 1 è completo: implementazione, matrice CI Ubuntu/Windows e branch protection con revisione
code owner sono attive. Lo Step 2 è il prossimo passo e non è ancora iniziato. Il piano normativo e
il tracker aggiornato sono in [`IMPLEMENTATION_SPEC.md`](IMPLEMENTATION_SPEC.md); l'evidenza
verificata dello spike è sotto [`docs/spike-0/`](docs/spike-0/).

## Sviluppo

Prerequisiti: CPython 3.12.13 e uv 0.11.28.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher --version
uv run --frozen qwen-launcher doctor
```

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
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` |

Il launcher non crea né modifica automaticamente il file di configurazione.
