# qwen-launcher

`qwen-launcher` è una distribuzione locale e riproducibile per il modello appuntato
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`, servito da `llama.cpp b10011` con contratti e
asset verificati.

## Stato della release

La versione corrente è **`0.1.0rc1`**, un release candidate locale per lo Human Gate 0.1. Non è
ancora pubblicata su PyPI: non esiste quindi un one-liner PyPI supportato e gli installer non
scelgono una sorgente implicita. Il Gate umano deve ancora verificare Ubuntu 22.04 pulito, Windows
Sandbox, i tre modi, calibrazione, riuso e disinstallazione prima della decisione `RELEASE`.

Gli Step 0–5B sono conclusi. Il Gate `calibration/v3` è accettato localmente sui tre modi Windows
11/CUDA; la copertura empirica resta `GATE-PARTIAL` perché manca hardware materialmente diverso.
D-047 rende quel follow-up non bloccante, senza trasformare il risultato della macchina 32/8 in una
busta trasferibile. Stato ed evidenza sono in
[`docs/calibration-gate-v3-windows.md`](docs/calibration-gate-v3-windows.md).

## Funzionalità 0.1

- modi `coding`, `studio` e `vstudio`, con UI e vision abilitate o disabilitate esplicitamente;
- configurazione severa e percorsi nativi Ubuntu/Windows senza side effect all'import;
- rilevamento CPU, RAM e NVIDIA con una sola GPU CUDA selezionata nel solo ambiente figlio;
- modello e mmproj risolti in sola lettura alla revisione e ai digest appuntati;
- installazione sicura di `llama.cpp`, checksum obbligatori e attivazione atomica via manifest;
- lifecycle con salute, log, stato atomico, lock d'avvio, `status` e `stop` identity-safe;
- calibrazione locale v3 con RAM/VRAM, screening, round ABBA e record candidato/attivo/previous;
- policy/report condivisi usati soltanto per ordinare probe, mai come `LaunchPlan` remoto;
- `validate`, `doctor`, bundle privacy-safe e `uninstall` confinato alle directory gestite.

Open WebUI, skill, router e benchmark autonomo appartengono alla roadmap 0.2 e non sono inclusi.

## Requisiti supportati

- Ubuntu 22.04 o superiore x86-64, oppure Windows 11 x86-64;
- CPU oppure una singola GPU NVIDIA CUDA esplicitamente selezionata;
- almeno 28 GiB di RAM totale e 22 GiB disponibili per il gate del modello predefinito;
- modello e mmproj appuntati già presenti nella cache Hugging Face, oppure `model_path` esplicito per
  un modello diverso;
- spazio per modello, mmproj, motore e log. I pesi appuntati occupano 22.663.387.424 byte e il mmproj
  902.822.528 byte; il launcher non li redistribuisce né gestisce la cache Hugging Face;
- rete HTTPS per installare uv/dipendenze o il motore quando non si usano artefatti già disponibili.

CUDA su host multi-GPU resta bloccato: lo Spike 0 ha verificato soltanto una macchina con una GPU.
`--force` bypassa esclusivamente il gate RAM del modello predefinito.

## Installare il release candidate locale

Gli script appuntano uv `0.11.28` e CPython `3.12.13`. Prima della pubblicazione richiedono una
sorgente esplicita. Per un artefatto RC trasferito, verificare il digest comunicato separatamente:

```bash
sha256sum dist/qwen_launcher-0.1.0rc1-py3-none-any.whl
sh ./install.sh \
  --wheel dist/qwen_launcher-0.1.0rc1-py3-none-any.whl \
  --sha256 <64-hex-verificato>
```

```powershell
(Get-FileHash .\dist\qwen_launcher-0.1.0rc1-py3-none-any.whl -Algorithm SHA256).Hash
.\install.ps1 `
  -Wheel .\dist\qwen_launcher-0.1.0rc1-py3-none-any.whl `
  -Sha256 <64-hex-verificato>
```

Per un collaudo da commit esatto è disponibile `--git-commit <40-hex>` / `-GitCommit <40-hex>`.
`--pypi-version` / `-PypiVersion` è ammesso soltanto per una versione già realmente pubblicata.
Rieseguire lo stesso comando è sicuro; una versione uv diversa nel `PATH` non viene usata: lo script
installa e invoca quella appuntata tramite l'installer ufficiale versionato, senza elevazione.

La procedura RC, il workflow OIDC e il cancello umano sono descritti in
[`docs/releasing.md`](docs/releasing.md).

## Primo avvio

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
qwen-launcher engine install
qwen-launcher calibrate --mode all
qwen-launcher coding
```

