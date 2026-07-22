# Smoke Windows 11 — cache KV Q8 su llama.cpp b10011 CUDA 13.3

## Decisione

**Windows 11 CUDA 13.3: `GO` per cache K/V `q8_0` mantenendo `--mmap`.**

Con il GO Ubuntu del mini-spike precedente, questa evidenza completa il requisito di D-033: la
coppia server/runtime CUDA 13.3 accetta `--cache-type-k q8_0 --cache-type-v q8_0`, serve i tre modi
a `ctx=131072` con MTP, UI e vision corretti e rilascia la VRAM entro finestra e tolleranza. La
modifica dichiarativa separata adotta i due argomenti nel solo ramo CUDA di `engine.lock`;
`--no-mmap` resta fuori dal contratto (NO-GO Ubuntu, non riproposto qui).

Il GO riguarda compatibilità funzionale e comportamento di memoria del contratto, non promesse di
prestazioni: le misure Windows registrano il carico ambientale di un desktop reale e la loro
dispersione, dati usati dalla progettazione di `calibration/v2`.

## Macchina e protocollo

- Windows 11 Pro build 26200, x86-64 — **stesso hardware fisico della macchina Ubuntu del
  mini-spike** (dual boot): Intel Core i5-10400F, 31,9 GiB RAM, NVIDIA GeForce RTX 2060 SUPER
  8 GiB; driver Windows 610.47 (Ubuntu: 595.71.05);
- motore gestito b10011 (`bf2c86ddc`), coppia server/runtime CUDA 13.3 e prebuilt CPU, digest del
  lock; modello e mmproj verificati contro i digest del lock (`system-info.txt`);
- `ctx=131072`, Q8+mmap, `n_cpu_moe ∈ {48, 38}` per coding e vstudio, `38` per studio, più un
  riferimento col contratto attuale a `48`; compatibilità CPU a `ctx=8192`;
- `benchmark/v1` (digest appuntati): un warm-up escluso e cinque misure valide da 256 token;
- polling VRAM/RAM a 250 ms, salute, MTP, stop e rilascio fino a 10 s con tolleranza 0,125 GiB;
- a differenza del run Ubuntu (X quieto, ~0,6 GiB ambientali), il desktop Windows aveva un carico
  grafico ambientale reale di ~1,4–1,5 GiB VRAM e ~20 GiB RAM già impegnati; i valori assoluti
  vanno letti in quel contesto e ogni run registra la propria baseline;
- stop tramite CTRL_BREAK: su Windows il processo termina con `0xC000013A`
  (`STATUS_CONTROL_C_EXIT`), l'equivalente console della terminazione per segnale registrata come
  exit 0 su Ubuntu.

I comandi completi, con i soli percorsi privati redatti, sono in `results.json`; prompt e richiesta
mantengono i digest appuntati di `benchmark/v1`.

## Dominio di `n_cpu_moe` sul modello appuntato

I metadati GGUF del modello (`general.architecture=qwen35moe`) dichiarano `block_count=41`,
`expert_count=256`, `expert_used_count=8`, `context_length=262144`. I probe a `ctx=8192` misurano:

| Probe | n_cpu_moe | Picco VRAM usata GiB | Min libera VRAM GiB |
|---|---:|---:|---:|
| `ncmoe-domain-48` | 48 | 4,479 | 3,341 |
| `ncmoe-domain-49` | 49 | 4,485 | 3,334 |
| `ncmoe-domain-41` | 41 | 4,477 | 3,343 |
| `ncmoe-domain-40` | 40 | 4,731 | 3,088 |

48, 49 e 41 sono la stessa configurazione entro il rumore di misura; solo sotto 41 la VRAM cresce.
**Il dominio legale dell'asse è `[0, 41]`**: ogni valore superiore è un alias di «tutti i layer MoE
su CPU». La baseline storica `n_cpu_moe=48` resta valida come alias prudente del massimo; della
scala storica `48, 44, 42, 40, 39, 38, 37` i primi tre valori erano alias della stessa busta.

## Confronto coding CUDA (ctx 131072)

