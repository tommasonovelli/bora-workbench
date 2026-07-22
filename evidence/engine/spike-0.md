# Spike 0 — llama.cpp b10011

## Stato

**Decisione complessiva: `GO`. Risultati Ubuntu e Windows: `PASS`.**

La matrice richiesta è completa su Ubuntu 24.04 e Windows 11, con backend CPU e CUDA nei modi
`coding`, `studio` e `vstudio`. Il `GO` riguarda esclusivamente Qwen 3.6, la release e la busta di
prova indicate qui. Le misure non definiscono tier RAM/VRAM e non modificano gli assetti di
produzione dei tre modi.

La macchina possiede una sola GPU. `CUDA_VISIBLE_DEVICES=0` ha esposto `CUDA0` al figlio senza
modificare l'ambiente padre, ma non è stato possibile provare una selezione fra più GPU fisiche.
Di conseguenza la 0.1 dovrà rifiutare l'avvio CUDA su host multi-GPU finché tale caso non sarà
verificato; questo limite dichiarato non invalida l'esecuzione su host a GPU singola collaudata qui.

## Versioni verificate

- motore: `ggml-org/llama.cpp` tag `b10011`;
- commit: `bf2c86ddc0685f580595954056c2e77ebabfab4f`;
- probe: `version: 10011 (bf2c86ddc)`, build Clang Windows e GNU Linux x86-64;
- licenza motore: MIT;
- modello: `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`;
- revisione modello: `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`;
- licenza modello dichiarata: Apache-2.0; testo del modello base acquisito alla revisione
  `995ad96eacd98c81ed38be0c5b274b04031597b0`;
- GGUF: SHA-256 `0b21525e972670ed59e1812e170b27c26355381f0656ecc4e25617ece7dac58b`;
- mmproj BF16: SHA-256 `da63cb47a76763c712393f8a017070188a304fa39f8aeea6edc629ed7b975cfa`.

Il launcher non redistribuisce i pesi e non modifica la cache Hugging Face.

## Macchine

Entrambe le prove usano Intel Core i5-10400F, 6 core / 12 thread, circa 32 GiB RAM e NVIDIA
GeForce RTX 2060 SUPER da 8192 MiB.

- Ubuntu 24.04 x86-64, kernel `6.17.0-40-generic`, driver NVIDIA `595.71.05`, toolkit CUDA
  `12.0.140`;
- Windows 11 Pro x86-64, build `10.0.26200`, driver NVIDIA `610.47`, CUDA UMD `13.3`.

Gli output completi sono `spike-0/ubuntu-b10011/system-info.txt` e
`spike-0/windows-b10011/system-info.json`/`nvidia-smi.txt`.

## Asset e runtime verificati

### Ubuntu CPU e CUDA

L'asset CPU ufficiale provato è:

```text
llama-b10011-bin-ubuntu-x64.tar.gz
https://github.com/ggml-org/llama.cpp/releases/download/b10011/llama-b10011-bin-ubuntu-x64.tar.gz
sha256: 3cae0a514d2e95062be5b1ca19474446080a1cc12ae5cb1a89d0534bcd013ec1
```

CUDA è stato compilato dall'archivio del commit esatto, SHA-256
`8a43d487370d775a4f6a6faa1f27085c51eae13d7d2b9dc403b551966114f397`, impostando
`LLAMA_BUILD_NUMBER=10011` e il commit completo perché l'archivio sorgente non contiene `.git`.
Il comando CMake e il log grezzo sono archiviati.

### Windows CPU

```text
llama-b10011-bin-win-cpu-x64.zip
sha256: 5cb0676f1b6341aa1f3144c3d7fd00bd638a0ce676954712444aecd61f71ad36
```

L'asset è stato scaricato dalla release ufficiale, verificato prima dell'estrazione e provato nei
tre modi. `--list-devices` non elenca CUDA e i comandi CPU non contengono `-ngl` o `-ncmoe`.

### Windows CUDA 13.3

La coppia realmente sovrapposta e provata è:

