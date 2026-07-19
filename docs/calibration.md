# Calibrazione locale (`calibration/v3`) e laboratorio v1

La calibrazione non è un normale avvio né un singolo benchmark. Il comando usa per default
`calibration/v3`: cerca la busta sul PC corrente, conferma i finalisti in finestre temporali
accoppiate e crea un record privato. `calibration/v2` è stato respinto dal Gate del 18 luglio 2026
perché misurava i finalisti in finestre disgiunte; il relativo design è conservato come evidenza
storica in [`calibration-v2-design.md`](calibration-v2-design.md). Il design v3 implementato è in
[`calibrate_v3.md`](calibrate_v3.md).

I profili condivisi sono soltanto seed. Nessun vincitore misurato su un altro PC diventa una busta
locale senza una nuova misura.

## Stato del Calibration Gate

Il run Windows 11/CUDA del 19 luglio 2026 ha completato `--mode all --no-activate` e ha prodotto
candidati validi per coding, studio e vstudio, senza attivarli. L'esito locale è
`CALIBRATION-ACCEPTED`; la copertura empirica complessiva resta `GATE-PARTIAL`. D-047 autorizza
Step 5B e rinvia lo stesso protocollo su hardware materialmente diverso a un follow-up futuro non
bloccante. Risultati, riserve e limiti sono registrati in
[`calibration-gate-v3-windows.md`](calibration-gate-v3-windows.md).

## Prerequisiti

Prima di iniziare:

- modello predefinito appuntato e motore `b10011` compatibile già disponibili;
- almeno 28 GiB di RAM totale e 24 GiB disponibili al preflight;
- nessun servizio gestito attivo;
- una sola GPU NVIDIA quando il backend rilevato è CUDA;
- nessun altro workload compute o grafico intensivo sulla GPU selezionata.

Su WDDM i contesti persistenti del desktop riportati come compute entrano in una baseline
immutabile per l'intero run. Un respawn dello stesso file eseguibile è ammesso entro la molteplicità
iniziale e contato come evidenza; un file nuovo, un'identità illeggibile o un'istanza aggiuntiva
invalida il run. Il processo gestito coincide soltanto per `pid + create_time`. Fuori da WDDM
qualunque contesto compute iniziale blocca la calibrazione.

Il comando non scarica il modello, non installa il motore, non modifica `config.toml`, non crea
commit e non effettua upload.

## Percorso predefinito

L'utente sceglie soltanto il modo oppure `all`:

```console
qwen-launcher calibrate --mode <coding|studio|vstudio|all>
```

L'obiettivo lessicografico dichiarato è:

1. massimo contesto fattibile sulla scala approvata;
2. a quel contesto, throughput confermato dai round accoppiati;
3. a parità, maggiore margine di memoria;
4. a parità, configurazione più prudente.

Per ogni modo il v3:

1. legge dai metadati GGUF il dominio CUDA `[0, block_count]`; su CPU conferma la baseline del
   motore perché non esiste ancora un asse CPU verificato;
2. prova la scala `131072 → 65536 → 32768 → 16384 → 8192` e scende solo quando la busta più prudente
   non è fattibile;
3. cerca il confine con processi freschi entro 12 probe. La bisezione può scegliere il prossimo
   punto tramite interpolazione dei soli picchi fattibili, ma la previsione ordina e non esclude;
4. verifica la monotonia VRAM soltanto sui caricamenti completati: un picco OOM troncato non forza
   una scansione lineare spuria;
5. monitora ogni 250 ms RAM su tutti i backend e VRAM aggregata su CUDA. Ogni trial deve lasciare
   almeno 2,0 GiB di RAM disponibile; CUDA deve lasciare almeno 0,5 GiB di VRAM libera;
6. conferma due finalisti con due round ABBA: `A→B`, poi `B→A`. Ognuno dei quattro avvii esegue un
   `benchmark/v1` completo (warm-up escluso più cinque misure);
7. dichiara dominanza solo se lo stesso finalista ha mediana di sessione maggiore in entrambi i
   round. Round discordi o pari ripiegano sul margine VRAM e poi sulla prudenza;
