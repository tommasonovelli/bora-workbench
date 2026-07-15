# Spike 0 — llama.cpp b10011

## Stato

**Decisione complessiva: `PENDING_WINDOWS`. Risultato Ubuntu: `PASS`.**

La matrice Ubuntu 24.04 è completa per CPU e CUDA nei modi `coding`, `studio` e
`vstudio`. Non è ancora lecito dichiarare `GO`: mancano Windows CPU, Windows
CUDA `studio`/`vstudio` e i benchmark Windows previsti dalla specifica.

## Versioni verificate

- motore: `ggml-org/llama.cpp` tag `b10011`;
- commit: `bf2c86ddc0685f580595954056c2e77ebabfab4f`;
- licenza motore: MIT;
- modello: `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`;
- revisione modello: `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`;
- licenza modello dichiarata dalla model card: Apache-2.0; il testo Apache 2.0 del modello base è
  stato acquisito alla revisione `995ad96eacd98c81ed38be0c5b274b04031597b0`;
- GGUF: SHA-256 `0b21525e972670ed59e1812e170b27c26355381f0656ecc4e25617ece7dac58b`;
- mmproj BF16: SHA-256 `da63cb47a76763c712393f8a017070188a304fa39f8aeea6edc629ed7b975cfa`.

Il launcher non redistribuirà i pesi del modello e non ha modificato la cache Hugging Face.

## Macchina Ubuntu

- Ubuntu 24.04 x86-64, kernel `6.17.0-40-generic`;
- Intel Core i5-10400F, 6 core / 12 thread;
- 32,775,508 KiB RAM totale;
- NVIDIA GeForce RTX 2060 SUPER, 8192 MiB;
- driver NVIDIA `595.71.05`;
- CUDA toolkit `12.0.140`.

I dettagli grezzi sono in `spike-0/ubuntu-b10011/system-info.txt`.

## Preparazione del motore

### CPU

È stato usato l'asset ufficiale:

```text
https://github.com/ggml-org/llama.cpp/releases/download/b10011/llama-b10011-bin-ubuntu-x64.tar.gz
sha256: 3cae0a514d2e95062be5b1ca19474446080a1cc12ae5cb1a89d0534bcd013ec1
```

Il probe restituisce `version: 10011 (bf2c86ddc)` e nessun device CUDA.

### CUDA

È stato compilato l'archivio del commit esatto con:

```text
cmake -S <source> -B <build> -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON \
  -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_NUMBER=10011 \
  -DLLAMA_BUILD_COMMIT=bf2c86ddc0685f580595954056c2e77ebabfab4f
cmake --build <build> --config Release --parallel 6 --target llama-server
```

Un archivio sorgente GitHub non contiene `.git`: senza i due valori `LLAMA_BUILD_*` il primo
probe ha correttamente rivelato `version: 0 (unknown)`. La build finale riporta versione 10011 e
commit completo. CMake ha rilevato automaticamente l'architettura CUDA 7.5 della GPU.

## Contratto osservato

- versione: `--version`, exit 0, contiene `version: 10011` e `bf2c86ddc`;
- help: `--help`, exit 0;
- salute in caricamento: HTTP 503 con `{"error":{"message":"Loading model",...}}`;
- salute pronta: HTTP 200 con `{"status":"ok"}`;
- modelli: `/v1/models`;
- chat: `/v1/chat/completions`;
- metriche: `/metrics`;
- UI: `/`;
- host provato: `127.0.0.1`;
- CORS fissato a `--cors-origins localhost`;
- UI esplicita: `--webui` / `--no-webui`;
- vision esplicita: `--mmproj <file>` / `--no-mmproj`;
- CUDA: `-ngl 99 -ncmoe 48`;
- CPU: nessun `-ngl` e nessun `-ncmoe`;
- MTP: `--spec-type draft-mtp --spec-draft-n-max 2`.

Il contratto macchina completo e gli array di argomenti sono in `spike-0.json` e
`spike-0/ubuntu-b10011/commands.json`.

## Matrice Ubuntu