```text
llama-b10011-bin-win-cuda-13.3-x64.zip
sha256: 2af4f3c1fb42afa85c76a782187444e44f33c08fa31b9000e6baeb18342c6ea2

cudart-llama-bin-win-cuda-13.3-x64.zip
sha256: 1462a050eb4c684921ba51dcc4cc488a036674c3e73e9945ee705b854808d03e
```

Il runtime contiene esattamente `cublas64_13.dll`, `cublasLt64_13.dll` e `cudart64_13.dll`.
`extracted-files.json` registra dimensione e SHA-256 di ogni file estratto. Versione, help, device,
caricamento e intera matrice sono stati eseguiti con questa coppia, non con l'installazione
preesistente b9987 trovata sulla macchina.

## Licenze e redistribuibilità

- Il testo MIT di llama.cpp è stato acquisito dal commit esatto e ha SHA-256
  `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`.
  Gli zip binari non includono il testo: una distribuzione gestita deve conservarne copyright e
  permission notice.
- La CUDA Toolkit EULA v13.3, aggiornata il 26 gennaio 2026, è archiviata con SHA-256
  `6180cc2a02db890cf87ba52f078b7a222b04dcb3c2650865763d4f32ad663a5c`.
  La sezione 2.6 Attachment A elenca come redistribuibili le varianti Windows di CUDA Runtime
  (`cudart`) e CUDA BLAS (`cublas`, `cublasLt`), soggette ai requisiti di distribuzione della
  sezione 1.1.2. Lo zip runtime contiene soltanto tali tre DLL ma non la EULA; l'installazione
  gestita corrente conserva quindi l'avviso NVIDIA verificato insieme agli asset.
- Modello e mmproj non vengono redistribuiti dal launcher.

Questa è una verifica tecnica dei termini applicabili agli asset, non consulenza legale.

## Contratto osservato

- versione: `--version`, exit 0, contiene `version: 10011` e `bf2c86ddc`;
- help completo: `--help`, exit 0, con tutti i flag del contratto;
- salute in caricamento: HTTP 503 con errore `Loading model`;
- salute pronta: HTTP 200 con `{"status":"ok"}`;
- modelli: `/v1/models`; chat: `/v1/chat/completions`; metriche: `/metrics`; UI: `/`;
- host: `127.0.0.1`; CORS ristretto con `--cors-origins localhost`;
- UI esplicita: `--webui` / `--no-webui`;
- vision esplicita: `--mmproj <file>` / `--no-mmproj`;
- CUDA: `-ngl 99 -ncmoe 48`; CPU: nessun argomento CUDA;
- MTP: `--spec-type draft-mtp --spec-draft-n-max 2`;
- sampling coding `(0.6, 0.95, 20)`, studio/vstudio `(0.7, 0.8, 20)`.

Gli array completi sono in `spike-0.json`, nei `commands.json` Ubuntu e nei `command.json` di ogni
prova Windows. Il contratto non contiene parametri dedotti da RAM, VRAM o velocità.

## Matrice funzionale

| OS | Backend | Modo | UI | Vision | MTP | Salute/API/metriche | Stop/log | Esito |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Ubuntu | CPU | coding | off | off | sì | sì | sì | PASS |
| Ubuntu | CPU | studio | on | off | sì | sì | sì | PASS |
| Ubuntu | CPU | vstudio | on | on | sì | sì | sì | PASS |
| Ubuntu | CUDA | coding | off | off | sì | sì | sì | PASS |
| Ubuntu | CUDA | studio | on | off | sì | sì | sì | PASS |
| Ubuntu | CUDA | vstudio | on | on | sì | sì | sì | PASS |
| Windows | CPU | coding | off | off | sì | sì | sì | PASS |
| Windows | CPU | studio | on | off | sì | sì | sì | PASS |
| Windows | CPU | vstudio | on | on | sì | sì | sì | PASS |
| Windows | CUDA | coding | off | off | sì | sì | sì | PASS |
| Windows | CUDA | studio | on | off | sì | sì | sì | PASS |
| Windows | CUDA | vstudio | on | on | sì | sì | sì | PASS |

