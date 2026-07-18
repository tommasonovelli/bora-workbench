# Calibrazione locale (`calibration/v2`) e laboratorio v1

La calibrazione non è un normale avvio e non equivale a un singolo benchmark. Il comando usa per
default `calibration/v2`: cerca e conferma una busta sulla macchina corrente, poi salva un record
privato riutilizzabile soltanto finché identità e headroom coincidono. `calibration/v1` resta
selezionabile con `--protocol v1` per riprodurre il laboratorio e genera soltanto una bozza di
contribuzione. Una classe RAM/VRAM non rende portabile il vincitore su CPU e GPU diverse: i profili
condivisi sono reference-only e possono soltanto ordinare i probe. L'audit è in `CALIBRATE.md` e la
progettazione approvata è in `docs/calibration-v2-design.md`.

## Prerequisiti

Prima di iniziare:

- modello predefinito appuntato e motore `b10011` compatibile già disponibili;
- almeno 28 GiB di RAM totale e 24 GiB disponibili;
- nessun servizio gestito attivo;
- una sola GPU NVIDIA quando il backend rilevato è CUDA;
- nessun altro processo compute sulla GPU selezionata.

Il comando non scarica il modello, non installa il motore, non modifica `config.toml`, non crea
commit e non effettua upload.

## Protocollo predefinito `calibration/v2`

L'utente sceglie soltanto uno dei modi installati oppure `all`; asse CUDA, candidati, contesti,
riserva e criterio di selezione derivano dal protocollo versionato e dalle misure locali:

```console
qwen-launcher calibrate --mode <coding|studio|vstudio|all>
```

Dopo il preflight e la conferma esplicita, per ogni modo il v2:

1. legge dai metadati GGUF il dominio CUDA `[0, block_count]`; su CPU conferma onestamente la sola
   baseline del motore perché non esiste ancora un asse CPU verificato;
2. prova la busta più prudente sulla scala `131072 → 65536 → 32768 → 16384 → 8192`, scendendo di
   contesto soltanto quando quella busta non è fattibile;
3. cerca il confine di fattibilità con processi freschi, al massimo 12 probe e degradazione lineare
   quando i picchi VRAM contraddicono la monotonia; il tetto esaurito non produce un falso optimum;
4. monitora RAM su tutti i backend e VRAM aggregata su CUDA ogni 250 ms durante caricamento,
   workload e benchmark;
5. conferma il confine e il vicino prudente con due avvii stabili e `benchmark/v1`, poi applica la
   dominanza fra misure locali o, senza dominanza, preferisce margine VRAM e prudenza;
6. scrive atomicamente `data_dir()/calibration/records/<modo>.json` conforme a
   `calibration-record/v1`.

Ogni lancio rivalida schema, selezione, modello/digest, release/commit/contratto motore, OS, backend,
hardware, driver e headroom corrente. Una divergenza ignora il record con diagnostica e usa la
baseline non ottimizzata; non esistono nearest-match o upload automatici. `doctor` mostra per modo
record valido, assente, invalido, obsoleto o temporaneamente privo di headroom. Il Calibration Gate
reale deve ancora validare le costanti D-039; fino a `CALIBRATION-ACCEPTED` lo Step 5B resta chiuso.

## Laboratorio `calibration/v1` senza policy

Finché `calibration-policy.json` è assente, candidati e criteri devono essere forniti senza default
nascosti. Un candidato CUDA usa `ID:CTX:N_CPU_MOE`; un candidato CPU usa `ID:CTX`. L'opzione
`--settings` usa `RUNS:MIN_FREE_VRAM_GIB:RELEASE_TOLERANCE_GIB` su CUDA e `RUNS` su CPU. La
tolleranza è espressa in GiB, deve essere non negativa e non ha un default implicito; `0` è valido.

Esempio puramente sintattico, **non** policy consigliata:

```console
qwen-launcher calibrate \
  --mode coding \
  --protocol v1 \
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
bundle contiene solo scarti. `v1` non monitora la RAM durante il trial e non attiva localmente il
risultato: resta un protocollo storico di laboratorio e non deve essere presentato come
ottimizzazione portabile.

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
