# Calibration Gate v3 — Windows CUDA, 19 luglio 2026

> **Stato:** evidenza locale del Gate Step 5A, non policy portabile. Il run sostiene i modi
> `coding`, `studio` e `vstudio` sulla macchina descritta; il Gate complessivo resta `GATE-PARTIAL`
> finché lo stesso protocollo non viene provato su hardware materialmente diverso. I record e i log
> privati restano nella directory dati locale e non sono inclusi nel repository.

## 1. Contratti provati

- Launcher: commit `6f69d7724a857d7e9527cc6d7fa01f082227c367` per D-046; la successiva
  correzione diagnostica `2d4cc22a8b76670172a1b0375f2e71c7e4c8e794` non cambia il protocollo o i
  candidati.
- Protocollo: `calibration/v3`; record: `calibration-record/v2`; benchmark: `benchmark/v1`.
- Modello: `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M` appuntato dal lock.
- Motore: `llama.cpp b10011`, backend CUDA.
- Host: Windows 11 build 10.0.26200, 31,92 GiB RAM, RTX 2060 SUPER con 8 GiB VRAM e singola
  GPU selezionata.
- Comando:

  ```console
  uv run --frozen qwen-launcher calibrate --mode all --no-activate
  ```

Il preflight osservava 26,34 GiB di RAM disponibile, 7,30 GiB di VRAM libera e una popolazione WDDM
stabile di 20 contesti identificabili. Chrome non era presente nei contesti GPU del run pulito.

## 2. Provenienza di D-046 e igiene ambientale

Due tentativi precedenti erano stati invalidati dal respawn di un eseguibile desktop già presente
nella baseline. D-046 ha sostituito il PID come proxy del lifecycle con identità eseguibile opaca a
scope di run, mantenendo invalidanti file nuovi, identità illeggibili e molteplicità aggiuntive.

Il primo tentativo dopo D-046 è progredito oltre i punti di fallimento precedenti, poi è stato
correttamente invalidato quando Chrome è stato aperto durante `studio`: era un file eseguibile nuovo,
non un respawn della baseline. Nessun candidato parziale è stato scritto. Un idle soak successivo di
10 minuti non ha osservato cambi della popolazione. Il run pulito è quindi partito con Chrome chiuso
e non ha subito contaminazioni.

## 3. Esito del run pulito

Il comando ha terminato con exit code 0 in 1.623 secondi (27 minuti e 3 secondi). Tutti i modi hanno
raggiunto il contesto massimo della scala, `ctx=131072`, senza degradazione e con sequenze probe
contigue entro il tetto di 12.

| Modo | Screening | Conferma | Probe | Busta candidata | Regola |
|---|---:|---:|---:|---|---|
| coding | 3,53 min | 5,08 min | 7 | `ctx=131072`, `n_cpu_moe=37` | `dominance-unanimous-rounds` |
| studio | 3,06 min | 4,94 min | 6 | `ctx=131072`, `n_cpu_moe=37` | `equivalent-prefer-minimum-free-vram` |
| vstudio | 4,33 min | 5,19 min | 7 | `ctx=131072`, `n_cpu_moe=39` | `single-finalist` |

### Coding

- Probe `(n_cpu_moe, fattibile)`: `41✓, 20✗, 31✗, 36✗, 39✓, 38✓, 37✓`.
- Finalisti 37 e 38 in ordine ABBA; posizioni rispettive `1/4` e `2/3`.
- Mediane per round: 37 = `25,814 / 24,873` tok/s; 38 = `25,088 / 24,555` tok/s.
- Vincitore di entrambi i round: 37.

### Studio

- Probe: `41✓, 20✗, 31✗, 36✓, 34✗, 35✗`.
- Finalisti 36 e 37 in ordine ABBA.
- Mediane per round: 36 = `27,381 / 26,194` tok/s; 37 = `25,236 / 26,578` tok/s.
- I round discordi hanno disabilitato la dominanza; il maggiore margine VRAM ha selezionato 37.

### Vstudio

- Probe: `41✓, 20✗, 31✗, 36✗, 39✓, 38✓, 37✗`.
- Finalisti 38 e 39 hanno entrambi completato due benchmark.
- Il finalista 38 è stato scartato perché la seconda sessione ha raggiunto 0,488 GiB di VRAM libera,
  sotto la riserva di 0,5 GiB; la prima sessione aveva raggiunto 0,505 GiB.
