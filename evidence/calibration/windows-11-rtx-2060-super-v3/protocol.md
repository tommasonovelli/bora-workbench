# `calibrate_v3.md` — Ridisegno implementato della conferma `calibration/v3`

> **Stato:** design approvato, implementato e sostenuto dal Gate v3 Windows CUDA dello Step 5A.
> Risponde al run reale `coding` del 18 luglio 2026 (`CALIBRATION-REJECTED` per v2); il run pulito
> `--mode all --no-activate` del 19 luglio è `CALIBRATION-ACCEPTED` localmente per coding, studio e
> vstudio. La copertura empirica resta `GATE-PARTIAL`; D-047 autorizza Step 5B e rinvia hardware
> materialmente diverso a un follow-up futuro non bloccante.
> **Data:** 19 luglio 2026. **Evidenza citata:** `docs/calibration-gate-v3-windows.md`, record
> `calibration-record/v1` del run v2, `docs/calibration-v2-design.md` e mini-spike.

## 1. Sintesi

Il run del 18 luglio è formalmente corretto ma non convincente, e il difetto non è un bug: è un
limite strutturale del disegno della conferma. Gli otto problemi osservati hanno tre cause radice:

1. **i finalisti sono misurati in finestre temporali disgiunte**, su un ambiente che deriva nel
   tempo, con una statistica d'ordine estrema (il massimo) che un singolo burst rende decisiva —
   da qui i problemi 1, 2, 3 e la scelta di 38 nonostante l'11% di svantaggio mediano;
2. **obiettivo e ciclo di vita sono impliciti** — il protocollo non dichiara che cosa ottimizza
   (problema 4) e attiva il record prima che il Gate lo accetti (problema 8);
3. **evidenza e riserve sono incomplete** — telemetria GPU assente (5), RAM passiva (6), record
   che non conserva i singoli avvii e log cancellati (7).

La soluzione implementata, `calibration/v3`, non aggiunge statistica: **cambia la geometria della
misura in modo che la deriva ambientale si cancelli da sola**, e rende espliciti obiettivo e
ciclo di vita. In cinque punti:

1. **Conferma accoppiata (ABBA).** Stessi 4 avvii freschi di oggi, ma intercalati per round:
   round 1 `A→B`, round 2 `B→A`, con `benchmark/v1` completo su ogni avvio. Ogni finalista è
   quindi misurato due volte, su due processi freschi, in posizioni temporali medie identiche.
2. **Dominanza per unanimità dei round.** A domina B soltanto se la mediana di sessione di A
   supera quella di B **in ogni round**. Nessuna nuova soglia: la regola resta derivata soltanto
   dalle misure locali. Senza unanimità i finalisti sono equivalenti e decide, come oggi, il
   margine VRAM e poi la prudenza.
3. **Riserva RAM universale** (2,0 GiB) con la stessa semantica della riserva VRAM: violarla
   durante un trial rende il probe non fattibile o scarta il finalista. Il Gate locale non l'ha
   avvicinata; la prova su capacità diverse resta un follow-up D-047 non bloccante.
4. **Record `calibration-record/v2`** con evidenza per singolo avvio (baseline, picco, rilascio e
   sua durata, RAM, sessione benchmark, telemetria GPU, ordine temporale) e conservazione dei log
   dell'ultimo run; `validate` ricostruisce round, unanimità e scelta.
