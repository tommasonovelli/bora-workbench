# Calibrazione assistita (`calibration/v1`)

La calibrazione confronta buste esplicite sulla macchina corrente; non è un normale avvio e non
equivale a un singolo benchmark. L'attuale `calibration/v1` è un protocollo di laboratorio per il
Gate: non è ancora il calibratore pubblico generale. Lo Step 5A non distribuisce policy o profili e
ogni risultato resta una bozza locale. Una classe RAM/VRAM non rende portabile il vincitore su CPU e
GPU diverse: per questo i profili v1 condivisi sono ora reference-only e non entrano direttamente nel
`LaunchPlan`. L'audit e il percorso correttivo sono in `CALIBRATE.md`.

## Prerequisiti

Prima di iniziare:

- modello predefinito appuntato e motore `b10011` compatibile già disponibili;
- almeno 28 GiB di RAM totale e 24 GiB disponibili;
- nessun servizio gestito attivo;
- una sola GPU NVIDIA quando il backend rilevato è CUDA;
- nessun altro processo compute sulla GPU selezionata.

Il comando non scarica il modello, non installa il motore, non modifica `config.toml`, non crea
commit e non effettua upload.

## Primo run senza policy

Finché `calibration-policy.json` è assente, candidati e criteri devono essere forniti senza default
nascosti. Un candidato CUDA usa `ID:CTX:N_CPU_MOE`; un candidato CPU usa `ID:CTX`. L'opzione
`--settings` usa `RUNS:MIN_FREE_VRAM_GIB:RELEASE_TOLERANCE_GIB` su CUDA e `RUNS` su CPU. La
tolleranza è espressa in GiB, deve essere non negativa e non ha un default implicito; `0` è valido.

Esempio puramente sintattico, **non** policy consigliata:

```console
qwen-launcher calibrate \
  --mode coding \
  --candidate <id-1>:<ctx>:<n-cpu-moe-1> \
  --candidate <id-2>:<ctx>:<n-cpu-moe-2> \
  --settings <avvii-stabili>:<riserva-vram-gib>:<tolleranza-rilascio-gib>
```

I valori reali devono essere forniti e approvati da Tommaso. Il codice impone un solo contesto per
run: un ripiego di contesto è una prova separata, perché tok/s non deve premiare una finestra più
piccola. Su CUDA ogni `n_cpu_moe` è unico e la lista è ordinata dal più prudente al più aggressivo,
poi provata per intero senza arresto al primo fallimento. Su CPU, a contesto fisso, `v1` accetta un
solo candidato perché non possiede ancora un asse di tuning verificato. La scala ricavata dal PC
8-GiB può riprodurre quel PC, ma non costituisce la futura policy per macchine diverse.

Omettendo candidati o impostazioni, la CLI li richiede interattivamente. Mostra hardware, workload,
destinazione, finestra/tolleranza di rilascio, durata non stimabile con precisione, log e rischio di
crash o scarto, poi richiede conferma.

## Protocollo eseguito

Per ogni modo e candidato, nell'ordine dichiarato, il launcher:

1. verifica assenza di servizi e carichi compute concorrenti;
2. avvia un processo fresco con stato isolato e contratto comandi del lock;
3. campiona memoria GPU complessiva e libera ogni 250 ms;
4. esegue il carico testuale verificato; `vstudio` esegue anche la richiesta immagine verificata;
5. sull'ultimo avvio stabile esegue `benchmark/v1`: un warm-up escluso e cinque misure esatte da 256
   token;
6. dopo lo stop ricampiona ogni 250 ms fino a 10 secondi e accetta il rilascio appena la memoria
   usata è entro `baseline + RELEASE_TOLERANCE_GIB`;
7. applica la stessa tolleranza all'intervallo fra le baseline degli avvii stabili; una deriva oltre
   soglia scarta il solo candidato, mentre carico compute, cambio driver o monitor guasto invalidano
   l'intera calibrazione;
8. scarta il candidato in caso di crash, OOM, timeout, risposta incompatibile, riserva violata o
   rilascio non stabilizzato;
9. propone il candidato con mediana maggiore, poi maggiore VRAM libera, poi il primo candidato
   nell'ordine prudente dichiarato.

Il report conserva finestra, tolleranza e campione finale di rilascio. `validate` ricostruisce anche
riserva, rilascio, coerenza della VRAM e vincitore deterministico di un eventuale report accettato.
Se tutti i candidati sono scartati, il comando termina correttamente dopo aver dichiarato che il
bundle contiene solo scarti. La RAM disponibile durante il trial e l'attivazione locale restano
requisiti aperti del protocollo successivo: `v1` non deve essere presentato come ottimizzazione
portabile.

## Cache KV Q8: attiva nel ramo CUDA

Il modello resta `UD-Q4_K_M`. Il contratto attivo imposta la cache KV Q8 tramite
`--cache-type-k q8_0 --cache-type-v q8_0` nel solo ramo CUDA, mantenendo mmap; il ramo CPU è
invariato. Il mini-spike Ubuntu ha approvato Q8+mmap e rifiutato `--no-mmap`; lo smoke Windows CUDA
13.3 ha confermato Q8+mmap sui tre modi (`docs/mini-spike-kv-q8-windows.md`). Le calibrazioni e i
report precedenti al cambio restano evidenza del contratto senza Q8 e non sono confrontabili con le
misure successive.

## Bundle e privacy

Il bundle viene promosso atomicamente sotto la directory dati:

```text
calibrations/<calibration-id>/
├── <calibration-id>.json
├── benchmark-results.json
├── profile-proposal.json
├── logs/<mode>/<candidate>/*.log
├── CONTRIBUTING.md
└── SHA256SUMS
```

Il report usa `decision=draft`, `privacy_reviewed=false` e selezioni accettate nulle. La proposta è
`draft-not-distributable` e non inventa classe o finestra hardware. I motivi di scarto puntano ai log
relativi copiati; tutti i campi stringa dei tre JSON e i log vengono redatti. La validazione cerca
anche username, hostname e pattern di percorsi assoluti POSIX/Windows in ogni file condivisibile.

```console
qwen-launcher validate --path <percorso-del-bundle>
```

La validazione controlla schema, semantica, riferimenti, digest, manifest, stato non distribuibile e
privacy automatica. Un report accettato richiede inoltre una policy approvata; ciò non autorizza
comunque ad applicare il vincitore a un altro PC. La revisione umana di ogni file nel manifest resta
obbligatoria. Il comando non crea branch, issue o PR.