- Il solo finalista valido 39 è stato selezionato.

## 4. Riserve, rilascio e telemetria

I minimi seguenti considerano soltanto probe fattibili e sessioni finaliste valide:

| Modo | RAM disponibile minima | VRAM libera minima | Massimo rilascio oltre baseline | Deriva baseline |
|---|---:|---:|---:|---:|
| coding | 9,291 GiB | 0,950 GiB | 0 GiB | 0 GiB |
| studio | 9,331 GiB | 0,503 GiB | 0,0078 GiB | 0,0146 GiB |
| vstudio | 8,602 GiB | 0,505 GiB | 0,0176 GiB | 0,0176 GiB |

La riserva RAM di 2 GiB non è stata avvicinata su questo host. La riserva VRAM ha invece governato
concretamente il confine, incluso lo scarto vstudio 38; i margini studio e vstudio sono stretti e non
autorizzano a ridurre la costante. Rilascio e deriva sono rimasti sotto 0,125 GiB.

La telemetria best-effort era presente in tutti i 32 trial ed è rimasta evidence-only. Tutti i 32
log contengono i marker MTP e tutti gli 11 log vstudio contengono i marker mmproj/vision; i trial
vstudio validi hanno inoltre superato la richiesta vision reale prevista dal protocollo. L'unico
slot evidence contiene 11 log coding, 10 studio e 11 vstudio, senza riferimenti mancanti.

## 5. Record e lifecycle

`--no-activate` ha prodotto tre candidati validi senza cambiare alcun piano di lancio:

| Modo | SHA-256 candidato | Active dopo il run | Previous |
|---|---|---|---|
| coding | `666b4588c9e4f6ec2fca4d24596bfffffbeee0bb9f052a76805425a8f0987b8f` | v1 storico invariato | assente |
| studio | `6fc8d291c90aa8def63be021f866976f947bbc5ab70c92da35af4e870b3c6632` | assente | assente |
| vstudio | `e904d4d18e4f295aa12250b80d0e2bedeb716fb3fda0ba66e7dbca4aaa0117d2` | assente | assente |

L'active storico coding è rimasto byte-identico, SHA-256
`6da4a4229ca9eb2c9d65f5780c8b735193cf13d4f013cacb8db75609fa5afbc9`. Il loader ha ricostruito
schema, probe, ABBA, mediane, riserve, deriva e selezione di ogni candidato. Il commit `2d4cc22` ha
poi verificato che `doctor` mostri contemporaneamente l'active coding v1 superato e il candidato v2
valido in attesa; nessuna calibrazione è stata rieseguita e nessun candidato è stato attivato.

## 6. Verifiche software

- Locale Windows, uv 0.11.28 e CPython 3.12.13: Ruff check e format verdi, 314 test, `validate`,
  build e verifica wheel isolata verdi.
- D-046, commit `6f69d77`: GitHub Actions run `29684539755` verde su Ubuntu 22.04 e Windows 2022.
- Diagnostica lifecycle, commit `2d4cc22`: GitHub Actions run `29684866498` verde sulla stessa
  matrice.

## 7. Verdetto e limite di portabilità

- Windows 11 / CUDA / coding: `CALIBRATION-ACCEPTED`.
- Windows 11 / CUDA / studio: `CALIBRATION-ACCEPTED`.
- Windows 11 / CUDA / vstudio: `CALIBRATION-ACCEPTED`.
- Calibration Gate complessivo: `GATE-PARTIAL`.

Il risultato valida localmente screening, ABBA, riserve, lifecycle, MTP, vision e D-046, ma non prova
che le costanti comuni siano sufficienti su componenti o capacità diverse. D-047 accetta
esplicitamente questa copertura parziale come sufficiente per aprire Step 5B: il prossimo step
pubblica il metodo di ricerca e dichiara il perimetro misurato, senza esportare la busta 32/8.
Un nuovo run con `--no-activate` su hardware materialmente diverso resta un follow-up futuro non
bloccante. I candidati locali rimangono inattivi finché il maintainer non autorizza separatamente la
promozione.