5. **Ciclo candidato → attivo.** Il record nasce `candidate` e viene promosso atomicamente ad
   attivo nello stesso comando (l'utente ignaro continua a fare tutto con un solo `calibrate`);
   `--no-activate` ferma la promozione per i run sperimentali del Gate. Il passaggio di schema
   v1→v2 rende inoltre il record respinto di oggi automaticamente inerte, senza migrazioni.

Costo rispetto a oggi: **zero avvii in più** (4 come ora), due sessioni benchmark aggiuntive
(~24 richieste totali contro 14, pochi minuti). Lo screening non cambia: resta la bisezione
misurata entro 12 probe, con due sole correzioni di robustezza (sezione 4).

### L'esperienza utente resta il requisito

Il principio guida non cambia ed è il metro di ogni scelta qui sotto: l'utente che non sa nulla
di `llama-server` esegue `qwen-launcher calibrate`, aspetta, e ottiene la migliore configurazione
per la sua macchina — zero input obbligatori, nessun secondo comando, nessuna decisione tecnica.
Tutta la sofisticazione di questa proposta è interna al protocollo; l'interfaccia resta un solo
comando che finisce con un verdetto in linguaggio piano. Le uniche opzioni nuove (`--no-activate`,
`--target-ctx`) sono facoltative e pensate per il maintainer o l'utente esperto; il percorso
predefinito non le richiede mai.

## 2. Diagnosi: perché il protocollo ha scelto 38

I numeri del record reale:

| Finalista | Misure (tok/s) | Mediana | Massimo | VRAM minima libera |
|---|---|---:|---:|---:|
| 37 | 22,19 · 22,28 · 24,20 · 23,18 · 22,85 | 22,85 | 24,20 | 0,649 GiB |
| 38 | 23,79 · 23,77 · 18,69 · 19,71 · 20,52 | 20,52 | 23,79 | 0,930 GiB |

La regola attuale chiede alla mediana di 37 (22,85) di superare il massimo di 38 (23,79). Le
prime due misure di 38 appartengono però a un regime veloce che scompare a metà sessione
(23,79 → 18,69): la serie non è stazionaria, e il massimo — la statistica più fragile che esista —
fotografa proprio il regime scomparso. Un solo burst ambientale di 38 annulla così un vantaggio
mediano dell'11,35% di 37, e la regola ripiega sul margine VRAM.

Il punto essenziale: **su un desktop reale il rumore non è i.i.d., è deriva più burst.** Qualsiasi
regola che confronti due serie raccolte in momenti diversi — con qualunque statistica — resta
esposta alla domanda «è più veloce il candidato o era più scarico il PC?». Il protocollo attuale
non può rispondere, perché misura 37 per intero e poi 38 per intero (problema 3), benchmarka ogni
finalista una sola volta (problema 2) e non conserva l'evidenza per distinguere i casi
(problema 7).

Le alternative scartate, e perché:

- **test statistici di stazionarietà o di significatività** (confronto fra metà serie, trend,
  rango): richiedono soglie di significanza, cioè costanti inventate, vietate dai principi del
  progetto (`CALIBRATE.md` sezione 2.2: il criterio deriva dal rumore misurato localmente);
  inoltre aggiungono cicli di ri-misura dalla durata non prevedibile;
- **più misure per sessione** (10, 20…): pagano tempo lineare per un problema che non è la
  varianza veloce (già domata dalla mediana di 5) ma la deriva lenta, che più misure nella stessa
  finestra temporale non correggono affatto;
- **fasce di equivalenza fisse** («2%»): già escluse dall'evidenza dei due host (dispersione
  0,14–18,8% sullo stesso hardware).

La risposta giusta è progettuale, non statistica: **rendere il confronto equo per costruzione**,
in modo che la deriva colpisca entrambi i finalisti allo stesso modo. È il classico disegno
accoppiato ABBA, ed è più semplice — non più complesso — del protocollo attuale da spiegare.

## 3. Il cuore della proposta: conferma accoppiata e unanimità dei round

### 3.1 Struttura della conferma

Per i due finalisti A (confine, più aggressivo) e B (vicino prudente), la conferma esegue
`CONFIRM_ROUNDS = 2` round deterministici:

```text
round 1:  avvio fresco A (benchmark/v1 completo)  →  avvio fresco B (benchmark/v1 completo)
round 2:  avvio fresco B (benchmark/v1 completo)  →  avvio fresco A (benchmark/v1 completo)
```

- ogni avvio resta un processo fresco, isolato, con carico reale del modo, monitor VRAM e RAM a
  250 ms e verifica del rilascio: nulla di ciò che oggi rende un avvio «stabile» viene rimosso;
- **ogni avvio esegue `benchmark/v1` completo** (un warm-up escluso più cinque misure): «2 avvii
  stabili» torna a significare «prestazioni confermate su 2 avvii» (problema 2);
- l'ordine interno si inverte al secondo round: sotto una deriva lineare le posizioni temporali
  medie di A (1ª e 4ª) e B (2ª e 3ª) sono identiche, quindi la deriva non favorisce nessuno
  (problema 3);
- l'ordine è fisso e deterministico, mai casuale: `validate` deve poterlo ricostruire;
- il numero di avvii per finalista resta 2: la costante D-039 «2 avvii stabili» diventa
  «2 round», senza costi aggiuntivi di caricamento.

`benchmark/v1` non cambia di una virgola (risorse byte-identiche, un warm-up, cinque misure):
cambia soltanto quante sessioni la calibrazione esegue e come le confronta. Il protocollo di
benchmark e quello di calibrazione restano versionati separatamente.

