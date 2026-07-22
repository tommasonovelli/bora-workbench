# Calibrazione locale

## In breve

La calibrazione serve a trovare una configurazione adatta **a questo PC**. Non cambia il modello e
non migliora la qualità delle risposte: massimizza prima il contesto fattibile e poi confronta
throughput e margine di memoria nel dominio verificato dal protocollo v3.

Per iniziare non occorre conoscere i parametri di `llama.cpp`:

```bash
qwen-launcher calibrate --mode all
```

Il comando:

1. controlla modello, motore, memoria e processi concorrenti;
2. mostra cosa eseguirà e chiede conferma;
3. avvia più server temporanei, quindi può durare da molti minuti a ore;
4. misura separatamente `coding`, `studio` e `vstudio`;
5. salva un record privato per ogni modo completato;
6. attiva per default i record, che saranno valutati al lancio successivo.

Non effettua upload, non modifica `config.toml` e non pubblica risultati.

## Termini essenziali

- **Baseline**: configurazione verificata ma non ottimizzata (`ctx=8192`; su CUDA
  `n_cpu_moe=48`). Permette di usare il launcher senza calibrazione.
- **Busta**: coppia di parametri prestazionali scelta per un modo, principalmente `ctx` e, su CUDA,
  `n_cpu_moe`.
- **`ctx`**: limite della finestra di contesto del server, espresso in token.
- **`n_cpu_moe`**: numero di blocchi MoE lasciati sulla CPU; valori minori usano più VRAM, valori
  maggiori spostano pesi e lavoro verso RAM e CPU. Il throughput non è assunto monotono.
- **Record locale**: JSON privato che conserva misure, identità della macchina e busta selezionata.
- **Candidato**: record valido ma non ancora usato dai lanci.
- **Record attivo**: unico record che può entrare nel piano di lancio.
- **Seed condiviso**: suggerimento sull'ordine dei probe proveniente da evidenza pubblica; non è una
  configurazione da copiare.
- **Headroom**: memoria libera oltre il fabbisogno misurato.
- **Benchmark**: misura ripetibile di una busta già scelta; da solo non è una calibrazione.

## Prima di iniziare

Servono:

- modello predefinito e, per `vstudio`, mmproj già presenti e verificabili;
- `llama.cpp b10011` compatibile già disponibile;
- almeno 28 GiB RAM totali e 22 GiB disponibili al preflight;
- nessun servizio gestito attivo;
- su CUDA, una sola GPU NVIDIA e nessun workload GPU intensivo concorrente.

Controllare prima:

```bash
qwen-launcher validate
qwen-launcher doctor
qwen-launcher engine status
qwen-launcher status
```

La calibrazione usa `llama_port` quando è libera. Nel branch corrente, se la porta è occupata,
ciascun trial sceglie una porta temporanea su `127.0.0.1`; gli avvii ordinari restano severi sulla
porta configurata. Questa correzione non è presente negli artefatti pubblici `0.1.0`.

### Contesti GPU concorrenti

Fuori da WDDM un processo compute già presente rende la misura inaffidabile e blocca il run. Su
Windows/WDDM alcuni processi desktop sono inevitabili: il launcher cattura una popolazione iniziale
per l'intero run usando PID, tempo di creazione e identità opaca dell'eseguibile. Un respawn dello
stesso eseguibile è ammesso entro la molteplicità iniziale; file nuovi, identità illeggibili o istanze
aggiuntive invalidano il run. Le differenze Ubuntu/Windows e il carico desktop non producono
profili OS hardcoded: entrano nella decisione tramite RAM/VRAM e baseline osservate sul posto.

## Uso normale

Calibrare tutti i modi e attivare i risultati:

```bash
qwen-launcher calibrate --mode all
```

Calibrare un solo modo:

```bash
qwen-launcher calibrate --mode coding
```

Su un terminale interattivo la CLI mostra spinner, barra, tempo trascorso, trial in corso e tempo
rimanente appreso soltanto dalla fase corrente. Lo screening attende due processi e usa la mediana;
la conferma, che ha trial omogenei e totale esatto, mostra una prima ETA dopo il primo e la stabilizza
con la mediana. Nello screening `12` è un cap: il conteggio usa `≤12` e il tempo è una proiezione
fino al cap, non un limite garantito. Se l'output è rediretto, viene mantenuta una riga stabile per
ogni trial completato. Al termine, il riepilogo spiega la regola di selezione e i minimi RAM/VRAM
misurati.

Un crash di un trial è isolato dal servizio di produzione; il motivo e i log vengono conservati.

Al termine verificare:

