# Calibrazione assistita (`calibration/v1`)

La calibrazione confronta più buste esplicite; non è un normale avvio e non equivale a un singolo
benchmark. Lo Step 5A non distribuisce ancora una policy o un profilo: ogni risultato resta una
bozza locale fino al Calibration Gate e allo Step 5B.

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
`--settings` usa `RUNS:MIN_FREE_VRAM_GIB` su CUDA e `RUNS` su CPU.

Esempio puramente sintattico, **non** policy consigliata:

```console
qwen-launcher calibrate \
  --mode all \
  --candidate <id-1>:<ctx-1>:<n-cpu-moe-1> \
  --candidate <id-2>:<ctx-2>:<n-cpu-moe-2> \
  --settings <avvii-stabili>:<riserva-vram-gib>
```

I valori reali del primo run devono essere forniti e approvati da Tommaso; non vanno ricavati dallo
spike, che ha verificato soltanto la fattibilità della busta `ctx=8192`, `n_cpu_moe=48`.
Omettendo candidati o impostazioni, la CLI li richiede interattivamente. In entrambi i casi mostra
hardware, workload, destinazione, durata non stimabile con precisione, spazio occupato dai log e
rischio di crash/scarto, poi richiede conferma.

## Protocollo eseguito

Per ogni modo e candidato, nell'ordine dichiarato, il launcher:

1. verifica assenza di servizi e carichi compute concorrenti;
2. avvia un processo fresco con stato isolato e contratto comandi del lock;
3. campiona memoria GPU complessiva e libera ogni 250 ms;
4. esegue il carico testuale verificato; `vstudio` esegue anche la richiesta immagine verificata;
5. sull'ultimo avvio stabile esegue `benchmark/v1`: un warm-up escluso e cinque misure esatte da 256
   token;
6. arresta il processo e richiede che la GPU torni alla baseline;
7. scarta soltanto il candidato in caso di crash, OOM, timeout, risposta incompatibile o riserva
   violata; un carico concorrente invalida invece la calibrazione;
8. propone il candidato con mediana maggiore, poi maggiore VRAM libera, poi il primo candidato
   nell'ordine prudente dichiarato.

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

Il report usa `decision=draft`, `privacy_reviewed=false` e selezioni accettate nulle. La proposta non
usa lo schema `profile/v1`, dichiara `draft-not-distributable` e lascia classe/finestra hardware a
`null`: non può essere copiata fra i profili distribuiti. Hostname, username e percorsi privati noti
sono rimossi dai log; la CLI mostra il contenuto esatto di ogni file condivisibile, e la revisione
umana deve includere ogni voce elencata nel manifest.

Validazione locale indipendente dalle risorse installate:

```console
qwen-launcher validate --path <percorso-del-bundle>
```

La validazione controlla schema e semantica del report, riferimenti ai candidati, digest dei log,
completezza del manifest e stato non distribuibile della proposta. Non crea branch, issue o PR.