### 3.2 Regola di selezione

Per il finalista F e il round r, la **mediana di sessione** `m(F, r)` è la mediana delle cinque
misure di quella sessione — robusta ai singoli burst per costruzione.

> **A domina B se e solo se `m(A, r) > m(B, r)` in ogni round.** Altrimenti i finalisti sono
> equivalenti e si applica l'ordine attuale: maggiore VRAM libera minima osservata, poi il più
> prudente. Una parità esatta in un round non è una vittoria.

Proprietà, tutte verificabili dal record:

- **zero costanti nuove**: niente fasce, niente percentuali, niente p-value; solo confronti
  d'ordine fra misure locali — esattamente il vincolo di design che ha già escluso le soglie
  fisse;
- **simmetrica** (l'attuale «mediana di A contro massimo di B» non lo era) e al riparo dal veto
  del singolo outlier: il massimo grezzo non è più decisionale, sopravvive solo come evidenza;
- **l'unanimità è il test di equivalenza implicito**: un vantaggio reale e riproducibile vince
  entrambi i round accoppiati; un vantaggio che appare una volta sola — burst, deriva, bimodalità
  — produce round discordi e ricade in sicurezza sul margine di memoria. Su host quieto
  (dispersione < 1%) l'unanimità emerge quasi sempre; su host rumoroso la regola degrada nello
  stesso ripiego prudente di oggi, ma soltanto quando il disaccordo è reale;
- **deterministica e ricostruibile**: `validate` ricalcola mediane di sessione, vincitori di
  round, unanimità e tie-break dai dati per-avvio del record.

Etichette di selezione risultanti (registrate nel record): `dominance-unanimous-rounds`,
`equivalent-prefer-minimum-free-vram`, `equivalent-prefer-prudent`,
`equivalent-after-baseline-drift` (sezione 3.3), `single-finalist`, `cpu-baseline-confirmation`.

### 3.3 Deriva di baseline: da scarto a degradazione onesta

Oggi una deriva di baseline oltre 0,125 GiB fra i due avvii di un finalista lo **scarta**. Con
l'intercalazione i due avvii dello stesso finalista distano di più nel tempo, e su WDDM la
baseline del desktop oscilla già di ~0,1 GiB: mantenere lo scarto significherebbe bocciare
entrambi i finalisti su molti host normali e far fallire l'intero run — l'opposto della
generalità richiesta.

La correzione usa un fatto già vero nel codice: la sicurezza di memoria **non dipende** dalla
stabilità della baseline, perché la riserva è verificata su ogni campione come VRAM libera
assoluta (`_calibration_vram.py`: `vram_free_gib < minimum_free_gib` su ogni campione). Se
l'ambiente si prende memoria e la riserva regge, la busta è ancora più dimostrata; se la riserva
cade, il probe/finalista è già scartato dalla regola esistente.

Quindi in v3 la deriva di baseline oltre tolleranza durante la conferma:

- **non scarta nessun finalista** (nessuno dei due ne ha colpa);
- **spegne le pretese di dominanza**: la selezione dichiara equivalenza con etichetta
  `equivalent-after-baseline-drift` e decide per margine VRAM e prudenza — se l'ambiente si è
  mosso, il confronto di velocità non è affidabile e il protocollo lo dice, invece di fingere;
- resta registrata per avvio nel record (baseline di ognuno dei 4 avvii, escursione complessiva).

Le invalidazioni di run restano severe: un file eseguibile compute estraneo alla baseline WDDM
(D-046), cambio driver, cambio capacità o monitor guasto. Un respawn dello stesso file entro la
molteplicità iniziale è soltanto evidenza; non modifica riserve o selezione.

### 3.4 Il run del 18 luglio sotto la nuova regola

Onestà prima di tutto: un protocollo diverso avrebbe prodotto misure diverse; il run non è
rieseguibile a tavolino. Ma i due esiti possibili sono entrambi difendibili, ed è questo il
punto:

- **se il regime veloce di 38 era ambiente** (PC più scarico a inizio conferma), i round
  intercalati lo fanno assaggiare a entrambi i finalisti; le mediane di sessione di 37
  (22,8–23,2 osservate) battono quelle del regime lento di 38 (19,7–20,5) in entrambi i round →
  **dominanza, vince 37**, cioè il candidato 11% più veloce che il protocollo attuale ha perso;
- **se 38 è genuinamente bimodale fra avvii freschi** (a volte parte «veloce»), i round si
  dividono → equivalenza → margine → vince 38, ma stavolta la scelta poggia su evidenza
  accoppiata e il record mostra il perché, invece di un massimo solitario.

In entrambi i casi la risposta alla domanda «più veloce lui o più scarico il PC?» è nel record.

## 4. Screening: due correzioni di robustezza, nessun cambio di strategia

La bisezione misurata resta com'è (è già la parte che funziona: confine 37 trovato in 7 probe su
12). Due correzioni:

1. **La verifica di monotonia usa solo i probe fattibili.** Oggi `has_monotonic_violation`
   confronta anche i picchi dei probe falliti. Ma il picco di un probe OOM è un'osservazione
   troncata (il processo muore a caricamento parziale): su un'altra macchina può risultare
   *inferiore* al picco di un probe prudente riuscito e innescare una degradazione lineare
   spuria che brucia il budget. I probe non fattibili devono contribuire solo il segno di
   fattibilità alla bisezione; il modello monotono si verifica sui soli caricamenti completi.
   È una correzione di portabilità pura (nel run reale i picchi saturi 7,79–7,83 GiB non hanno
   fatto danni per pochi centesimi di GiB).
2. **Split guidato dall'interpolazione, con fallback a bisezione.** I picchi
   fattibili misurati sono già quasi perfettamente lineari nell'asse: 41→5,61, 39→6,40,
   38→6,89, 37→7,34 GiB, ossia ~0,4 GiB per blocco. Dopo due probe fattibili si può stimare il
   confine per interpolazione (qui: limite 8,0−0,5=7,5 GiB → previsione ≈ 37) e puntare il
   probe lì, invece che sul punto medio cieco (20). Regola di sicurezza: il punto interpolato
   vale solo se cade dentro la staffa corrente e la restringe, altrimenti punto medio — la
   correttezza resta quella della bisezione, la predizione **ordina e non esclude mai**
   (stesso principio dei seed, D-035/D-038). Tipico: 4–5 probe invece di 6–7; caso peggiore
   invariato. L'implementazione v3 lo usa esclusivamente come ordinamento interno alla staffa.

## 5. Riserva RAM universale (problema 6)

Costante implementata, simmetrica alla riserva VRAM:

> `RAM_RESERVE_GIB = 2,0`: se durante un trial la RAM disponibile minima scende sotto
> la riserva, il probe è non fattibile / il finalista è scartato, con motivo esplicito
> («minimum available RAM reserve was violated»).

