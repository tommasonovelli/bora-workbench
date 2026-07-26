# Installation and first run

## 1. Requirements

`bora-workbench` supports:

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

## 2. Installing bora-workbench 0.2.1

`bora-workbench` is distributed through GitHub Releases. These commands download the `v0.2.1`
manifest, verify the installer and wheel, and install with pinned uv `0.11.28` and CPython
`3.12.13`. They require no administrator privileges.

### Ubuntu

Open a terminal in a new directory and copy the complete block:

```bash
version="0.2.1"
base="https://github.com/tommasonovelli/bora-workbench/releases/download/v${version}"
wheel="bora_workbench-${version}-py3-none-any.whl"

curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/install.sh" --output install.sh
curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/$wheel" --output "$wheel"
curl --fail --location --proto '=https' --tlsv1.2 \
  "$base/SHA256SUMS" --output SHA256SUMS
installer_sha256="$(awk '$2 == "install.sh" { print $1 }' SHA256SUMS)"
wheel_sha256="$(awk -v wheel="$wheel" '$2 == wheel { print $1 }' SHA256SUMS)"
test "${#installer_sha256}" -eq 64
test "${#wheel_sha256}" -eq 64
printf '%s  %s\n' "$installer_sha256" install.sh | sha256sum --check -
printf '%s  %s\n' "$wheel_sha256" "$wheel" | sha256sum --check -
sh ./install.sh --wheel "./$wheel" --sha256 "$wheel_sha256"
```

### Windows

Open PowerShell in a new directory and copy the complete block:

```powershell
$Version = "0.2.1"
$Base = "https://github.com/tommasonovelli/bora-workbench/releases/download/v$Version"
$Wheel = "bora_workbench-$Version-py3-none-any.whl"

Invoke-WebRequest -Uri "$Base/install.ps1" -OutFile install.ps1
Invoke-WebRequest -Uri "$Base/$Wheel" -OutFile $Wheel
Invoke-WebRequest -Uri "$Base/SHA256SUMS" -OutFile SHA256SUMS

$Expected = @{}
Get-Content .\SHA256SUMS | ForEach-Object {
    if ($_ -match '^([0-9a-f]{64})\s+(.+)$') {
        $Expected[$Matches[2]] = $Matches[1]
    }
}
foreach ($File in @("install.ps1", $Wheel)) {
    if (-not $Expected.ContainsKey($File)) {
        throw "$File is missing from SHA256SUMS"
    }
    $Actual = (Get-FileHash ".\$File" -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected[$File]) {
        throw "$File SHA-256 mismatch"
    }
}
$WheelSha256 = $Expected[$Wheel]
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Wheel ".\$Wheel" -Sha256 $WheelSha256
```

`ExecutionPolicy Bypass` applies to that process only. The script does not change the system policy
and does not require administrative privileges.

The release also contains the source distribution, both installers, and `SHA256SUMS` for offline
verification and installation.

The installers always accept exactly one explicit source:

```text
install.sh  --wheel PATH --sha256 HEX
install.sh  --git-commit FULL_COMMIT

install.ps1 -Wheel PATH -Sha256 HEX
install.ps1 -GitCommit FULL_COMMIT
```

Use the wheel and manifest for a release installation. The full 40-character commit option is for
testing an exact repository revision and never follows a branch or tag implicitly.

## 3. Verifying the tool

For `0.2.1`:

```bash
bora --version
bora validate
bora doctor
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
bora engine install
bora engine status
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
bora doctor
bora coding
```

Without a valid local record the launcher uses the verified `ctx=8192` baseline; on CUDA it also
uses `n_cpu_moe=48`. The CLI declares it as not optimized.

To measure the machine before ordinary launches:

```bash
bora calibrate --mode all
```

Calibration can run for a long time, creates local processes, and activates the resulting records by
default. Read [Calibration](calibration.md) before starting it.

The available modes are:

```bash
bora coding    # text API, no UI and no vision
bora studio    # text chat in the built-in UI
bora vstudio   # built-in UI and image input
```

The processes stay in the foreground. `Ctrl-C` performs the cleanup and exits with code 130. From
another terminal you can use:

```bash
bora status
bora stop
```

## 7. Removal

```bash
bora stop
bora uninstall
```

`uninstall` shows the four managed roots and the Python installation, then asks for a single
confirmation. It refuses live services, roots that are symlinks, or an altered set of paths. With
the supported script installation it also removes the Python tool through uv as soon as the command
finishes; the Hugging Face cache and uv itself always stay excluded.

**Next:** [Commands](commands.md)
