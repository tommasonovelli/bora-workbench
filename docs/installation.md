# Installazione e primo avvio

## 1. Requisiti

`qwen-launcher` supporta:

- Ubuntu 22.04 o successivo, x86-64;
- Windows 11, x86-64;
- backend CPU oppure una singola GPU NVIDIA rilevata tramite `nvidia-smi`;
- CPython 3.12; gli installer fissano `3.12.13` e uv `0.11.28`.

Per il modello predefinito il preflight richiede almeno **28 GiB di RAM totale** e **22 GiB
disponibili**. Sono inoltre necessari circa 22,7 GB per il GGUF, circa 0,9 GB per il proiettore
vision e spazio aggiuntivo per motore, cache di download e log.

CUDA su una macchina con più GPU viene rilevato ma l'avvio è bloccato: l'isolamento fisico è stato
verificato solo su host a GPU singola. Se `nvidia-smi` manca, fallisce o produce dati illeggibili, il
launcher usa il backend CPU e mostra il motivo.

## 2. Installare la release pubblica

La release pubblica è `0.1.2`. PyPI è ancora indisponibile; usare gli artefatti della
[GitHub Release v0.1.2](https://github.com/tommasonovelli/qwen-launcher/releases/tag/v0.1.2).
La release allega wheel, sdist, installer e `SHA256SUMS` ottenuti dal run test/build
multipiattaforma. Una release pubblicata non viene modificata in place.

### Ubuntu

```bash
base="https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.2"
wheel="qwen_launcher-0.1.2-py3-none-any.whl"
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
$base = "https://github.com/tommasonovelli/qwen-launcher/releases/download/v0.1.2"
$wheel = "qwen_launcher-0.1.2-py3-none-any.whl"
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

`ExecutionPolicy Bypass` vale soltanto per quel processo. Lo script non cambia la policy di sistema
e non richiede privilegi amministrativi.

Gli installer accettano sempre una sola sorgente esplicita:

```text
install.sh  --wheel PATH --sha256 HEX
install.sh  --git-commit COMMIT_COMPLETO
install.sh  --pypi-version VERSIONE

install.ps1 -Wheel PATH -Sha256 HEX
install.ps1 -GitCommit COMMIT_COMPLETO
install.ps1 -PypiVersion VERSIONE
```

`--pypi-version` / `-PypiVersion` non è utilizzabile finché una versione non è realmente presente
su PyPI.

## 3. Verificare il tool

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
```

`validate` controlla lock, schemi e contenuti installati. `doctor` legge configurazione, hardware,
motore e record senza modificarli.

## 4. Rendere disponibile il modello

Il launcher non distribuisce e non scarica i pesi. Per l'identità predefinita cerca in sola lettura
lo snapshot Hugging Face della revisione appuntata in `engine.lock`:

```text
repository: unsloth/Qwen3.6-35B-A3B-MTP-GGUF
revision:   5bc3e238d916f48a861bac2f8a1990a0e9b7e98d
GGUF:       Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
mmproj:     mmproj-BF16.gguf
```

Acquisire separatamente i due file dalla
[revisione fissata del repository](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/tree/5bc3e238d916f48a861bac2f8a1990a0e9b7e98d)
con uno strumento scelto dall'utente. Dimensione e SHA-256 devono coincidere col lock. Il proiettore
è richiesto solo da `vstudio`; il launcher non crea ref o snapshot e non altera la cache Hugging
Face.

Un modello diverso richiede una coppia coerente `model` + `model_path` nella configurazione. Non
eredita gate, record o compatibilità del modello predefinito; `vstudio` non può usarlo perché non è
configurabile un mmproj alternativo.

## 5. Installare il motore

```bash
qwen-launcher engine install
qwen-launcher engine status
```

Il backend viene scelto dall'hardware rilevato. Ubuntu CPU e Windows CPU usano prebuilt verificati;
Windows CUDA combina server e runtime CUDA 13.3 verificati; Ubuntu CUDA compila il solo
`llama-server` dal commit sorgente fissato. Se mancano prerequisiti di compilazione, il comando li
elenca senza eseguire `sudo` o package manager.

Download, checksum, estrazione, verifica e attivazione devono completare tutti prima che
`current.json` punti alla nuova installazione. Su un terminale, la CLI mostra per download ed
estrazione una barra a byte con asset corrente, velocità ed ETA calcolata; le altre operazioni
mantengono visibile la fase senza inventare una durata. È normale che la compilazione CUDA Ubuntu
richieda diversi minuti. I probe finali di versione e help restano limitati a 60 secondi ciascuno.
Vedere
[architettura](architecture.md#motore-e-modello) per il contratto.

## 6. Primo utilizzo

Percorso minimo:

```bash
qwen-launcher doctor
qwen-launcher coding
```

Senza un record locale valido il launcher usa la baseline verificata `ctx=8192`; su CUDA usa anche
`n_cpu_moe=48`. La CLI la dichiara non ottimizzata.

Per misurare la macchina prima del lancio ordinario:

```bash
qwen-launcher calibrate --mode all
```

La calibrazione può durare a lungo, crea processi locali e attiva per default i record risultanti.
Leggere [Calibrazione](calibration.md) prima di avviarla.

I modi disponibili sono:

```bash
qwen-launcher coding    # API testuale, senza UI e vision
qwen-launcher studio    # chat testuale nella UI integrata
qwen-launcher vstudio   # UI integrata e input immagine
```

I processi restano in foreground. `Ctrl-C` esegue la pulizia e termina con exit code 130. Da un
altro terminale si possono usare:

```bash
qwen-launcher status
qwen-launcher stop
```

## 7. Rimozione

```bash
qwen-launcher stop
qwen-launcher uninstall
```

`uninstall` mostra le quattro radici gestite e l'installazione Python, poi richiede una sola
conferma. Rifiuta servizi vivi, radici che sono symlink o set di percorsi alterati. Con
l'installazione supportata degli script rimuove anche il tool Python tramite uv appena il comando
termina; la cache Hugging Face e uv stesso restano sempre esclusi.

**Successivo:** [Comandi](commands.md)