Motivazione del valore: è un margine assoluto contro la paginazione, indipendente dalla taglia
della macchina (Windows degrada in modo simile vicino all'esaurimento a 16 come a 64 GiB); i
prerequisiti attuali (28 GiB totali) e la misura reale (minimo 9,6 GiB disponibili) lo rendono
inerte sugli host sani e attivo solo dove oggi accetteremmo una busta al limite del thrashing.
Provenienza dichiarata: questa proposta. Il Gate Windows ha osservato almeno 8,602 GiB disponibili
nei trial accettati, quindi ha verificato il monitor e la regola ma non ha stressato la soglia; la
validazione su hardware con meno RAM resta aperta.

Coerenza con il riuso: il controllo di headroom al lancio richiede già
`RAM disponibile ≥ fabbisogno misurato`; diventa `≥ fabbisogno + riserva RAM`, speculare al ramo
VRAM.

Caveat misurato da registrare nel design: con mmap gran parte del modello è page cache
reclamabile; la «RAM disponibile» di Windows include la standby list, quindi la riserva colpisce
soprattutto le allocazioni private reali — è il comportamento voluto, ma il Gate deve osservarlo
almeno una volta su un host con meno RAM prima di dichiarare il valore definitivo.

## 6. Telemetria GPU: evidenza, non decisione (problema 5)

Il monitor VRAM interroga già `nvidia-smi` ogni 250 ms: la stessa query può chiedere anche
`utilization.gpu`, `temperature.gpu`, `clocks.current.sm`, `power.draw` e i flag di throttling dichiarati
dal driver (`clocks_event_reasons.active` / alias storico `clocks_throttle_reasons.active`).
Costo zero, nessun campionatore nuovo.

Regole:

- **evidence-only in v3**: la telemetria finisce nel record per avvio (aggregati: utilizzo
  massimo, clock SM minimo, temperatura massima, flag di throttling osservati) e spiega i casi
  «regime veloce/lento» come quello di 38; **nessuna decisione** dipende da essa, perché ogni uso
  decisionale richiederebbe soglie («quanto caldo è troppo?») che i principi vietano — e su GPU
  piccole il thermal throttling sotto carico prolungato è normale, non un ambiente invalido;
- **portabilità garantita**: campi non supportati dal driver → `null` nel record, mai un errore
  (una query di telemetria fallita non deve rompere una calibrazione);
- il Gate, con evidenza raccolta, potrà decidere se un flag del driver (che non è una soglia
  inventata: lo dichiara l'hardware) meriti di diventare decisionale in un protocollo futuro.

Questo risponde anche al limite WDDM residuo: un contesto desktop già presente che inizia a
lavorare non cambia necessariamente istanza, ma lascia traccia in utilizzo/clock e nel confronto fra
round.

### 6.1 Identità WDDM a scope di run (D-046)

Due tentativi reali del Gate hanno mostrato lo stesso contesto desktop ricreato con PID diversi. Il
PID era quindi un proxy asimmetrico: ammetteva qualunque cambio di attività finché l'istanza restava
viva, ma invalidava il lifecycle ordinario dello stesso eseguibile. V3 usa ora una baseline
immutabile per l'intero run:

- ogni istanza è `pid + create_time`; il processo gestito è escluso soltanto con questa coppia;
- l'eseguibile usa un digest locale di volume/file-id (`st_dev + st_ino`), senza conservare percorsi;
- il multiset corrente deve essere un sotto-multiset della popolazione iniziale. Un respawn dello
  stesso file è ammesso entro la molteplicità iniziale; file nuovi, identità illeggibili o istanze
  aggiuntive invalidano ancora il run;
- i respawn sono contati come evidenza per trial e non alimentano soglie o selezione;
- i gap fra trial non sono campionati. Un evento interamente confinato nel gap non sovrappone una
  misura; se persiste nel trial successivo viene confrontato con la baseline di run e non può essere
  assorbito silenziosamente.

La regola governa l'igiene della misura, non la sicurezza contro processi ostili. Riserve assolute,
ABBA, telemetria e divieto di workload concorrenti restano invariati.

## 7. Record `calibration-record/v2` ed evidenza (problema 7)

Lo schema v2 conserva tutto ciò che serve a rifare i conti del run senza i log:

- **per ogni avvio di conferma** (e in forma ridotta per ogni probe): round, posizione globale
  nell'ordine temporale, timestamp di inizio/fine, baseline/picco/minimo libero VRAM, valore e
  **durata del rilascio**, baseline/minimo RAM, sessione benchmark completa (warm-up + 5 misure),
  telemetria (o `null`), numero di contesti WDDM iniziali e respawn ammessi evidence-only;
- **per la selezione**: mediane di sessione, vincitore di ogni round, esito
  unanimità/equivalenza, escursione delle baseline della conferma, flag
  `equivalent-after-baseline-drift`;
- invariati: identità hardware/contratti, busta, minimi osservati, costanti dell'algoritmo,
  probe di screening con esiti e motivi.

I **log runtime dell'ultimo run** vengono conservati (oggi `.runtime-*` viene cancellato):
directory `calibration/evidence/<run-id>/` con rotazione a uno slot — il run nuovo elimina il
precedente solo dopo aver scritto il proprio. Disco limitato, diagnosi possibile, niente crescita
infinita. I record restano privati e locali; il percorso di condivisione con redazione e privacy
scanner non cambia (timestamp e telemetria locali non sono identificativi, e comunque non
lasciano la macchina se non via bundle redatto).

`verify_record` v2 estende la ricostruzione attuale: mediane per sessione dalle misure
memorizzate, vincitori di round, unanimità, tie-break, coerenza fra evidenza per-avvio e
aggregati — la scelta resta dimostrabile a freddo, requisito già esistente (D-038) applicato alla
nuova regola.

## 8. Ciclo di vita: candidato → attivo (problema 8)

- `calibrate` scrive prima `records/<modo>.candidate.json`, poi — comportamento predefinito — lo
  **promuove atomicamente** a `records/<modo>.json` (rename nella stessa directory); l'eventuale
  attivo precedente sopravvive come `<modo>.previous.json` (uno slot, rollback a costo zero).
  L'utente ignaro continua a vivere con un solo comando e il record attivo subito: D-038 resta
  vero alla lettera.
- `--no-activate` ferma il flusso al candidato: è la modalità per i run sperimentali del Gate — un
  risultato non accettato non diventa operativo. `doctor` mostra per
  modo lo stato: attivo, candidato in attesa, assente, invalido, schema superato, senza headroom.
  Un successivo `calibrate --activate` promuove il candidato senza rieseguire la ricerca.
- **Il record respinto di oggi si neutralizza da solo**: quando v3 arriva, `coding.json` (schema
  v1, protocollo v2) non supera più la validazione di caricamento e ogni lancio ripiega sulla
  baseline con diagnostica azionabile («record di protocollo superato: riesegui calibrate»).
  Niente codice di migrazione. La quarantena manuale del file attuale come evidenza (spostarlo
  sotto `data/calibrations/`) resta un'azione esplicita da fare **solo su autorizzazione** — non
  è stata eseguita in questa sessione.

## 9. L'obiettivo dichiarato (problema 4)

`calibration/v3` dichiara l'obiettivo — nel design, nel record (`objective`) e nell'output:

> **Obiettivo lessicografico:** (1) il contesto massimo fattibile sulla scala approvata del modo;
> (2) a quel contesto, il throughput confermato dalla dominanza accoppiata; (3) a parità, il
> margine di memoria; (4) a parità, la prudenza.

Perché contesto-prima resta il default giusto per l'utente ignaro:

- il contesto è capacità funzionale (un agente di coding con 131k *può fare cose* che con 32k
  non può); i tok/s sono comfort — e il protocollo li massimizza comunque entro il contesto;
- l'alternativa («esplora anche 65536, 32768, …» e scegli il compromesso) moltiplica la durata
  per ~5 e richiede una funzione di utilità contesto/velocità che nessuna misura locale può
  decidere al posto dell'utente: sarebbe una costante inventata travestita da ottimizzazione;
- la scelta resta onesta perché **dichiarata**: il record non pretende più di essere «la busta
  migliore in assoluto», ma «la busta più veloce confermata al contesto massimo fattibile» — che
  è ciò che il codice fa davvero.

Due estensioni facoltative post-Gate, nessuna delle quali tocca il percorso predefinito:

- `--target-ctx <valore della scala>`: l'utente esperto che preferisce velocità blocca la scala a
  un gradino (la macchina esistente fa il resto; ~10 righe);
- **suggerimento informativo** nel sommario finale, derivato dalla pendenza VRAM misurata: «a
  ctx 32768 entrerebbero sulla GPU ~N blocchi in più; se preferisci velocità al contesto,
  `calibrate --target-ctx 32768`». È una predizione di capienza (misurata), mai una promessa di
  tok/s; etichettata come tale.

## 10. Complessità e durata (la domanda «meno che lineare»)

Dove va il tempo, e che cosa si può comprimere:

- **Screening: è già sublineare.** La bisezione è `O(log₂ 41) ≈ 6` probe (7 osservati, tetto 12);
  una scansione lineare ne avrebbe usati fino a 41. Sotto il logaritmo si può scendere solo in
  media, con lo split interpolato della sezione 4 (tipicamente 4–5 probe): il floor teorico è 2
  probe *misurati* — confine fattibile e vicino non fattibile — perché il confine va dimostrato,
  non predetto. Qualunque schema con meno misure smetterebbe di essere una calibrazione.
- **Il costo dominante è l'avvio di processo** (caricamento modello, minuti), non la matematica.
  Per questo la conferma v3 tiene **4 avvii esatti come oggi** e spende il guadagno dove rende:
  4 sessioni benchmark invece di 2 (~+10 richieste ≈ pochi minuti) comprano il raddoppio
  dell'evidenza prestazionale e l'equità temporale — il miglior rapporto informazione/minuto
  dell'intero protocollo.
- **Niente parallelismo**: una sola GPU e la contesa di memoria renderebbero le misure
  reciprocamente contaminate; la serialità è un requisito di correttezza, non un'ingenuità.
- La stima di design era 30–45 minuti a modo e 1,5–2 ore per `all`. Il Gate Windows reale ha
  completato `all` in **27 minuti e 3 secondi**: coding 8,61 min, studio 7,99 min, vstudio 9,52 min.
  Lo split interpolato e i tempi di caricamento locali spiegano il divario; il dato non diventa una
  promessa su altro hardware. La CLI mostra progresso per fase con stima appresa online.
- Futuro possibile, da mini-spike: `coding` e `studio` differiscono solo per sampling e UI; se
  uno spike verifica che la busta di memoria del server è identica, `all` può condividere lo
  screening fra i due (−~6 probe) confermando comunque per modo. Non necessario ora.

## 11. Costanti e provenienza (aggiornamento D-039)

| Costante | Valore | Evidenza del Gate Windows v3 |
|---|---:|---|
| Riserva VRAM minima | 0,5 GiB | ha governato il confine; ha scartato vstudio 38 a 0,488 GiB; minimi accettati studio/vstudio 0,503/0,505 GiB |
| Tolleranza rilascio/deriva | 0,125 GiB | massimo rilascio 0,0176 GiB e massima deriva 0,0176 GiB |
| Round di conferma | 2 | ordine ABBA completo nei tre modi; benchmark su ogni avvio |
| Riserva RAM minima | 2,0 GiB | minimo accettato 8,602 GiB; soglia non stressata |
| Tetto probe screening per modo | 12 | usati 7/6/7 probe per coding/studio/vstudio |
| Scala contesti | 131072 → 8192 | `ctx=131072` fattibile e selezionato nei tre modi |
| Regola di selezione | unanimità dei round su mediane di sessione | osservate dominanza unanime, equivalenza per round discordi e finalista unico dopo scarto di riserva |

Nessuna costante per-macchina; ogni effetto passa da misure locali. La provenienza è registrata in
D-039/D-041–D-046. Il Gate locale sostiene i valori sulla macchina 32/8; D-047 rinvia la prova su
hardware eterogeneo a un follow-up non bloccante e vieta di descriverla come già eseguita.

## 12. Versionamento, decisioni, migrazione

- **Protocollo `calibration/v3`**, non una revisione silenziosa di v2: la riproducibilità del
  progetto è «versione dell'algoritmo + misure registrate», quindi ad algoritmo diverso id
  diverso. v2 non ha prodotto risultati accettati e non è pubblicato: il suo codice viene
  **sostituito** da v3 (nessun terzo protocollo vivo), `--protocol v1` resta il laboratorio
  storico, `docs/calibration-v2-design.md` riceve lo stato «superseded» con puntatore al design
  v3. Il run del 18 luglio resta evidenza conservata del perché v2 è stato respinto.
- **Schema `calibration-record/v2`** nella wheel; i record v1 diventano «invalidi, schema
  superato» con diagnostica azionabile (è la quarantena automatica del record attuale).
- **Decisioni registrate nella spec:** D-041 conferma accoppiata e dominanza per unanimità;
  D-042 riserva RAM universale; D-043 ciclo candidato→attivo con promozione atomica e
  `--no-activate`; D-044 telemetria GPU evidence-only; D-045 monotonia sui soli probe fattibili e
  split interpolato come solo ordinamento; D-046 identità eseguibile WDDM a scope di run.
- **Cosa non cambia**, ed è la maggior parte: zero input obbligatori, un contesto per confronto,
  bisezione misurata con tetto e degradazione onesta, riserva VRAM su ogni campione, rilascio con
  tolleranza, D-040/D-046 su WDDM, invalidazioni di run, `benchmark/v1` byte-identico, identità e
  headroom del riuso senza nearest-match, seed solo come ordinamento, conferma onesta della
  baseline su CPU (ora con benchmark su entrambi gli avvii), privacy e bundle, confini dei moduli
  e limiti di dimensione del codice.

## 13. Limiti onesti della proposta

1. Non riabilita il run v2 del 18 luglio: il nuovo run v3 è evidenza distinta e non reinterpreta
   retroattivamente misure raccolte con un altro protocollo.
2. Con 2 round, un burst che cade esattamente dentro una sessione può ancora produrre round
   discordi → equivalenza → margine: è il fallback voluto, prudente e dichiarato, non una scelta
   sbagliata; il Gate può alzare i round a 3 (unanimità su 3, sempre senza soglie) se l'evidenza
   lo chiederà — al costo di 2 avvii in più.
3. Un carico ambientale **costante** per tutto il run abbassa i tok/s assoluti di entrambi i
   finalisti: il confronto resta equo, i valori assoluti restano relativi all'ambiente (il record
   lo dichiara; la telemetria lo documenta).
4. Il Gate Windows ha osservato la riserva RAM con mmap, ma con almeno 8,602 GiB disponibili: la
   semantica vicino a 2 GiB e su un host con meno RAM resta non provata.
5. La telemetria è best-effort per costruzione: su driver che non la espongono il record ha
   `null` e la spiegazione ambientale resta parziale (mai bloccante).
6. I gap fra trial non sono campionati; D-046 impedisce l'assorbimento di contesti persistenti ma
   non registra eventi nati e terminati interamente fuori da una finestra di misura.

## 14. Implementazione e test completati nello Step 5A

Il codice è stato separato per responsabilità entro i limiti di 200 righe/file e 40/funzione:

| Area | Modifica |
|---|---|
| `_calibration_v2_search.py` → `_calibration_v3_search.py` | monotonia sui soli fattibili, selezione per unanimità e split interpolato sicuro |
| `_calibration_v2_confirm.py` → `_calibration_v3_confirm.py` | round ABBA con benchmark per avvio; deriva → flag di degradazione (~80 r. riorganizzate) |
| `_calibration_v2_runner.py` → `_calibration_v3_runner.py` | orchestrazione round, etichette selezione, evidence dir con rotazione (~30 r.) |
| `_calibration_ram.py` | riserva RAM nel validate del monitor (~10 r.) |
| `_hardware_monitoring.py` / `_calibration_vram.py` | telemetria opzionale e baseline eseguibili WDDM a scope di run |
| record: schema v2 + `_record_build` / `_record_checks` / `_record` | evidenza per avvio, ricostruzione round/unanimità, percorsi candidate/active/previous (~120 r.) |
| `_calibration_reuse.py`, `_cli_doctor.py` | headroom RAM + riserva; stati candidato/schema superato (~30 r.) |
| `_cli_calibration_v2.py` → `_cli_calibration_v3.py` | `--no-activate`/`--activate`, progresso per fase, sommario in linguaggio piano (~40 r.) |

La suite offline deterministica copre (fake trial runner, nessun hardware):

- ordine ABBA emesso esattamente (posizioni globali 1–4 registrate);
- dominanza: vittoria in entrambi i round → `dominance-unanimous-rounds`; round discordi o
  parità → equivalenza → margine → prudenza (fixture con i numeri del run del 18 luglio:
  la regola nuova sui dati registrati seleziona 37);
- deriva di baseline in conferma → nessuno scarto, etichetta `equivalent-after-baseline-drift`;
- riserva RAM violata in screening → probe non fattibile con motivo; in conferma → finalista
  scartato;
- regressione monotonia: picco OOM troncato inferiore a un picco fattibile prudente → nessuna
  degradazione spuria;
- split interpolato dentro staffa, fallback a punto medio e tetto rispettato;
- record v2: costruzione/carico/verifica, ricostruzione della selezione, rifiuto azionabile dei
  record v1, promozione atomica candidate→active→previous, `--no-activate` che non attiva;
- telemetria assente → `null` senza errori;
- respawn stesso file ammesso e contato, file nuovo/molteplicità extra/identità illeggibile e PID
  gestito riciclato rifiutati senza percorsi serializzati.

Verifica locale Windows: uv 0.11.28, CPython 3.12.13, Ruff, 314 test offline, `validate`, build e
wheel isolata verdi. La baseline D-046 ha risolto 20/20 identità WDDM reali senza serializzare
percorsi. Le matrici CI Ubuntu/Windows sono verdi sui commit D-046 `6f69d77` (run `29684539755`) e
lifecycle doctor `2d4cc22` (run `29684866498`). Il Gate reale è descritto in
`docs/calibration-gate-v3-windows.md`.

## 15. Percorso operativo

1. ~~approvare riserva RAM, ABBA, lifecycle, telemetria e split interpolato~~ — completato con
   D-041–D-046;
2. ~~implementare v3 e i test offline~~ — completato; i run sperimentali usano `--no-activate`;
3. ~~rieseguire il Calibration Gate sulla macchina di Tommaso~~ — completato il 19 luglio 2026 con
   esito locale accettato per i tre modi e candidati lasciati inattivi;
4. ~~implementare Step 5B con copertura empirica esplicitamente limitata alla macchina misurata e
   senza distribuire la sua busta come optimum remoto~~ — completato con policy/report v2, checksum
   e seed di solo ordine;
5. ripetere in futuro il Gate su almeno un caso materialmente diverso e aggiornare l'evidenza, senza
   rendere il follow-up bloccante per Step 5B.

La conclusione aggiornata resta onesta: `CALIBRATION-REJECTED` vale per il protocollo v2, mentre il
v3 spiega quale busta vince e perché sulla macchina misurata. Il risultato Windows è
`CALIBRATION-ACCEPTED` per i tre modi; D-047 permette di procedere con Step 5B senza chiamare
completa la copertura empirica.