```bash
qwen-launcher doctor
qwen-launcher coding
```

Se il record è valido e ha headroom sufficiente, l'avvio mostra `local-calibration-record`; altrimenti
spiega il motivo e usa la baseline.

## Misurare senza attivare

Per un esperimento o per preparare evidenza:

```bash
qwen-launcher calibrate --mode all --no-activate
```

I risultati vengono scritti come:

```text
data_dir()/calibration/records/<modo>.candidate.json
```

I lanci continuano a usare il record attivo precedente o la baseline. Dopo aver controllato
`doctor`, promuovere i candidati senza ripetere i trial:

```bash
qwen-launcher calibrate --mode all --activate
```

La promozione è atomica. Se esiste già un attivo, ne viene conservata una copia in:

```text
<modo>.previous.json
```

Esiste un solo slot precedente; non c'è un comando CLI di rollback automatico. Non rinominare o
modificare manualmente i record.

## Contesto esplicito per utenti esperti

La ricerca normale prova in ordine:

```text
131072 → 65536 → 32768 → 16384 → 8192
```

È possibile fissare uno dei target approvati:

```bash
qwen-launcher calibrate --mode coding --target-ctx 98304
```

Valori ammessi: `131072`, `98304`, `65536`, `32768`, `16384`, `8192`. `98304` è disponibile solo
come target esplicito e non cambia la scala automatica. Se la ricerca automatica si ferma a 65536,
la CLI propone il comando 98304 con `--no-activate` come misura separata, senza implicarne la
fattibilità. I candidati vengono sempre confrontati allo stesso contesto.

`131072` è il tetto automatico del protocollo corrente, non una prova che il modello non supporti
contesti maggiori. Perciò “best fit” significa il migliore nel dominio v3 sopra elencato.

## Come funziona la ricerca v3

Questa sezione spiega l'algoritmo; non è necessaria per usare il comando.

L'obiettivo è lessicografico:

1. massimo contesto fattibile;
2. throughput confermato a quel contesto;
3. maggiore margine di memoria;
4. configurazione più prudente.

Su CUDA il dominio di `n_cpu_moe` viene letto dai metadati del GGUF ed è `[0, block_count]`; per il
modello appuntato il massimo atteso e verificato è 41. Un report condiviso può suggerire il primo
punto, ma non restringe il dominio.

Per ogni modo il calibratore:

1. scende nella scala dei contesti solo se la configurazione più prudente non è fattibile;
2. cerca il confine CUDA con al massimo 12 probe e processi freschi;
3. monitora RAM e VRAM ogni 250 ms;
4. richiede almeno 2,0 GiB RAM disponibili durante ogni trial;
5. su CUDA richiede almeno 0,5 GiB VRAM libera e rilascio entro 0,125 GiB dalla baseline;
6. considera la monotonia solo fra probe completati; un OOM parziale non inventa un picco;
7. sceglie il primo valore fattibile al confine e, se disponibile, il solo adiacente più prudente;
8. li conferma in due round accoppiati: `A→B` e `B→A`;
9. esegue un `benchmark/v1` completo in ciascuno dei quattro avvii;
10. usa il throughput solo se lo stesso finalista vince entrambi i round; altrimenti preferisce
    margine e prudenza.

Una deriva della baseline VRAM oltre 0,125 GiB disabilita la vittoria per throughput, ma non elimina
un finalista che ha rispettato le riserve assolute. Telemetria come utilizzo, clock, temperatura,
potenza e throttle è raccolta quando disponibile solo per spiegare l'evidenza; non introduce soglie.

Su CPU non esiste un asse di tuning verificato: per default v3 conferma la baseline del motore a
`ctx=8192` invece di simulare una ricerca. Un `--target-ctx` esperto può fissare uno degli altri
valori approvati, ma non introduce un asse automatico.

La ricerca CUDA trova quindi un confine di memoria e confronta due valori adiacenti: non esegue uno
sweep globale di `n_cpu_moe` e non dimostra che nessun valore lontano abbia throughput maggiore.
Cambiare scala, assi, benchmark o finalisti sarebbe un nuovo metodo con nuovi record, non una
correzione silenziosa di `calibration/v3`.

## `benchmark/v1`

Ogni sessione valida esegue:

1. un warm-up completo escluso dai risultati;
2. cinque richieste misurate;
3. esattamente 256 completion token per richiesta;
4. `max_tokens=256`, `ignore_eos=true` e seed `424242`;
5. controllo di `finish_reason=length`, conteggio token e timing;
6. riepilogo minimo, mediana e massimo.

