# Calibrazione locale

## In breve

La calibrazione serve a trovare una configurazione adatta **a questo PC**. Non cambia il modello e
non migliora la qualità delle risposte: massimizza prima il contesto fattibile e poi confronta
throughput e margine di memoria nel dominio del protocollo v5.

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

### Nota di compatibilità del contratto motore

La preparazione del contratto per lo spike cross-context cambia il
`command_contract_sha256`. I record locali `calibration-record/v2`, `/v3` e `/v4` già presenti
restano leggibili per la diagnostica, ma non sono più riutilizzabili: rieseguire `calibrate`.
I seed pubblici v3 restano soltanto suggerimenti per l'ordine dei probe e non diventano mai buste.

`vstudio` conserva `--mmproj` ma non emette `--spec-type` o `--spec-draft-n-max`: la model card
appuntata non dichiara supportata la combinazione vision+MTP, nonostante lo Spike 0 locale l'avesse
completata. La scelta prudenziale resta attiva finché uno spike dedicato non fornisce nuova evidenza.

Con la migrazione `mode/v2` (0.1.4) i tre modi emettono anche `--min-p`, `--presence-penalty`,
`--repeat-penalty` e `--reasoning` (coding `on`; studio e vstudio `off`); temperatura, top-p e top-k
restano invariati. Questi token derivano dal contenuto del modo e non cambiano il
`command_contract_sha256`.