`engine install` usa soltanto gli asset HTTPS e i digest di `engine.lock`. Su Ubuntu CUDA compila il
solo server dal commit appuntato e, se mancano prerequisiti, stampa i comandi da eseguire senza
installare pacchetti. Dettagli: [`docs/engine-lock.md`](docs/engine-lock.md).

Senza record locale compatibile, hardware idoneo usa la baseline verificata `ctx=8192`, dichiarata
non ottimizzata. `calibrate` misura invece la macchina corrente. Per il Gate o per ispezionare un
candidato senza attivarlo:

```bash
qwen-launcher calibrate --mode all --no-activate
qwen-launcher calibrate --mode coding --activate
```

La guida completa è [`docs/calibration.md`](docs/calibration.md). Il contributo di evidenza resta
manuale e separato: [`docs/calibration-contributing.md`](docs/calibration-contributing.md).

## Modi e servizi

```bash
qwen-launcher coding    # API locale, UI off, vision off
qwen-launcher studio    # UI integrata testuale, vision off
qwen-launcher vstudio   # UI integrata e mmproj vision
qwen-launcher status
qwen-launcher stop
```

I servizi ascoltano soltanto su `127.0.0.1`. `studio` e `vstudio` aprono il browser solo dopo READY
quando `open_browser=true`. Anatomia dei contratti:
[`mode/v1`](docs/anatomy/mode.md) e [`profile/v1`](docs/anatomy/profile.md).

## Configurazione

File: `config_dir()/config.toml`. La precedenza è ambiente > TOML > default; chiavi sconosciute o
valori malformati sono errori.

| Chiave | Variabile ambiente | Default |
|---|---|---|
| `model` | `QWEN_LAUNCHER_MODEL` | modello appuntato |
| `model_path` | `QWEN_LAUNCHER_MODEL_PATH` | `None` |
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` | `8080` |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` | `None` |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` | `true` |

Il launcher non modifica mai automaticamente `config.toml`.

## Privacy e sicurezza

- nessun servizio viene esposto su `0.0.0.0`;
- nessun test usa rete, GPU, modello o server reale;
- download motore con TLS e SHA-256 obbligatori, estrazione confinata e nessuna elevazione;
- niente credenziali, hostname, username o percorsi assoluti nei report condivisibili;
- record, log e configurazione locali non vengono caricati automaticamente;
- la cache Hugging Face non viene modificata o rimossa, neppure da `uninstall`;
- identità processo = `pid + create_time`; stato obsoleto non autorizza a terminare processi estranei;
- report condivisi e profili storici non sostituiscono una calibrazione locale compatibile.

Consultare anche [`docs/troubleshooting.md`](docs/troubleshooting.md) e il modello di sicurezza
normativo in `IMPLEMENTATION_SPEC.md` sezione 5.

## Disinstallare dati e tool

```bash
qwen-launcher stop
qwen-launcher uninstall
uv tool uninstall qwen-launcher
```

`uninstall` mostra config, dati, cache e stato esatti e richiede conferma. Non cancella il tool
stesso e non tocca mai la cache Hugging Face. Se un servizio è ancora attivo, fermarlo prima per non
lasciare un processo senza stato gestito.

## Benchmark

`benchmark/v1` è riusato internamente dalla calibrazione: un warm-up escluso e cinque misure da 256
token esatti. Non misura qualità semantica e non prova portabilità o optimum globale. La 0.1 non
espone ancora un comando benchmark autonomo. Vedere [`docs/benchmarks.md`](docs/benchmarks.md).

## Sviluppo

Prerequisiti di sviluppo: CPython `3.12.13` e uv `0.11.28`.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
uv build
uv run --frozen python scripts/verify_wheel.py
```

La CI esegue la matrice Ubuntu/Windows. Le regole di contribuzione sono in
[`CONTRIBUTING.md`](CONTRIBUTING.md); `IMPLEMENTATION_SPEC.md` resta l'unico piano normativo.

## Roadmap 0.2

Dopo la stabilizzazione della 0.1: skill dichiarative e router a frasi, Open WebUI appuntata e
isolata, sync locale, benchmark autonomo e doctor definitivo. Nessuna funzione 0.2 viene anticipata
nel release candidate 0.1.

## Licenze

Il launcher è MIT. Le installazioni gestite conservano il testo MIT di `llama.cpp` e, su Windows
CUDA, la NVIDIA CUDA Toolkit EULA richiesta. Modello e mmproj restano sotto la licenza del modello e
non sono redistribuiti.
