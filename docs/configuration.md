# Configuration and local data

## File and precedence

The configuration lives in `config_dir()/config.toml`. The keys sit at the root of the document:

```toml
model = "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M"
llama_port = 8080
open_browser = true
# model_path = "~/models/custom.gguf"
# engine_path = "~/bin/llama-server"
```

Precedence is:

1. environment variable;
2. `config.toml`;
3. code defaults.

The TOML file is validated **in full before** the environment overrides are applied. An unknown key
or a malformed value therefore stays an error even when a variable would replace it. The launcher
never creates or rewrites `config.toml` automatically.

## Public keys

| Key | Environment variable | Default | Constraint |
|---|---|---|---|
| `model` | `BORA_MODEL` | the pinned model | non-empty string |
| `model_path` | `BORA_MODEL_PATH` | absent | path string |
| `llama_port` | `BORA_LLAMA_PORT` | `8080` | integer 1–65535 |
| `engine_path` | `BORA_ENGINE_PATH` | absent | path string |
| `open_browser` | `BORA_OPEN_BROWSER` | `true` | boolean |

In TOML, booleans must be `true` or `false`. In the environment the following are accepted,
case-insensitively:

```text
true/false  1/0  yes/no  on/off
```

A `BORA_MODEL_PATH` or `BORA_ENGINE_PATH` variable that is present but empty
clears the path. Other empty variables are errors. Paths expand `~`, but they are not checked
against the filesystem while the configuration alone is being loaded.

No keys other than these five are accepted; endpoints, bind addresses, mmproj, and arbitrary
`llama.cpp` flags are not configurable.

## Model identity and path

`model` is a declarative identity used by locks, records, and state. `model_path` is the physical
file passed to the engine. The valid combinations are:

- default model + no `model_path`: resolution of the pinned Hugging Face snapshot;
- different model + explicit `model_path`: a local GGUF, with no inherited calibration or
  guarantees.

The default model with an explicit `model_path` is rejected, so the bytes cannot be silently
replaced while the verified identity is kept. A different model without a path is rejected.

For the default model the cache lookup follows the order observed in the engine release:

1. `LLAMA_CACHE`;
2. `HF_HUB_CACHE`;
3. `HUGGINGFACE_HUB_CACHE`;
4. `HF_HOME/hub`;
5. `XDG_CACHE_HOME/huggingface/hub`;
6. `~/.cache/huggingface/hub`.

The launcher reads only
`models--<repository>/snapshots/<pinned-revision>/<filename>` and verifies the size and SHA-256. It
does not follow moving branches and does not modify the cache.

## Engine resolution

The executable is looked up in this order:

1. an explicit `engine_path`;
2. `llama-server` / `llama-server.exe` on the `PATH`;
3. the managed installation pointed at by `data_dir()/engine/current.json`.

Every candidate must pass the version and help probes from `engine.lock`. An executable that is
found but incompatible produces an error: it is not skipped in favor of the next candidate.

## Public directories

The helpers compute the paths without creating any directory.

| Root | Ubuntu/Linux | Windows |
|---|---|---|
| configuration | `${XDG_CONFIG_HOME:-~/.config}/bora-workbench` | `%APPDATA%\bora-workbench` |
| data | `${XDG_DATA_HOME:-~/.local/share}/bora-workbench` | `%LOCALAPPDATA%\bora-workbench\data` |
| cache | `${XDG_CACHE_HOME:-~/.cache}/bora-workbench` | `%LOCALAPPDATA%\bora-workbench\cache` |
| state | `${XDG_STATE_HOME:-~/.local/state}/bora-workbench` | `%LOCALAPPDATA%\bora-workbench\state` |

An XDG, `APPDATA`, or `LOCALAPPDATA` variable that is missing, empty, or relative uses the fallback;
an absolute value is honored. On Windows the fallbacks are `~/AppData/Roaming` and
`~/AppData/Local`. `bora doctor` prints the four paths resolved for the current machine.

## Data layout

Operations create only what they own:

```text
config_dir()/
└── config.toml                         # written by the user only

data_dir()/
├── engine/
│   ├── current.json                    # atomic pointer to the active engine
│   └── installations/<id>/             # immutable installations
├── calibration/
│   ├── records/
│   │   ├── <mode>.json                 # active record
│   │   ├── <mode>.candidate.json       # inactive candidate
│   │   └── <mode>.previous.json        # single previous slot
│   └── evidence/<run-id>/              # private logs of the last calibration run

cache_dir()/
└── llama.cpp/                           # managed engine downloads and staging

state_dir()/
├── services.json                        # process state, version 1
├── start.lock                           # startup serialization
└── logs/llama-server-<timestamp>.log
```

The `calibration/evidence` directory keeps a single run UUID: once the new run is promoted, the
previous managed ones are removed. Records are private and are not wheel content.

## What `uninstall` deletes

After confirmation, exactly the four roots above are deleted. Excluded are:

- the Hugging Face cache;
- external GGUF and mmproj files;
- executables pointed at by `engine_path` or found on the `PATH`;
- uv, its caches, and other tools;
- any path outside the managed roots.

If the current command belongs to exactly the `bora-workbench` environment configured by uv, the same
confirmation also schedules the removal of that environment and of the command. Python installations
outside `uv tool` stay unchanged and are reported in the summary.

**Next:** [Architecture](architecture.md)
