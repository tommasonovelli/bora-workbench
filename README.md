# qwen-launcher

[![CI](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/qwen-launcher.svg)](https://pypi.org/project/qwen-launcher/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-31213/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`qwen-launcher` installa e governa una distribuzione locale e riproducibile del modello
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`, servito dall'esatta release verificata
`llama.cpp b10011`.

Non è un model manager generico: modello, motore, flag, salute, modi e protocollo di calibrazione
sono vincolati da lock e contratti versionati. I servizi ascoltano soltanto su `127.0.0.1`.

## Installazione

La release corrente è **`0.1.0`**. Gli installer ufficiali fissano uv `0.11.28` e CPython `3.12.13`,
non richiedono privilegi amministrativi e richiedono sempre una sorgente/versione esplicita.

### Ubuntu 22.04+

```bash
curl --fail --location \
  https://raw.githubusercontent.com/tommasonovelli/qwen-launcher/v0.1.0/install.sh \
  --output install.sh
sh ./install.sh --pypi-version 0.1.0
```

### Windows 11

Da PowerShell:

```powershell
Invoke-WebRequest `
  https://raw.githubusercontent.com/tommasonovelli/qwen-launcher/v0.1.0/install.ps1 `
  -OutFile install.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -PypiVersion 0.1.0
```

`ExecutionPolicy Bypass` vale soltanto per quel processo e non modifica la policy di sistema.

### Se uv è già installato

```bash
uv tool install --python 3.12.13 "qwen-launcher==0.1.0"
```

Verificare subito l'installazione:

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
```

La pagina [GitHub Releases](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.0)
contiene anche wheel, sdist e checksum. Per installazioni verificabili da wheel o commit Git completo,
consultare [la procedura di release](docs/releasing.md).

## Requisiti

- Ubuntu 22.04+ x86-64 oppure Windows 11 x86-64;
- CPU oppure una singola GPU NVIDIA CUDA;
- almeno **28 GiB di RAM totale** e **22 GiB disponibili** per il modello predefinito;
- modello e mmproj appuntati già presenti nella cache Hugging Face, oppure `model_path` esplicito per
  un modello diverso;
- spazio per modello, mmproj, motore e log;
- rete HTTPS per installare dipendenze e motore, salvo disponibilità locale degli artefatti.

I pesi non sono inclusi: il GGUF appuntato occupa 22.663.387.424 byte e il mmproj 902.822.528 byte.
Il launcher verifica revisione, dimensione e SHA-256 senza modificare la cache Hugging Face.

CUDA su host multi-GPU resta bloccato perché la selezione fisica è stata verificata soltanto su host
a GPU singola. La copertura empirica della calibrazione resta `GATE-PARTIAL`: il metodo è stato
accettato localmente su Windows 11/CUDA per i tre modi, ma manca ancora una prova su hardware
materialmente diverso.

## Primo avvio

```bash
qwen-launcher engine install
qwen-launcher doctor
qwen-launcher calibrate --mode all
qwen-launcher coding
```

`engine install` scarica o costruisce soltanto gli asset descritti da `engine.lock`, ne verifica i
checksum e attiva il motore tramite un manifest atomico. Su Ubuntu CUDA, se mancano prerequisiti di
compilazione, il launcher mostra i comandi necessari ma non esegue `sudo` o package manager.

La calibrazione è locale e potenzialmente lunga. Senza un record locale compatibile, il launcher usa
la baseline verificata `ctx=8192`, dichiarandola non ottimizzata. Per misurare senza attivare il
risultato:

```bash
qwen-launcher calibrate --mode all --no-activate
```

Dettagli: [motore](docs/engine-lock.md) e [calibrazione](docs/calibration.md).

## Modi disponibili

| Comando | UI | Vision | Uso principale |
|---|---:|---:|---|
| `qwen-launcher coding` | no | no | API locale per coding e integrazioni |
| `qwen-launcher studio` | sì | no | chat nella UI integrata di llama.cpp |
| `qwen-launcher vstudio` | sì | sì | chat e input immagine tramite mmproj |

Comandi di controllo:

```bash
qwen-launcher status
qwen-launcher stop
```

`studio` e `vstudio` aprono il browser soltanto dopo lo stato READY e solo quando
`open_browser=true`. Open WebUI, skill e router appartengono alla roadmap 0.2.

## Configurazione

Il file è `config_dir()/config.toml`. La precedenza è **ambiente > TOML > default**; chiavi
sconosciute e valori malformati sono errori. Il launcher non modifica mai automaticamente il file.

| Chiave | Variabile ambiente | Default |
|---|---|---|
| `model` | `QWEN_LAUNCHER_MODEL` | modello appuntato |
| `model_path` | `QWEN_LAUNCHER_MODEL_PATH` | `None` |
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` | `8080` |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` | `None` |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` | `true` |

Un modello diverso richiede `model_path` esplicito e non eredita gate, record o calibrazione del
modello predefinito.

## Dati locali e disinstallazione

```bash
qwen-launcher stop
qwen-launcher uninstall
uv tool uninstall qwen-launcher
```

`uninstall` mostra in anteprima le radici gestite, richiede conferma e rifiuta servizi vivi, symlink
o percorsi alterati. Non cancella mai la cache Hugging Face. La rimozione del tool Python resta
separata tramite uv.

## Sicurezza e privacy

- nessun bind implicito su `0.0.0.0`;
- download HTTPS e SHA-256 obbligatori;
- estrazione degli archivi confinata e nessuna elevazione automatica;
- identità processo basata su `pid + create_time`;
- `CUDA_VISIBLE_DEVICES` impostata soltanto nell'ambiente del processo figlio;
- configurazione, record e log locali mai caricati automaticamente;
- bundle condivisibili redatti e validati contro hostname, username e percorsi assoluti;
- report pubblici usati soltanto per ordinare la ricerca, mai come busta calibrata remota.

Per errori di installazione, modello, RAM, CUDA, porte o record consultare
[troubleshooting](docs/troubleshooting.md).

## Sviluppo

Prerequisiti: CPython `3.12.13` e uv `0.11.28`.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
uv build
uv run --frozen python scripts/verify_wheel.py
```

I test sono deterministici e non usano rete, GPU, modello o server reali. La CI copre Ubuntu e
Windows. Leggere [CONTRIBUTING.md](CONTRIBUTING.md) prima di modificare il progetto;
`IMPLEMENTATION_SPEC.md` resta l'unico piano normativo.

## Licenze

Il launcher è distribuito con licenza [MIT](LICENSE). Le installazioni gestite conservano il testo
MIT di `llama.cpp` e, su Windows CUDA, la NVIDIA CUDA Toolkit EULA richiesta. Modello e mmproj non
sono redistribuiti e restano soggetti alla licenza del modello.