Le risorse del prompt e della richiesta sono immutabili nella wheel. Tok/s misura la velocità della
busta nelle condizioni osservate, non la qualità semantica e non una promessa per un'altra macchina.
La CLI corrente non espone un comando autonomo `benchmark`.

## Record e riuso

Un record attivo viene rivalidato a ogni lancio. Devono coincidere:

- schema e ricostruzione di probe, sessioni, mediane e selezione;
- modello, filename e digest;
- release, commit e digest del contratto motore;
- modo e backend;
- OS, CPU/GPU, driver e identità hardware stabile;
- memoria disponibile corrente.

Il totale RAM registrato resta esatto; nel branch corrente il confronto ammette al massimo 1 MiB di
differenza per assorbire il rumore di reporting osservato. Per il riuso servono fabbisogno RAM
misurato + 2,0 GiB e, su CUDA, fabbisogno VRAM + 0,5 GiB.

Un file candidato, previous, invalido o con schema non supportato non pilota mai il lancio. I record
`calibration-record/v1` sono diagnosticati come superati; il rimedio è rieseguire `calibrate`, non
convertirli a mano.

## File privati

I record vivono in:

```text
data_dir()/calibration/records/
```

I log e l'evidenza dettagliata dell'ultimo run vivono in:

```text
data_dir()/calibration/evidence/<run-id>/
```

Dopo che un nuovo run è stato preservato, il launcher elimina soltanto le precedenti directory di
evidenza con nome UUID gestito. Questi file possono contenere dettagli operativi e non vanno
pubblicati senza revisione.

## Evidenza condivisa e limite empirico

La wheel distribuisce una policy `calibration-policy/v2` e un report
`calibration-report/v2`. Il report copre realmente un solo scope:

- Windows 11 build 10.0.26200;
- CUDA, driver NVIDIA 610.47;
- RTX 2060 SUPER 8 GiB;
- 31,92 GiB RAM;
- tutti e tre i modi.

Lo stato complessivo resta `GATE-PARTIAL`: le costanti non sono state ripetute su hardware
materialmente diverso. I valori osservati non vengono trasferiti. Il loader estrae soltanto
`n_cpu_moe` come seed d'ordine per modello, motore, backend e modo esatti; la macchina dell'utente
esegue comunque la ricerca completa.

Le fonti con checksum sono in
[`evidence/calibration/windows-11-rtx-2060-super-v3/`](../evidence/calibration/windows-11-rtx-2060-super-v3/).

## Contribuire nuova evidenza

La pubblicazione è manuale: il launcher non esegue login, upload, commit, branch remoto, issue o
pull request.

1. Eseguire un run reale senza attivazione:

   ```bash
   qwen-launcher calibrate --mode all --no-activate
   ```

2. Non copiare record o log grezzi nel repository. Preparare un report `calibration-report/v2`
   privacy-safe con soli modi completati e misure reali.
3. Usare un id ASCII minuscolo con trattini, per esempio `<os>-<gpu>-v3`, e salvare il report in
   `src/qwen_launcher/resources/content/calibrations/<id>.json`.
4. Aggiungere fonti revisionate e un manifest sotto `evidence/calibration/<id>/`.
5. Aggiornare il riferimento e lo SHA-256 esatto nella policy.
6. Mantenere `gate-partial` finché il nuovo insieme di prove non autorizza onestamente uno scope più
   ampio.
7. Eseguire validazione, suite, build e verifica wheel.

Non includere hostname, username, seriali, UUID, percorsi assoluti, credenziali, configurazione,
prompt utente o record privati. Non aggiungere `profile/v1`, nearest-match o promesse tok/s.

Checklist per la pull request:

- [ ] run `calibration/v3` reale sul modello e motore appuntati;
- [ ] report limitato ai modi completati, senza campi ricostruiti;
- [ ] `privacy_reviewed=true` dopo revisione dei byte finali;
- [ ] scope e limite di portabilità espliciti;
- [ ] seed di solo ordinamento;
- [ ] SHA-256 e manifest aggiornati;
- [ ] PR di contenuto, senza modifiche al core Python;
- [ ] `qwen-launcher validate`, Ruff, pytest, build e verifica wheel verdi.

## Laboratorio v1

`--protocol v1` resta disponibile per prove esplicite e compatibilità del bundle. Richiede candidati
e impostazioni tecniche, misura solo la lista fornita e produce una bozza sotto
`data_dir()/calibrations/`. Non monitora la RAM, non crea un record v3 e non attiva risultati. Per un
nuovo utente il percorso corretto è sempre il protocollo v3 predefinito.

**Successivo:** [Operazioni e diagnostica](operations.md)
