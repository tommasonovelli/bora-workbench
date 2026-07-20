# qwen-launcher

[![CI](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/tommasonovelli/qwen-launcher/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/tommasonovelli/qwen-launcher.svg)](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.0)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-31213/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`qwen-launcher` installa e governa una distribuzione locale e riproducibile del modello
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`, servito dall'esatta release verificata
`llama.cpp b10011`.

Non è un model manager generico: modello, motore, flag, salute, modi e protocollo di calibrazione
sono vincolati da lock e contratti versionati. I servizi ascoltano soltanto su `127.0.0.1`.

## Stato e maturità

> [!WARNING]
> `0.1.0` è la **prima release pubblica**, destinata a valutazione ed early adopter. Non è garantita
> alcuna stabilità di CLI, configurazione, formati dei record, procedure operative, prestazioni o
> compatibilità con versioni future. Non usarla per workload critici senza verifiche indipendenti e
> senza conservare copie dei propri dati locali.

I test e i lock documentano ciò che è stato verificato sulla versione corrente; non costituiscono una
garanzia di disponibilità, assenza di difetti, qualità delle risposte del modello o prestazioni su
hardware diverso. Il software è fornito “as is” secondo la licenza MIT. Problemi e correzioni saranno
gestiti con nuove versioni, senza sostituire gli artefatti `0.1.0` già pubblicati.

## Installazione

La release corrente è **`0.1.0`**. Gli installer ufficiali fissano uv `0.11.28` e CPython `3.12.13`,
non richiedono privilegi amministrativi e verificano la wheel prima di installarla. PyPI è in attesa
della configurazione del Trusted Publisher; gli artefatti GitHub qui sotto sono già pubblici e sono
gli stessi costruiti e verificati dalla CI release su Ubuntu e Windows.

SHA-256 della wheel `0.1.0`:

```text
8966539a9e257f532d14fab821bf507a9c0327fa7fb246e5d8803fa69289c482
```

### Ubuntu 22.04+

```bash
base="https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.0"
curl --fail --location "$base/install.sh" --output install.sh
curl --fail --location "$base/qwen_launcher-0.1.0-py3-none-any.whl" \
  --output qwen_launcher-0.1.0-py3-none-any.whl
sh ./install.sh \
  --wheel ./qwen_launcher-0.1.0-py3-none-any.whl \
  --sha256 8966539a9e257f532d14fab821bf507a9c0327fa7fb246e5d8803fa69289c482
```

### Windows 11

Da PowerShell:

```powershell
$base = "https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.0"
Invoke-WebRequest "$base/install.ps1" -OutFile install.ps1
Invoke-WebRequest "$base/qwen_launcher-0.1.0-py3-none-any.whl" `
  -OutFile qwen_launcher-0.1.0-py3-none-any.whl
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Wheel .\qwen_launcher-0.1.0-py3-none-any.whl `
  -Sha256 8966539a9e257f532d14fab821bf507a9c0327fa7fb246e5d8803fa69289c482
```

`ExecutionPolicy Bypass` vale soltanto per quel processo e non modifica la policy di sistema.

### Se uv è già installato

```bash
uv tool install --python 3.12.13 \
  "qwen-launcher @ https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.0/qwen_launcher-0.1.0-py3-none-any.whl"
```

Verificare subito l'installazione:

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
```

La pagina [GitHub Releases](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.0)
contiene installer, wheel, sdist e `SHA256SUMS`. Per l'installazione da commit Git completo e lo stato
della pubblicazione PyPI consultare [la procedura di release](docs/releasing.md).

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