8. se le baseline VRAM derivano oltre 0,125 GiB, non scarta i finalisti: disabilita la dominanza e
   registra `equivalent-after-baseline-drift`, perché le riserve assolute sono comunque verificate;
9. raccoglie, quando il driver le espone, utilizzo, clock SM, temperatura, potenza e motivi di
   throttling. Questi dati sono solo evidenza e non introducono soglie decisionali;
10. conserva log ed evidenza dell'ultimo run in `data_dir()/calibration/evidence/<run-id>/` con un
    solo slot ruotato.

La CLI mostra il progresso per fase. Dopo due processi locali aggiunge una stima best-effort del
tempo rimanente; la stima non cambia il protocollo.

## Record candidato e attivazione

Il risultato è `calibration-record/v2`. Prima viene scritto e validato come:

```text
data_dir()/calibration/records/<modo>.candidate.json
```

Nel percorso predefinito il candidato viene promosso atomicamente a `<modo>.json`; l'attivo
precedente viene copiato in `<modo>.previous.json` come singolo slot di rollback. Quindi il normale
comando resta sufficiente per calibrare e usare subito la busta.

Per il Gate o per esperimenti:

```console
qwen-launcher calibrate --mode coding --no-activate
qwen-launcher calibrate --mode coding --activate
```

`--no-activate` lascia il risultato candidato e non cambia il piano di lancio. `--activate` promuove
un candidato già validato senza rieseguire modello, hardware o benchmark. `doctor` distingue attivo,
candidato, assente, invalido, superato e privo di headroom.

I record storici `calibration-record/v1` prodotti da `calibration/v2` sono classificati come
**superati** e non possono pilotare un lancio; il rimedio è rieseguire `calibrate`. Non esiste
migrazione automatica.

## Contesto esperto

Un utente esperto può fissare un solo gradino approvato:

```console
qwen-launcher calibrate --mode coding --target-ctx 32768
```

Il confronto resta a contesto fisso. Il percorso predefinito senza questa opzione continua a
massimizzare il contesto fattibile.

## Riuso e headroom

Ogni caricamento ricostruisce schema, sessioni ABBA, mediane, vincitori dei round, deriva, tie-break,
modello/digest, release/commit/contratto motore, OS, backend, hardware e driver. Il record attivo è
usabile soltanto se:

- RAM disponibile corrente ≥ fabbisogno RAM misurato + 2,0 GiB;
- su CUDA, VRAM libera corrente ≥ fabbisogno VRAM misurato + 0,5 GiB.

Una divergenza usa la baseline non ottimizzata con diagnostica. Un candidato non attivo non viene
mai usato da `LaunchPlan`. Non esistono nearest-match o upload automatici.

## Laboratorio storico `calibration/v1`

`calibration/v1` resta disponibile per riprodurre il laboratorio esplicito:

```console
qwen-launcher calibrate \
  --mode coding \
  --protocol v1 \
  --candidate <id-1>:<ctx>:<n-cpu-moe-1> \
  --candidate <id-2>:<ctx>:<n-cpu-moe-2> \
  --settings <avvii>:<riserva-vram-gib>:<tolleranza-rilascio-gib>
```

Su CPU un candidato usa `ID:CTX` e `--settings` contiene soltanto gli avvii. I valori sono sempre
espliciti; v1 non monitora RAM, non attiva il risultato e genera soltanto un bundle bozza.

## Cache KV Q8

Il modello resta `UD-Q4_K_M`. Il ramo CUDA imposta `--cache-type-k q8_0 --cache-type-v q8_0` con
mmap dopo i GO Ubuntu e Windows; il ramo CPU è invariato. `--no-mmap` è stato rifiutato dalle misure.

## Bundle e privacy

Il bundle condivisibile del laboratorio resta separato dai record privati. Contiene report, misure,
proposta non distribuibile, log redatti, manifest e guida. `validate --path <bundle>` verifica
schema, digest, riferimenti relativi e pattern privati POSIX/Windows. Nessun comando crea branch,
issue, PR o upload; la revisione umana resta obbligatoria.
