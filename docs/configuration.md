# Configurazione e dati locali

## File e precedenza

La configurazione vive in `config_dir()/config.toml`. Le chiavi sono alla radice del documento:

```toml
model = "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M"
llama_port = 8080
open_browser = true
# model_path = "~/models/custom.gguf"
# engine_path = "~/bin/llama-server"
```

La precedenza è:

1. variabile ambiente;
2. `config.toml`;
3. default nel codice.

Il file TOML viene validato **interamente prima** di applicare gli override ambiente. Una chiave
sconosciuta o un valore malformato resta quindi un errore anche se sarebbe sostituito da una
variabile. Il launcher non crea e non riscrive mai automaticamente `config.toml`.

## Chiavi pubbliche

| Chiave | Variabile ambiente | Default | Vincolo |
|---|---|---|---|
| `model` | `QWEN_LAUNCHER_MODEL` | modello appuntato | stringa non vuota |
| `model_path` | `QWEN_LAUNCHER_MODEL_PATH` | assente | stringa percorso |
| `llama_port` | `QWEN_LAUNCHER_LLAMA_PORT` | `8080` | intero 1–65535 |
| `engine_path` | `QWEN_LAUNCHER_ENGINE_PATH` | assente | stringa percorso |
| `open_browser` | `QWEN_LAUNCHER_OPEN_BROWSER` | `true` | booleano |

Nel TOML i booleani devono essere `true` o `false`. Nell'ambiente sono accettati, senza distinzione
fra maiuscole e minuscole:

```text
true/false  1/0  yes/no  on/off
```

Una variabile `QWEN_LAUNCHER_MODEL_PATH` o `QWEN_LAUNCHER_ENGINE_PATH` presente ma vuota annulla il
percorso. Le altre variabili vuote sono errori. I percorsi espandono `~`, ma non sono verificati sul
filesystem durante il solo caricamento della configurazione.

Non sono accettate chiavi diverse da queste cinque; endpoint, bind address, mmproj e flag arbitrari
di `llama.cpp` non sono configurabili.

## Identità e percorso del modello

`model` è un'identità dichiarativa usata da lock, record e stato. `model_path` è il file fisico
passato al motore. Le combinazioni valide sono:

- modello predefinito + `model_path` assente: risoluzione dello snapshot Hugging Face appuntato;
- modello diverso + `model_path` esplicito: GGUF locale, senza calibrazione o garanzie ereditate.

Il modello predefinito con `model_path` esplicito viene rifiutato, così non è possibile sostituire
silenziosamente i byte mantenendo l'identità verificata. Un modello diverso senza percorso viene
rifiutato.

Per il modello predefinito la ricerca della cache segue l'ordine osservato nella release motore:

1. `LLAMA_CACHE`;
2. `HF_HUB_CACHE`;
3. `HUGGINGFACE_HUB_CACHE`;
4. `HF_HOME/hub`;
5. `XDG_CACHE_HOME/huggingface/hub`;
6. `~/.cache/huggingface/hub`.

Il launcher legge esclusivamente
`models--<repository>/snapshots/<revisione-appuntata>/<filename>` e verifica dimensione e SHA-256.
Non segue branch mobili e non modifica la cache.

## Risoluzione del motore

L'eseguibile viene cercato in quest'ordine:

1. `engine_path` esplicito;
2. `llama-server` / `llama-server.exe` nel `PATH`;
3. installazione gestita indicata da `data_dir()/engine/current.json`.

Ogni candidato deve superare i probe di versione e help di `engine.lock`. Un eseguibile trovato ma
incompatibile produce un errore: non viene saltato in favore del candidato successivo.

## Directory pubbliche

Le funzioni calcolano i percorsi senza creare directory.

| Radice | Ubuntu/Linux | Windows |
|---|---|---|
| configurazione | `${XDG_CONFIG_HOME:-~/.config}/qwen-launcher` | `%APPDATA%\qwen-launcher` |
| dati | `${XDG_DATA_HOME:-~/.local/share}/qwen-launcher` | `%LOCALAPPDATA%\qwen-launcher\data` |
| cache | `${XDG_CACHE_HOME:-~/.cache}/qwen-launcher` | `%LOCALAPPDATA%\qwen-launcher\cache` |
| stato | `${XDG_STATE_HOME:-~/.local/state}/qwen-launcher` | `%LOCALAPPDATA%\qwen-launcher\state` |

Una variabile XDG, `APPDATA` o `LOCALAPPDATA` assente, vuota o relativa usa il fallback; un valore
assoluto viene rispettato. Su Windows i fallback sono `~/AppData/Roaming` e `~/AppData/Local`.
`qwen-launcher doctor` stampa i quattro percorsi risolti per la macchina corrente.

## Layout dei dati

Le operazioni creano soltanto ciò che possiedono:

```text
config_dir()/
└── config.toml                         # scritto solo dall'utente

data_dir()/
├── engine/
│   ├── current.json                    # puntatore atomico al motore attivo
│   └── installations/<id>/             # installazioni immutabili
├── calibration/
│   ├── records/
│   │   ├── <modo>.json                 # record attivo
│   │   ├── <modo>.candidate.json       # candidato non attivo
│   │   └── <modo>.previous.json        # singolo slot precedente
│   └── evidence/<run-id>/              # log privati dell'ultimo run v4
└── calibrations/<bundle-id>/            # bundle redatti del laboratorio v1

cache_dir()/
└── llama.cpp/                           # download e staging gestiti del motore

state_dir()/
├── services.json                        # stato processi versione 1
├── start.lock                           # serializzazione degli avvii
└── logs/llama-server-<timestamp>.log
```

La directory `calibration/evidence` conserva un solo run UUID: dopo la promozione del nuovo run,
quelli precedenti gestiti vengono rimossi. I record sono privati e non sono contenuto della wheel.

## Cosa elimina `uninstall`

Dopo conferma vengono eliminate esattamente le quattro radici sopra. Sono esclusi:

- cache Hugging Face;
- GGUF e mmproj esterni;
- eseguibili indicati da `engine_path` o trovati nel `PATH`;
- uv, le sue cache e gli altri tool;
- qualunque percorso fuori dalle radici gestite.

Se il comando corrente appartiene esattamente all'ambiente `qwen-launcher` configurato da uv, la
stessa conferma pianifica anche la rimozione di quell'ambiente e del comando. Installazioni Python
esterne a `uv tool` restano invariate e vengono indicate nel resoconto.

**Successivo:** [Architettura](architecture.md)