| Configurazione | n_cpu_moe | Load s | Mediana tok/s | Min libera VRAM GiB | Min RAM disp. GiB | Esito |
|---|---:|---:|---:|---:|---:|---|
| attuale, mmap/cache default | 48 | 5,28 | 20,011 | 0,505 | 4,97 | PASS |
| **Q8 K/V + mmap** | 48 | 5,54 | 20,155 | 1,687 | 5,11 | PASS |
| **Q8 K/V + mmap** | 38 | 6,06 | 21,796 | 0,248 | 4,90 | PASS funzionale, sotto riserva |

A parità di `n_cpu_moe=48`, Q8+mmap ha liberato 1,18 GiB di VRAM minima anche su Windows (Ubuntu:
1,16 GiB), con mediana equivalente entro il rumore. MTP attivo in tutte le misure (Q8: 197/156,
identico a Ubuntu a parità di seed). Il PASS di `38` con margine 0,248 GiB conferma che il confine
è sensibile al carico ambientale, come già osservato su Ubuntu (0,235 col contratto attuale).

## Smoke modi con Q8+mmap (ctx 131072) e CPU

| Backend/modo | Busta | Mediana tok/s | Min libera VRAM GiB | Verifiche | Esito |
|---|---|---:|---:|---|---|
| CUDA studio | 131072 / 38 | 22,153 | 0,307 | salute, UI 200, MTP, benchmark, stop | PASS funzionale, sotto riserva |
| CUDA vstudio | 131072 / 48 | 22,110 | 0,378 | salute, UI 200, vision `Rosso`, MTP, benchmark, stop | PASS funzionale, sotto riserva |
| CUDA vstudio | 131072 / 38 | 22,668 | 0,072 | salute, UI 200, vision `Rosso`, MTP, benchmark, stop | PASS funzionale, margine quasi nullo |
| CPU coding | 8192 | 8,885 | n/a | asset CPU, salute, MTP, benchmark, stop | PASS compatibilità |

Sotto il carico ambientale del desktop, **tutti** i candidati aggressivi restano sotto la riserva
prudenziale: su questa macchina in queste condizioni una calibrazione con riserva 0,5 GiB
selezionerebbe buste più prudenti dei PASS funzionali qui elencati. È il comportamento voluto: lo
smoke prova il contratto, la ricerca locale sceglie la busta.

Durante il run CPU la RAM disponibile è scesa fino a 0,01 GiB (Ubuntu quieto: 16,85): il PASS di
compatibilità è reale ma il sistema era al limite della paginazione. È l'evidenza più diretta a
favore del monitoraggio RAM obbligatorio per tutti i backend nel protocollo successivo.

## Dispersione delle misure e rumore ambientale

Dispersione relativa `(max − min) / mediana` delle cinque misure:

| Run | Dispersione |
|---|---:|
| coding attuale 48 / Q8 48 | 11,7% / 11,5% |
| coding Q8 38 | 9,6% |
| studio Q8 38 | 18,0% |
| vstudio Q8 48 / 38 | 10,5% / 18,8% |
| CPU coding Q8 | 6,3% |

Sullo stesso hardware fisico, l'host Ubuntu quieto misurava 0,14–2,4%. La dispersione non è quindi
una proprietà della configurazione ma dell'ambiente: una fascia fissa di equivalenza giudicherebbe
male almeno uno dei due casi. Il protocollo corrente affronta questo limite con round temporali
accoppiati e dominanza per unanimità, descritti in `docs/calibration.md`.

`benchmark/v1` non misura la qualità semantica; il GO attesta compatibilità funzionale, vision,
MTP e comportamento di memoria, non una regressione qualitativa nulla.

## Evidenza

- `evidence/engine/kv-q8-windows/results.json`;
- `evidence/engine/kv-q8-windows/logs/`;
- `evidence/engine/kv-q8-windows/system-info.txt`;
- `evidence/engine/kv-q8-windows/flag-help.txt`;
- `evidence/engine/kv-q8-windows/SHA256SUMS`.
