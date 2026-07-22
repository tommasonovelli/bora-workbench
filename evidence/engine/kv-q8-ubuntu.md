# Mini-spike Ubuntu — cache KV Q8 su llama.cpp b10011

## Decisione

**Ubuntu CUDA: `GO` per cache K/V `q8_0` mantenendo `--mmap`.**

**`--no-mmap`: `NO-GO`** su questa macchina: caricamento molto più lento, memoria disponibile
molto più bassa, throughput peggiore e rilascio VRAM ancora sopra la baseline dopo 10 secondi.

Il GO riguarda soltanto Ubuntu 24.04, llama.cpp `b10011`, commit
`bf2c86ddc0685f580595954056c2e77ebabfab4f`, il modello appuntato `UD-Q4_K_M` e il backend CUDA.
Non autorizza ancora la modifica del lock globale: resta obbligatorio lo smoke Windows sulla coppia
server/runtime CUDA 13.3 prima di dichiarare verificato il contratto Windows.

## Macchina e protocollo

- Ubuntu 24.04 x86-64;
- Intel Core i5-10400F, circa 32 GiB RAM;
- NVIDIA GeForce RTX 2060 SUPER 8 GiB, driver 595.71.05;
- `ctx=131072`, `n_cpu_moe ∈ {48, 38}` per i confronti CUDA coding;
- stesso modello, sampling, MTP e resto del contratto per tutte le configurazioni;
- `benchmark/v1`: un warm-up escluso e cinque misure valide da 256 token;
- polling RAM/VRAM a 250 ms, salute, MTP, stop e rilascio fino a 10 secondi;
- smoke UI per `studio`, UI+vision per `vstudio`, e compatibilità CPU a `ctx=8192`.

I comandi completi, con soli percorsi privati redatti, sono in `coding-results.json` ed
`extended-results.json`. Prompt e richiesta mantengono i digest appuntati di `benchmark/v1`.

## Confronto coding CUDA

| Configurazione | n_cpu_moe | Load s | Mediana tok/s | Min libera VRAM GiB | Min RAM disponibile GiB | Esito |
|---|---:|---:|---:|---:|---:|---|
| attuale, mmap/cache default | 48 | 2,32 | 31,751 | 1,638 | 27,905 | PASS |
| attuale, mmap/cache default | 38 | 2,17 | 35,889 | 0,235 | 27,932 | PASS funzionale, sotto riserva 0,25 |
| **Q8 K/V + mmap** | 48 | 2,21 | 34,809 | 2,797 | 27,960 | PASS |
| **Q8 K/V + mmap** | 38 | 2,20 | 37,399 | 1,426 | 27,973 | PASS |
| Q8 K/V + no-mmap | 48 | 81,77 | 32,476 | 2,608 | 8,406 | NO-GO |
| Q8 K/V + no-mmap | 38 | 48,74 | 33,514 | 1,112 | 8,685 | NO-GO |

A parità di `n_cpu_moe`, Q8+mmap ha aumentato la mediana di circa 9,6% a 48 e 4,2% a 38,
liberando circa 1,16–1,19 GiB di VRAM minima. MTP è rimasto attivo in tutte le misure. Il nuovo PASS
del contratto attuale a 38 non contraddice l'OOM precedente: il margine minimo è stato soltanto
0,235 GiB, sotto la riserva 0,25, e conferma la sensibilità del confine al carico ambientale.

`benchmark/v1` non misura la qualità semantica. Il GO attesta compatibilità funzionale, vision, MTP,
velocità e memoria, non una regressione qualitativa nulla; un'eventuale promessa di qualità richiede
un protocollo separato approvato.

Per no-mmap il campione finale dopo 10 secondi era circa 0,18–0,20 GiB sopra la baseline; con la
tolleranza 0,125 GiB usata nello spike correttivo quei candidati sarebbero scartati. Il suggerimento
generico del motore a usare no-mmap non prevale quindi sulle misure di questa macchina.

## Smoke modi e CPU con Q8+mmap

| Backend/modo | Busta | Mediana tok/s | Min libera VRAM GiB | Verifiche | Esito |
|---|---|---:|---:|---|---|
| CUDA studio | ctx 131072 / n_cpu_moe 38 | 35,141 | 1,227 | salute, UI 200, MTP, benchmark, stop | PASS |
| CUDA vstudio | ctx 131072 / n_cpu_moe 38 | 35,237 | 0,148 | salute, UI 200, vision `Rosso`, MTP, benchmark, stop | PASS funzionale |
| CPU coding | ctx 8192 | 10,084 | n/a | asset CPU, salute, MTP, benchmark, stop | PASS compatibilità |

`vstudio` a 38 è funzionale ma troppo vicino al limite per una riserva di 0,25 GiB: la successiva
calibrazione deve usare una lista per modo più prudente e includere valori superiori attorno al
confine. Questo dato non è un profilo e non seleziona ancora una busta.

La compatibilità CPU è confermata, ma il vantaggio Q8 osservato riguarda la VRAM CUDA e queste
misure non giustificano un cambio del ramo CPU. Insieme alla controprova Windows conservata accanto,
questa evidenza sostiene il contratto corrente: cache K/V Q8 solo in
`command_contract.backend_args.cuda`, `--mmap` ancora attivo e ramo CPU invariato. `--no-mmap`
resta escluso.

## Evidenza

- `evidence/engine/kv-q8-ubuntu/coding-results.json`;
- `evidence/engine/kv-q8-ubuntu/extended-results.json`;
- `evidence/engine/kv-q8-ubuntu/logs/`;
- `evidence/engine/kv-q8-ubuntu/system-info.txt`;
- `evidence/engine/kv-q8-ubuntu/flag-help.txt`;
- `evidence/engine/kv-q8-ubuntu/SHA256SUMS`.