| Backend | Modo | UI | Vision | MTP | API | Esito |
|---|---|---:|---:|---:|---:|---:|
| CUDA | coding | off | off | sì | sì | PASS |
| CUDA | studio | on | off | sì | sì | PASS |
| CUDA | vstudio | on | on | sì | sì | PASS |
| CPU | coding | off | off | sì | sì | PASS |
| CPU | studio | on | off | sì | sì | PASS |
| CPU | vstudio | on | on | sì | sì | PASS |

La PNG rossa riproducibile è stata riconosciuta come `Rosso` sia su CPU sia su CUDA. Nelle risposte
vision è presente attività draft MTP. La UI restituisce HTTP 200 quando il client dichiara il normale
supporto gzip; senza supporto gzip il server risponde 415 perché l'asset incorporato è compresso.
`--no-webui` restituisce 404 alla radice.

Il default CORS `*` ha prodotto un warning di sicurezza. Il probe dedicato ha verificato che
`--cors-origins localhost` non restituisce `Access-Control-Allow-Origin` per
`https://evil.example` e riflette correttamente `http://localhost:3000`; il flag è quindi parte del
contratto fisso, anche se la matrice prestazionale precedente documenta onestamente i comandi senza
questo affinamento successivo.

`CUDA_VISIBLE_DEVICES=0` espone soltanto `CUDA0`; una stringa vuota non espone device. La macchina ha
una sola GPU, quindi la prova Ubuntu non simula una selezione fra più GPU; l'evidenza Windows già
archiviata resta la prova preliminare disponibile.

## Benchmark `benchmark/v1`

Il protocollo usa:

- prompt e richiesta fissi con SHA-256 registrati;
- `max_tokens=256` e `ignore_eos=true`;
- seed `424242`;
- un warm-up escluso e cinque misure incluse;
- nessun client concorrente;
- cache prompt predefinita del server: il warm-up la popola e le misure successive hanno osservato
  124 token in cache e 4 token rivalutati;
- tok/s da `response.timings.predicted_per_second`, verificati con
  `predicted_n / predicted_ms`.

Tutte le 36 risposte Ubuntu hanno `completion_tokens=256`, `predicted_n=256` e
`finish_reason=length`. Sei sono warm-up; trenta sono misure valide.

| Backend | Modo | Min tok/s | Mediana tok/s | Max tok/s |
|---|---|---:|---:|---:|
| CUDA | coding | 31.493 | 31.524 | 31.547 |
| CUDA | studio | 34.279 | 34.294 | 34.388 |
| CUDA | vstudio | 35.037 | 35.214 | 35.253 |
| CPU | coding | 10.865 | 11.042 | 11.234 |
| CPU | studio | 11.097 | 11.261 | 11.507 |
| CPU | vstudio | 11.404 | 11.457 | 11.490 |

Questi numeri valgono soltanto per macchina, modello, release, contesto 8192 e parametri registrati.
Non rappresentano tier hardware generici.

## Licenze, asset e nomi

La release include licenza MIT e asset ufficiali Ubuntu CPU, Windows CPU, Windows CUDA 12.4/13.3,
runtime CUDA e UI. GitHub pubblica digest SHA-256 per gli asset; quelli pertinenti sono riportati in
`spike-0.json`. L'asset sorgente Ubuntu CUDA è fissato al commit completo e il suo archivio scaricato
ha SHA-256 `8a43d487370d775a4f6a6faa1f27085c51eae13d7d2b9dc403b551966114f397`.

Al momento del controllo, PyPI ha restituito 404 per `qwen-launcher`; l'API GitHub non autenticata ha
restituito 404 per il repository configurato. Sono controlli indicativi, non prenotazioni né prove di
disponibilità pubblica.

## Evidenza Windows già disponibile

L'archivio iniziale dimostra parzialmente Windows 11 CUDA `coding`: help/versione, selezione GPU,
caricamento, salute, API, metriche, UI off e stop. Non contiene ancora la matrice e il protocollo
benchmark completi.

## Lavoro residuo prima del `GO`

1. Windows CPU: `coding`, `studio`, `vstudio`.
2. Windows CUDA: `studio` e `vstudio`, inclusa immagine.
3. `benchmark/v1` Windows per ogni combinazione dichiarata.
4. Identificazione certa della coppia asset server/runtime CUDA usata nel test Windows.
5. Controllo finale di coerenza e decisione umana `GO` o `NO-GO`.

Fino ad allora lo Step 0 resta aperto e non autorizza Step 2.
