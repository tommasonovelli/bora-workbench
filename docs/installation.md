# Installation and first run

## 1. Requirements

`qwen-launcher` supports:

- Ubuntu 22.04 or later, x86-64;
- Windows 11, x86-64;
- the CPU backend, or a single NVIDIA GPU detected through `nvidia-smi`;
- CPython 3.12; the installers pin `3.12.13` and uv `0.11.28`.

For the default model the preflight requires at least **28 GiB of total RAM** and **22 GiB
available**. You also need roughly 22.7 GB for the GGUF, roughly 0.9 GB for the vision projector,
and extra space for the engine, the download cache, and logs.

CUDA on a machine with more than one GPU is detected, but startup is blocked: physical isolation has
only been verified on single-GPU hosts. If `nvidia-smi` is missing, fails, or produces unreadable
data, the launcher uses the CPU backend and shows why.

## 2. Installing the public release

The public release is `0.1.5`. PyPI is still unavailable; use the artifacts of the
[GitHub Release v0.1.5](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.5).
The release attaches the wheel, sdist, installers, and `SHA256SUMS` produced by the cross-platform
test/build run. A published release is never modified in place.

### Ubuntu

```bash
base="https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.5"
wheel="qwen_launcher-0.1.5-py3-none-any.whl"
curl --fail --location "$base/install.sh" --output install.sh
curl --fail --location "$base/$wheel" --output "$wheel"
curl --fail --location "$base/SHA256SUMS" --output SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
wheel_sha256="$(awk -v wheel="$wheel" '$2 == wheel { print $1 }' SHA256SUMS)"
test "${#wheel_sha256}" -eq 64
sh ./install.sh --wheel "./$wheel" --sha256 "$wheel_sha256"
```

### Windows

From PowerShell:

```powershell
$base = "https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.5"
$wheel = "qwen_launcher-0.1.5-py3-none-any.whl"
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

`ExecutionPolicy Bypass` applies to that process only. The script does not change the system policy
and does not require administrative privileges.

The installers always accept exactly one explicit source:

```text
install.sh  --wheel PATH --sha256 HEX
install.sh  --git-commit FULL_COMMIT
install.sh  --pypi-version VERSION

install.ps1 -Wheel PATH -Sha256 HEX
install.ps1 -GitCommit FULL_COMMIT
install.ps1 -PypiVersion VERSION
```

`--pypi-version` / `-PypiVersion` is unusable until a version is actually present on PyPI.

## 3. Verifying the tool

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
```

`validate` checks the installed locks, schemas, and content. `doctor` reads the configuration,
hardware, engine, and records without modifying them.

## 4. Making the model available

The launcher neither distributes nor downloads the weights. For the default identity it looks up,
read-only, the Hugging Face snapshot of the revision pinned in `engine.lock`:

```text
repository: unsloth/Qwen3.6-35B-A3B-MTP-GGUF
revision:   5bc3e238d916f48a861bac2f8a1990a0e9b7e98d
GGUF:       Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
mmproj:     mmproj-BF16.gguf
```

Acquire the two files separately from the
[pinned repository revision](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/tree/5bc3e238d916f48a861bac2f8a1990a0e9b7e98d)
with a tool of your choice. Size and SHA-256 must match the lock. The projector is only required by
`vstudio`; the launcher creates no refs or snapshots and never alters the Hugging Face cache.

A different model requires a consistent `model` + `model_path` pair in the configuration. It
inherits none of the default model's gates, records, or compatibility; `vstudio` cannot use it,
because an alternative mmproj is not configurable.

## 5. Installing the engine

```bash
qwen-launcher engine install
qwen-launcher engine status
```

The backend is chosen from the detected hardware. Ubuntu CPU and Windows CPU use verified prebuilts;
Windows CUDA combines the verified server and CUDA 13.3 runtime; Ubuntu CUDA builds `llama-server`
alone from the pinned source commit. If build prerequisites are missing, the command lists them
without running `sudo` or a package manager.

Download, checksum, extraction, verification, and activation must all complete before `current.json`
points to the new installation. On a terminal, the CLI shows a byte progress bar for download and
extraction with the current asset, speed, and computed ETA; the other operations keep the phase
visible without inventing a duration. It is normal for the Ubuntu CUDA build to take several
minutes. The final version and help probes stay bounded to 60 seconds each. See the
[architecture](architecture.md#engine-and-model) for the contract.

## 6. First use

The minimal path:

```bash
qwen-launcher doctor
qwen-launcher coding
```

Without a valid local record the launcher uses the verified `ctx=8192` baseline; on CUDA it also
uses `n_cpu_moe=48`. The CLI declares it as not optimized.

To measure the machine before ordinary launches:

```bash
qwen-launcher calibrate --mode all
```

Calibration can run for a long time, creates local processes, and activates the resulting records by
default. Read [Calibration](calibration.md) before starting it.

The available modes are:

```bash
qwen-launcher coding    # text API, no UI and no vision
qwen-launcher studio    # text chat in the built-in UI
qwen-launcher vstudio   # built-in UI and image input
```

The processes stay in the foreground. `Ctrl-C` performs the cleanup and exits with code 130. From
another terminal you can use:

```bash
qwen-launcher status
qwen-launcher stop
```

## 7. Removal

```bash
qwen-launcher stop
qwen-launcher uninstall
```

`uninstall` shows the four managed roots and the Python installation, then asks for a single
confirmation. It refuses live services, roots that are symlinks, or an altered set of paths. With
the supported script installation it also removes the Python tool through uv as soon as the command
finishes; the Hugging Face cache and uv itself always stay excluded.

**Next:** [Commands](commands.md)