La PNG rossa è stata riconosciuta come `Rosso` su CPU e CUDA in entrambi gli OS. La UI esplicita
restituisce 200 con supporto gzip; `--no-webui` restituisce 404. Le risposte contengono attività
draft MTP. Su Windows ogni processo è stato terminato, la porta è risultata chiusa e stdout/stderr
sono conservati nel relativo `server.log`.

## Isolamento GPU

Su Ubuntu e Windows `CUDA_VISIBLE_DEVICES=0` espone `CUDA0`; su Windows il PID del server è stato
osservato sulla GPU. La variabile del processo padre era assente prima e dopo le prove. L'host ha
una sola GPU, quindi non esiste evidenza di rimappatura fra più GPU fisiche. Inoltre, nella prova
Windows corrente un valore vuoto passato tramite `CreateProcess` non ha nascosto la GPU, mentre
l'indice inesistente `99` non ha esposto device; l'archivio preliminare PowerShell mostrava invece
nessun device col valore vuoto. Il launcher non usa il valore vuoto: imposta sempre un indice
concreto. Per non promettere più di quanto provato, CUDA multi-GPU deve restare bloccato nella 0.1.

## Benchmark `benchmark/v1`

Il protocollo usa prompt e richiesta fissi con SHA-256 registrati, `max_tokens=256`,
`ignore_eos=true`, seed `424242`, un warm-up escluso e cinque misure, senza client concorrenti.
Ogni risposta ha `completion_tokens=256`, `predicted_n=256` e `finish_reason=length`; tok/s deriva da
`response.timings.predicted_per_second`, ricontrollato con `predicted_n / predicted_ms`.

| OS | Backend | Modo | Min tok/s | Mediana tok/s | Max tok/s |
|---|---|---|---:|---:|---:|
| Ubuntu | CPU | coding | 10.865 | 11.042 | 11.234 |
| Ubuntu | CPU | studio | 11.097 | 11.261 | 11.507 |
| Ubuntu | CPU | vstudio | 11.404 | 11.457 | 11.490 |
| Ubuntu | CUDA | coding | 31.493 | 31.524 | 31.547 |
| Ubuntu | CUDA | studio | 34.279 | 34.294 | 34.388 |
| Ubuntu | CUDA | vstudio | 35.037 | 35.214 | 35.253 |
| Windows | CPU | coding | 8.437 | 8.710 | 8.967 |
| Windows | CPU | studio | 8.162 | 9.087 | 9.267 |
| Windows | CPU | vstudio | 8.378 | 8.394 | 8.498 |
| Windows | CUDA | coding | 15.503 | 19.281 | 19.598 |
| Windows | CUDA | studio | 23.958 | 24.393 | 24.787 |
| Windows | CUDA | vstudio | 23.749 | 24.365 | 24.495 |

Sono 12 warm-up esclusi e 60 misure valide. I numeri descrivono soltanto questa macchina, release,
modello, contesto 8192 e busta di prova; non sono profili né indicazioni per scegliere esperti,
layer, RAM o VRAM.

## Evidenza e integrità

- `evidence/engine/spike-0/SHA256SUMS`: manifest globale dell'evidenza attiva;
- `evidence/engine/spike-0/windows-b10011/SHA256SUMS`: tutti i 229 output Windows grezzi;
- `evidence/engine/spike-0/research/`: metadati release/modello e testi di licenza acquisiti.

## Decisione

L'esito è `GO` per il contratto oggi appuntato. Release, commit, asset Windows CPU/CUDA 13.3,
runtime, help/versione, comando, salute, API, UI, vision, MTP, sampling, metriche, stop/log e
benchmark sono stati verificati senza inventare dati. Queste misure dimostrano fattibilità, non una
busta ottima o un profilo trasferibile. CUDA multi-GPU resta fuori dallo scope verificato e le
installazioni gestite conservano gli avvisi MIT/NVIDIA richiesti.