La calibrazione predefinita resta `calibration/v5`. `calibration/v6-lite` è disponibile come
protocollo **sperimentale opt-in** (`--protocol v6`): è stata implementata su decisione del
maintainer (D-063) prima del verdetto GO dello spike cross-context, che resta la precondizione per
promuoverla a default. Vedi [calibration/v6-lite (sperimentale)](#calibrationv6-lite-sperimentale).

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
con la mediana. Nello screening `14` è un cap: il conteggio usa `≤14` e il tempo è una proiezione
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
131072 → 98304 → 65536 → 49152 → 32768 → 16384 → 8192
```

È possibile fissare uno dei target approvati:

```bash
qwen-launcher calibrate --mode coding --target-ctx 98304
```

Valori ammessi: `131072`, `98304`, `65536`, `49152`, `32768`, `16384`, `8192`. Tutti appartengono
anche alla scala automatica; `--target-ctx` serve a fissarne uno per una misura separata. I candidati
vengono sempre confrontati allo stesso contesto.

`131072` è il tetto automatico del protocollo corrente, non una prova che il modello non supporti
contesti maggiori. Perciò “best fit” significa il migliore nel dominio v5 sopra elencato.

## Come funziona la ricerca v5

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
2. cerca il confine CUDA con al massimo 14 probe e processi freschi;
3. monitora RAM e VRAM ogni 250 ms;
4. richiede almeno 2,0 GiB RAM disponibili durante ogni trial;
5. su CUDA richiede almeno 0,3 GiB VRAM libera (circa 307 MiB) e rilascio entro 0,125 GiB dalla
   baseline;
6. considera la monotonia solo fra probe completati; un OOM parziale non inventa un picco;
7. sceglie il primo valore fattibile al confine e, se disponibile, il solo adiacente più prudente;
8. li conferma in due round accoppiati: `A→B` e `B→A`;
9. esegue un `benchmark/v1` completo in ciascuno dei quattro avvii;
10. usa il throughput solo se lo stesso finalista vince entrambi i round; altrimenti preferisce
    margine e prudenza.

Una deriva della baseline VRAM oltre 0,125 GiB disabilita la vittoria per throughput, ma non elimina
un finalista che ha rispettato le riserve assolute. Telemetria come utilizzo, clock, temperatura,
potenza e throttle è raccolta quando disponibile solo per spiegare l'evidenza; non introduce soglie.

Su CPU non esiste un asse di tuning verificato: per default v5 conferma la baseline del motore a
`ctx=8192` invece di simulare una ricerca. Un `--target-ctx` esperto può fissare uno degli altri
valori approvati, ma non introduce un asse automatico.

La ricerca CUDA trova quindi un confine di memoria e confronta due valori adiacenti: non esegue uno
sweep globale di `n_cpu_moe` e non dimostra che nessun valore lontano abbia throughput maggiore.
v5 conserva ricerca, benchmark e finalisti di v4, aggiunge i gradini 96K e 48K e porta il cap da 12
a 14 per mantenere sufficiente il budget nel caso peggiore. Produce `calibration-record/v4`; i
record storici v2/v3 restano leggibili.

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
differenza per assorbire il rumore di reporting osservato. Per il riuso servono fabbisogno RAM più
la riserva registrata e, su CUDA, fabbisogno VRAM più 0,3 GiB per record v3/v4 oppure 0,5 GiB per un
record storico v2. La migrazione non indebolisce quindi l'headroom di record già misurati.

Un file candidato, previous, invalido o con schema non supportato non pilota mai il lancio. I record
`calibration-record/v2`, `/v3` e `/v4` restano supportati e leggibili, ma quelli creati con il
contratto precedente non coincidono con il digest corrente e quindi non pilotano il lancio; `/v1` è
diagnosticato come superato. Il rimedio è rieseguire `calibrate`, non convertire file a mano.

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
`calibration-report/v2` del metodo storico v3. v5 usa quel report soltanto come seed d'ordine; non lo
presenta come prova della nuova riserva. Il report copre realmente un solo scope:

- Windows 11 build 10.0.26200;
- CUDA, driver NVIDIA 610.47;
- RTX 2060 SUPER 8 GiB;
- 31,92 GiB RAM;
- tutti e tre i modi.

Lo stato complessivo resta `GATE-PARTIAL`: il maintainer ha attestato Gate v4 reali su Ubuntu e
Windows prima della 0.1.1, ma manca ancora hardware materialmente diverso e il Gate Windows v4 non è
stato trasformato in evidenza pubblica. I valori osservati non vengono trasferiti. Il loader estrae
soltanto `n_cpu_moe` come seed d'ordine per modello, motore, backend e modo esatti; la macchina
dell'utente esegue comunque la ricerca completa.

Le fonti con checksum sono in
[`evidence/calibration/windows-11-rtx-2060-super-v3/`](../evidence/calibration/windows-11-rtx-2060-super-v3/).

## Contribuire nuova evidenza

La pubblicazione è manuale: il launcher non esegue login, upload, commit, branch remoto, issue o
pull request. Il contratto pubblico corrente descrive soltanto v3; non convertire un record privato
v5 in un report v2. Un contributo v5 richiede uno step dichiarativo separato con nuovo schema,
revisione privacy, manifest e checksum.

Per preparare il Gate senza attivare risultati:

```bash
qwen-launcher calibrate --mode all --no-activate
```

Conservare privatamente esito riuscito e fallimenti, senza hostname, username, seriali, UUID,
percorsi assoluti, credenziali, prompt o log grezzi. Il Gate Windows v4 attestato per la 0.1.1 non
sostituisce un futuro contributo pubblico redatto e manifestato.

Checklist per la pull request:

- [ ] schema pubblico versionato e metodo v5 coerenti;
- [ ] run riusciti e falliti riportati senza ricostruire campi mancanti;
- [ ] `privacy_reviewed=true` soltanto dopo revisione dei byte finali;
- [ ] scope, limite di portabilità, seed, SHA-256 e manifest espliciti;
- [ ] PR dichiarativa senza modifiche al core Python;
- [ ] `qwen-launcher validate`, Ruff, pytest, build e verifica wheel verdi.

## calibration/v6-lite (sperimentale)

`calibration/v6-lite` è un protocollo **opt-in** (`--protocol v6`); `calibration/v5` resta il default.
È stata implementata su decisione registrata del maintainer (D-063) prima del verdetto GO dello spike
cross-context: la promozione a default resta una decisione umana registrata in
`IMPLEMENTATION_SPEC.md`, mai dichiarata dall'agente.

Invece di una singola busta, v6-lite misura tre envelope per modo e ne scrive tutte nel record:

- **`fast`** — minima mediana end-to-end del prompt corto con `ctx ≥ 16384`;
- **`balanced`** — massimo contesto con end-to-end corto entro `1,10×` quello di `fast`;
- **`max_context`** — contesto massimo fattibile, con l'ordinamento throughput→margine→prudenza di v5.

Pipeline: ricerca hardware **condivisa** per `coding`+`studio` (stesso modello, backend, niente
mmproj, stesso MTP) sui contesti `131072 → 65536 → 32768` (raffinamento `98304`/`49152` adiacente al
vincitore); `vstudio` ha ricerca propria (`--mmproj`, speculative disabilitato). Per ogni gradino un
probe prudente a `n_cpu_moe = 41`, poi la bisezione del solo lato VRAM; i campioni `boundary`,
`boundary+2` e il punto prudente sono misurati con il **quick-bench** (1 warm-up + 3 richieste corte
non cached + 1 richiesta da ~8K). La selezione è confermata da un ABBA a 2 round con un terzo round
solo se ambiguo, poi da un gate finale per envelope (smoke a ~80% del contesto, multi-turn a 4 turni,
vision per `vstudio`). Attesa: circa **40–60 processi** per `--mode all`.

Riserve dei trial v6, scritte nel record: **0,5 GiB VRAM, 2,0 GiB RAM, 0,125 GiB** di tolleranza al
rilascio. Al lancio si valuta **solo** l'envelope `active_preference` con i suoi fabbisogni misurati;
se l'headroom non basta si usa la baseline (`ctx=8192`, `n_cpu_moe=48`). `--preference` fissa la
busta attiva nel record (default `balanced`) e non modifica mai `config.toml`; `--target-ctx`
collassa la scala su un solo gradino. Il record è `calibration-record/v5`: identità e digest come v4,
le tre envelope, le soglie, le riserve e gli input di selezione (mediane per round) sufficienti a
ricostruire la scelta; probe, scarti e log restano nell'albero `evidence/`.

Nota: l'adapter di trial reale è validato su hardware; la logica di ricerca, selezione, conferma,
gate e record è coperta da test offline con fake.

## Laboratorio v1

`--protocol v1` resta disponibile per prove esplicite e compatibilità del bundle. Richiede candidati
e impostazioni tecniche, misura solo la lista fornita e produce una bozza sotto
`data_dir()/calibrations/`. Non monitora la RAM, non crea un `calibration-record/v4` e non attiva
risultati. Per un nuovo utente il percorso corretto è sempre il protocollo v5 predefinito.

**Successivo:** [Operazioni e diagnostica](operations.md)
