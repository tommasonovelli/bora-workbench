# qwen-launcher

[![CI](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/tommasonovelli/qwen-launcher.svg)](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.3)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-31213/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`qwen-launcher` installa, calibra e governa in locale una configurazione precisa di Qwen e
`llama.cpp`. È pensato per chi vuole avviare il modello senza ricostruire ogni volta flag, checksum,
profili e lifecycle del server.

Il progetto fissa:

- modello `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`;
- `llama.cpp b10011` al commit verificato;
- tre modalità d'uso (`coding`, `studio`, `vstudio`);
- installazione sicura del motore;
- calibrazione locale per la macchina corrente;
- stato, log, health check e stop identity-safe.

Non è un model manager generico e non esegue plugin. I servizi ascoltano soltanto su `127.0.0.1`.

## Inizia da qui

Se è la prima volta che apri il progetto, il percorso più semplice è:

1. controlla i [requisiti](#requisiti);
2. [installa la release](#installazione);
3. rendi disponibile il [modello appuntato](#modello);
4. esegui `engine install`;
5. avvia `coding` oppure calibra prima la macchina;
6. usa la [documentazione completa](docs/README.md) quando vuoi capire configurazione e dettagli.

## Stato del progetto

> [!WARNING]
> La serie `0.1` è destinata a valutazione. CLI, configurazione, formati dei record, procedure e
> prestazioni non hanno garanzia di stabilità. Non usarla per workload critici senza verifiche
> indipendenti e backup dei dati locali.

La release corrente è **`0.1.3`**, pubblicata su
[GitHub Releases](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.3). Mantiene
`calibration/v5` come default, corregge la precedenza degli errori di cleanup, disabilita
prudentemente MTP per `vstudio` e distribuisce nello sdist il pacchetto dello spike cross-context.
`calibration/v6-lite` resta bloccata fino a un verdetto umano GO. PyPI resta indisponibile.

## Requisiti

- Ubuntu 22.04+ x86-64 oppure Windows 11 x86-64;
- CPU oppure una singola GPU NVIDIA CUDA;
- almeno **28 GiB RAM totali** e **22 GiB disponibili** per il modello predefinito;
- spazio per GGUF (22.663.387.424 byte), mmproj (902.822.528 byte), motore e log;
- modello già presente nella cache Hugging Face appuntata;
- rete HTTPS per installare tool e motore, salvo artefatti già disponibili.

CUDA su host multi-GPU è bloccato perché l'isolamento è stato verificato solo su host a GPU singola.
Se `nvidia-smi` non è disponibile o affidabile, il launcher usa CPU e mostra un warning.

## Installazione

La release allega wheel, sdist, installer e `SHA256SUMS` prodotti a partire dal run test/build
multipiattaforma. Usare il digest della wheel riportato nel manifest allegato.

### Ubuntu

```bash
base="https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.3"
wheel="qwen_launcher-0.1.3-py3-none-any.whl"
curl --fail --location "$base/install.sh" --output install.sh
curl --fail --location "$base/$wheel" --output "$wheel"
curl --fail --location "$base/SHA256SUMS" --output SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
wheel_sha256="$(awk -v wheel="$wheel" '$2 == wheel { print $1 }' SHA256SUMS)"
test "${#wheel_sha256}" -eq 64
sh ./install.sh --wheel "./$wheel" --sha256 "$wheel_sha256"
```

### Windows

Da PowerShell:

```powershell
$base = "https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.3"
$wheel = "qwen_launcher-0.1.3-py3-none-any.whl"
Invoke-WebRequest "$base/install.ps1" -OutFile install.ps1
Invoke-WebRequest "$base/$wheel" -OutFile $wheel
Invoke-WebRequest "$base/SHA256SUMS" -OutFile SHA256SUMS
$pattern = "^[0-9a-f]{64}\s+$([regex]::Escape($wheel))$"
$entry = Select-String -Path .\SHA256SUMS -Pattern $pattern
if ($null -eq $entry) { throw "Wheel digest missing from SHA256SUMS" }
$sha256 = ($entry.Line -split "\s+")[0]
if ((Get-FileHash $wheel -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha256) {
  throw "Wheel SHA-256 mismatch"
}
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Wheel ".\$wheel" -Sha256 $sha256
```

Gli installer fissano uv `0.11.28` e CPython `3.12.13`, richiedono una sorgente esplicita e non
usano privilegi amministrativi. Dettagli e alternative sono in
[Installazione e primo avvio](docs/installation.md).

Verifica subito:

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
```

## Modello

I pesi non sono inclusi e il launcher non li scarica. Per il modello predefinito legge in sola
lettura lo snapshot Hugging Face della revisione `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d` e verifica
nome, dimensione e SHA-256 di:

```text
Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
mmproj-BF16.gguf
```

Il mmproj serve solo a `vstudio`. I file vanno acquisiti separatamente dalla
[revisione fissata del repository](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/tree/5bc3e238d916f48a861bac2f8a1990a0e9b7e98d)
con uno strumento scelto dall'utente. La cache Hugging Face non viene modificata né rimossa da
`uninstall`.

## Primo avvio

Installa il motore adatto all'hardware rilevato:

```bash
qwen-launcher engine install
qwen-launcher engine status
```

Poi puoi partire subito con la baseline verificata:

```bash
qwen-launcher coding
```

La baseline usa `ctx=8192` e, su CUDA, `n_cpu_moe=48`. È funzionale ma non ottimizzata.

Per misurare prima il PC e attivare una configurazione locale per tutti i modi:

```bash
qwen-launcher calibrate --mode all
```

La calibrazione può durare a lungo e avvia molti processi temporanei; mostra sempre un preflight e
chiede conferma. Leggi [Calibrazione locale](docs/calibration.md) prima di eseguirla.

## Concetti in un minuto

- **Motore**: l'eseguibile `llama-server` della release fissata.
- **Modo**: comportamento del servizio (UI, vision e sampling).
- **Baseline**: configurazione verificata usata quando manca una calibrazione locale.
- **Record locale**: risultato privato della calibrazione su questo PC e per un solo modo.
- **Seed condiviso**: suggerimento sull'ordine delle prove; non copia la configurazione di un altro
  PC.

Il launcher usa un record solo se macchina, modello, motore, modo e memoria corrente sono ancora
compatibili. In caso contrario spiega il motivo e torna alla baseline.

## Modi disponibili

| Comando | Esperienza |
|---|---|
| `qwen-launcher coding` | API OpenAI-compatible testuale, UI e vision disabilitate |
| `qwen-launcher studio` | chat testuale nella UI integrata di llama.cpp |
| `qwen-launcher vstudio` | UI integrata con proiettore vision appuntato |

Dopo READY la CLI mostra URL API/UI e log. `studio` e `vstudio` aprono il browser solo se
`open_browser=true`. Il processo rimane in foreground; `Ctrl-C` lo ferma e pulisce lo stato.

Controllo da un altro terminale:

```bash
qwen-launcher status
qwen-launcher stop
```

## Configurazione minima

Il file è `config_dir()/config.toml`; la precedenza è ambiente > TOML > default.

```toml
llama_port = 8080
open_browser = true
```

Le chiavi disponibili sono `model`, `model_path`, `llama_port`, `engine_path` e `open_browser`.
Chiavi sconosciute e valori malformati sono errori; il launcher non riscrive il file.

Vedere [Configurazione e dati locali](docs/configuration.md) per percorsi Linux/Windows, variabili
ambiente e layout dei record.

## Sicurezza e privacy

- bind esclusivo a `127.0.0.1`;
- HTTPS e SHA-256 obbligatori per gli asset;
- estrazione confinata e attivazione atomica del motore;
- nessun `shell=True`, `sudo` o elevazione automatica;
- stop basato su `pid + create_time`, non sul solo PID;
- `CUDA_VISIBLE_DEVICES` solo nell'ambiente figlio;
- config, record e log mai caricati automaticamente;
- cache Hugging Face mai modificata o eliminata.

## Documentazione

La [documentazione completa](docs/README.md) segue un percorso per chi parte da zero:
installazione → comandi → configurazione → architettura → calibrazione → operazioni → sviluppo →
release.

Il lavoro non ancora implementato vive soltanto in [IMPLEMENTATION_SPEC.md](IMPLEMENTATION_SPEC.md).
Le prove misurate che sostengono lock e report sono separate in [`evidence/`](evidence/README.md).

## Sviluppo

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
```

Per packaging o risorse:

```bash
uv build
uv run --frozen python scripts/verify_wheel.py
```

Leggere [CONTRIBUTING.md](CONTRIBUTING.md) e [Sviluppo e contributi](docs/development.md) prima di
modificare il repository.

## Licenze

Il launcher è distribuito con licenza [MIT](LICENSE). Le installazioni gestite conservano la licenza
MIT di `llama.cpp` e, per Windows CUDA, la NVIDIA CUDA Toolkit EULA. Modello e mmproj non sono
redistribuiti e restano soggetti alla licenza del modello.
