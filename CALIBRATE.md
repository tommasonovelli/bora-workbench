# CALIBRATE.md — Analisi del primo run di calibrazione e piano correttivo proposto

> **Stato:** documento di analisi e proposta, **non normativo**. `IMPLEMENTATION_SPEC.md` resta
> l'unica fonte normativa; ogni modifica qui proposta a codice, schema, lock o specifica richiede
> l'approvazione esplicita di Tommaso (Registro delle decisioni e Calibration Gate). Questo
> documento non anticipa lo Step 5B: serve a correggere lo Step 5A e a preparare un Calibration
> Gate ripetibile.
> **Data:** 16 luglio 2026. **Evidenza di riferimento:** bundle locale
> `calibration-20260716t142541702536` (run reale `calibrate --mode coding` su Ubuntu 24.04,
> RTX 2060 SUPER 8 GiB, 32 GiB RAM) e spike `docs/spike-0/`.

## 1. Sintesi

Il primo run reale del calibratore ha funzionato meccanicamente (exit 0, bundle atomico valido)
ma non ha accettato alcun candidato e ha rivelato quattro problemi distinti:

| # | Problema | Tipo | Soluzione scelta |
|---|---|---|---|
| A | Il controllo di rilascio VRAM scarta candidati sani | bug core Step 5A | finestra di stabilizzazione + tolleranza esplicita (§3) |
| B | Percorsi privati assoluti nei campi testuali del report | bug privacy Step 5A | percorsi relativi + redazione dei documenti + scanner in `validate` (§4) |
| C | Il contratto motore non copre cache KV Q8 e `--no-mmap` | limite di `engine.lock` | mini-spike mirato su b10011, poi aggiornamento del lock (§5) |
| D | Ricerca di `n_cpu_moe` troppo grossolana (48 → 38 → 36) | limite di strategia | scala dichiarata asimmetrica informata dal mini-spike (§6) |

L'ordine di esecuzione proposto è in §8. Nessun punto è implementato da questo documento.

## 2. Evidenza misurata del run del 16 luglio

Parametri espliciti forniti: `ctx=131072` per tutti i candidati, `n_cpu_moe ∈ {48, 38, 36}`,
2 avvii stabili, riserva minima 0,25 GiB. Esito per candidato (valori dal report del bundle):

| Candidato | `n_cpu_moe` | Esito | Avvii riusciti | Picco VRAM | Min. libera | Baseline pre-run |
|---|---:|---|---:|---:|---:|---:|
| `safe` | 48 | scartato (rilascio VRAM) | 1 di 2 | 6,677 GiB | 1,323 GiB | 0,885 GiB |
| `historical` | 38 | scartato (OOM all'avvio) | 0 | 7,573 GiB | 0,427 GiB | 0,924 GiB |
| `aggressive` | 36 | scartato (OOM all'avvio) | 0 | 5,263 GiB | 2,737 GiB | 0,924 GiB |

Fatti rilevanti, tutti verificabili nei log redatti del bundle:

- **Il candidato 48 era funzionalmente valido.** Ha completato due avvii, il carico reale e
  l'intero `benchmark/v1`: warm-up 30,85 tok/s e cinque misure da 256 token
  (30,03 / 30,18 / 29,41 / 30,24 / 30,25 tok/s, mediana 30,18). Rispetto alla mediana dello spike
  a `ctx=8192`/`n_cpu_moe=48` (31,52 tok/s, `docs/spike-0/ubuntu-b10011/benchmarks/cuda-coding/`),
  il passaggio a `ctx=131072` costa circa il 4,3 %. Il candidato è stato scartato **soltanto** dal
  controllo post-stop descritto in §3, e lo schema `calibration-report/v1` azzera correttamente le
  misure di un candidato scartato: i numeri sopravvivono solo nei log.
- **38 e 36 falliscono all'avvio con il contratto attuale** (cache KV a precisione piena,
  `--mmap`): `historical` non ha allocato un buffer di calcolo da 168,02 MiB, `aggressive` uno da
  531,00 MiB (`ggml_backend_cuda_buffer_type_alloc_buffer ... cudaMalloc failed: out of memory`).
  Il picco registrato per 36 (5,263 GiB) è più basso del reale: il polling a 250 ms può non
  osservare l'istante del picco prima del crash. È un limite noto del campionamento, non un bug.
- **Il motore stesso suggerisce `--no-mmap`.** Nel log di caricamento di b10011 compare:
  `tensor overrides to CPU are used with mmap enabled - consider using --no-mmap for better
  performance`.
- **La baseline ambiente non è stabile al MiB.** Fra il primo e i successivi candidati la VRAM
  usata a riposo è passata da 0,885 a 0,924 GiB (≈ 40 MiB): sulla GPU che pilota anche il desktop,
  compositor e applicazioni grafiche muovono decine di MiB senza alcun carico compute.
- **Il successo storico di `ctx=131072`/`n_cpu_moe=38` non è direttamente comparabile.** Il
  comando manuale storico usava `-ctk q8_0 -ctv q8_0 --no-mmap` (e `-hf` invece del `-m`
  verificato): la cache KV quantizzata e la mappatura memoria cambiano in modo sostanziale le
  allocazioni. Quella evidenza motiva l'ipotesi di §5, ma non contiene digest, versioni esatte né
  misure riproducibili: non può entrare nel contratto senza una verifica sulla release appuntata.

## 3. Problema A — Il controllo di rilascio VRAM scarta candidati sani

### Cosa dice la specifica e cosa fa il codice

`IMPLEMENTATION_SPEC.md` §5.6 punto 6 scarta un candidato quando la memoria non è «tornata
**vicino** alla baseline dopo lo stop». L'implementazione è invece più severa in tre punti:

1. `src/qwen_launcher/_calibration_vram.py:80` preleva **un solo campione**, immediatamente dopo
   lo stop del processo;
2. `_calibration_vram.py:116-117` pretende `release_used <= baseline_used` con **tolleranza
   zero**: un solo MiB sopra la baseline scarta il candidato;
3. `src/qwen_launcher/_calibration_runner.py:74-75` pretende l'**uguaglianza esatta** della
   baseline fra gli avvii stabili dello stesso candidato; una deriva di 1 MiB solleva
   `CalibrationError` che — propagandosi fuori da `_discarded` — **aborta l'intera calibrazione**
   senza bundle, un esito ancora peggiore dello scarto.

Nel run reale il campione immediato dopo lo stop risultava circa 40 MiB sopra la baseline;
pochi istanti dopo la GPU era scesa **sotto** la baseline (0,529 GiB usati, osservato
dall'operatore). Non c'era alcuna perdita persistente: solo rilascio CUDA non ancora
stabilizzato e rumore del desktop, cioè esattamente il margine che «vicino alla baseline»
intendeva concedere.

### Opzioni considerate

| Opzione | Descrizione | Valutazione |
|---|---|---|
| A1 | Finestra di stabilizzazione post-stop, tolleranza zero: si ricampiona a 250 ms fino a X secondi e si accetta appena `usata ≤ baseline` | Avrebbe salvato il run del 16 luglio senza introdurre soglie. Resta però fragile alla crescita *legittima* della memoria grafica del desktop durante una prova lunga: se il compositor cresce di 30 MiB, la baseline non viene mai più raggiunta e il candidato sano viene scartato di nuovo. |
| A2 | Finestra di stabilizzazione + **tolleranza esplicita** fornita dall'operatore (poi fissata dalla policy al Gate) | Copre sia il rilascio lento sia il rumore ambientale. Nessuna soglia inventata: pre-Gate il valore è un parametro esplicito come riserva e avvii (stesso principio dello Step 5A); il Gate approva il valore definitivo da evidenza misurata. Con tolleranza 0 degenera in A1. |
| A3 | Abbandonare il confronto aggregato e verificare solo che nessun processo compute resti sulla GPU dopo lo stop | Il controllo sui PID compute esiste già (`_calibration_vram.py:107-109`). Da solo però non rileva memoria trattenuta dal driver o leak non attribuiti a processi vivi: perderebbe la difesa che il controllo aggregato fornisce. |
| A4 | Tolleranza fissa cablata nel codice (es. 64 MiB) | Vietata: sarebbe una soglia inventata dalla memoria dell'autore, contro §5.6 e il principio dello Step 5A. |

### Soluzione scelta: A2

1. **Finestra di stabilizzazione**: dopo lo stop, `VramMonitor.finish()` ricampiona a 250 ms per
   una finestra massima fissa e dichiarata (proposta: **10 secondi**, coerente con i timeout
   procedurali di stop di §5.9 — 10 s terminate + 5 s kill). Il controllo passa appena un
   campione soddisfa `usata ≤ baseline + tolleranza`; l'ultimo campione osservato entra
   nell'evidenza del candidato. La finestra è una costante procedurale del protocollo, come
   l'intervallo di polling da 250 ms: va ratificata con un emendamento a §5.6.
2. **Tolleranza esplicita**: la sintassi `--settings` su CUDA diventa
   `RUNS:MIN_FREE_VRAM_GIB:RELEASE_TOLERANCE_GIB` (o prompt interattivo equivalente); su CPU
   resta `RUNS`. Nessun default: come per la riserva, il valore è richiesto e `0` è ammesso.
   Al Calibration Gate Tommaso approva il valore definitivo dall'evidenza (il rumore osservato
   finora è ±40 MiB) e lo Step 5B lo registra nella policy con un campo dedicato, ad esempio
   `vram_release_tolerance_gib` accanto a `minimum_free_vram_gib`. L'estensione dello schema
   `calibration-policy/v1` avviene prima che esista qualunque policy pubblicata, quindi non rompe
   contenuti distribuiti; va comunque emendata la lista dei campi in §5.3.
3. **Stessa tolleranza per la deriva fra avvii**: `_combine_vram` confronta le baseline dei
   diversi avvii con la stessa tolleranza invece dell'uguaglianza esatta, e una deriva oltre
   soglia **scarta il candidato** con motivo esplicito invece di abortire l'intera calibrazione.
   L'aborto totale resta riservato ai casi già previsti (carico compute concorrente, driver
   cambiato, monitor guasto).
4. **Test**: rilascio lento entro finestra (valido), rilascio oltre finestra (scartato),
   rilascio entro tolleranza (valido), oltre tolleranza (scartato), deriva fra avvii entro/oltre
   soglia, tolleranza rifiutata su CPU, sintassi `--settings` vecchia e nuova. Tutto offline con
   il monitor fake esistente.

Nota onesta sul caso limite: con una tolleranza approvata T, un leak reale ≤ T diventerebbe
invisibile al singolo candidato. La difesa resta stratificata: il controllo PID compute continua a
rilevare processi sopravvissuti e la deriva cumulativa fra candidati successivi resta visibile nei
campi `vram_baseline_gib` del report.

## 4. Problema B — Percorsi privati nei campi testuali del report

### Evidenza

Nel report del bundle i due candidati OOM hanno `discard_reason` del tipo:

```text
OOM: llama-server exited during startup; inspect /home/<utente>/.local/share/qwen-launcher/
calibrations/.calibration-<id>.tmp-<esadecimale>/.runtime/coding/historical/start-1/logs/...
```

Il testo proviene dai messaggi operativi di `_process_health.py:68,79,83` e `process.py:88,195`,
che per contratto (§5.9) devono mostrare il percorso del log **all'utente su stderr**. Quel
contratto è corretto e non va toccato; l'errore è ricopiare il messaggio non redatto dentro un
file condivisibile. La redazione attuale copre soltanto i log copiati
(`_calibration_bundle.py:_sanitized_log`), non i tre documenti JSON, e `validate --path`
(`_calibration_validation.py`) controlla schema, manifest, digest e riferimenti ma nessun
contenuto testuale. Risultato: il bundle è formalmente valido ma viola §5.6 punto 8 e l'attività 8
dello Step 5A («rimuove dai file condivisibili hostname, username e percorsi assoluti»).

### Opzioni considerate

| Opzione | Descrizione | Valutazione |
|---|---|---|
| B1 | Riscrivere nei motivi di scarto i percorsi runtime nel percorso **relativo del log copiato** (es. `logs/coding/historical/run-1.log`) | Strutturale: il riferimento resta utile al revisore del bundle e sparisce l'informazione privata. La corrispondenza sorgente→`run-N.log` esiste già in `_copy_logs`. |
| B2 | Applicare la redazione `_private_values` a **tutti i campi stringa** dei tre documenti JSON prima della scrittura | Difesa in profondità: copre qualunque testo futuro (nuovi motivi di scarto, messaggi di libreria) senza dipendere dalla disciplina di chi genera il messaggio. |
| B3 | Estendere `validate_bundle` con uno **scanner privacy**: errore se un file condivisibile contiene i valori privati noti localmente (username, hostname, home, percorsi di modello/motore/staging) o pattern generici di percorso assoluto (`/home/`, `/Users/`, `C:\Users\`, radici drive) | Rende il cancello verificabile: «validate passa» torna a implicare «condivisibile». I pattern generici proteggono anche il revisore che valida un bundle altrui. |
| B4 | Cambiare i messaggi del process layer per non contenere mai percorsi | Rigettata: degraderebbe l'esperienza interattiva richiesta da §5.9 per risolvere un problema che appartiene al confine del bundle. |

### Soluzione scelta: B1 + B2 + B3 insieme

Non sono alternative ma strati: B1 rende il report *utile e pulito*, B2 protegge dai casi non
previsti, B3 impedisce la regressione. Test da aggiungere: motivo di scarto con percorso runtime
→ nel report compare il percorso relativo del log copiato; valore privato iniettato in un campo
testo → redatto; bundle con percorso assoluto in un campo → `validate --path` fallisce con
messaggio azionabile; pattern Windows e POSIX. Da correggere anche il caso del log di fallback
(`_copy_logs`): oggi scrive il `discard_reason` grezzo e lo redige solo alla copia; con B1+B2 il
testo nasce già pulito.

## 5. Problema C — Il contratto motore non copre cache KV Q8 e `--no-mmap`

### Perché non si può «semplicemente usare i flag del vecchio script»

- §5.7 e D-017: il builder emette **soltanto** flag presenti in `verified_flags` ed espande solo i
  template del `command_contract`; il test flag-lock fallisce per costruzione su ogni flag nuovo.
- §5.6 punto 3: i candidati di calibrazione variano **soltanto** `n_cpu_moe` (e il contesto
  dichiarato). La quantizzazione della cache non può essere un asse dei candidati, altrimenti i
  confronti non sarebbero più a parità di condizioni: è una proprietà fissa del contratto motore
  (`fixed_args`, che per §5.8 ospita esattamente «template/Jinja/MTP/cache/flash/mmap verificati»).
- Gerarchia delle fonti (§2): il ricordo di un comando manuale funzionante è un'assunzione
  dell'esecutore finché non è riverificato sulla release appuntata.

### Cosa sappiamo già (evidenza, non ipotesi)

- L'help verificato di b10011 (`docs/spike-0/ubuntu-b10011/{cpu,cuda}-help.txt`, righe 75-90)
  elenca `-ctk, --cache-type-k` e `-ctv, --cache-type-v` con `q8_0` fra i valori ammessi, e la
  coppia `--mmap, --no-mmap`. I flag sono quindi *appuntabili*: `help_contract` con
  `must_list_verified_flags=true` li coprirebbe su entrambi i backend.
- Il log del run reale contiene il suggerimento del motore a usare `--no-mmap` con gli esperti
  spostati su CPU (§2).
- Il comando storico dell'autore usava esattamente `-ctk q8_0 -ctv q8_0 --no-mmap` a
  `ctx=131072`/`n_cpu_moe=38` sulla stessa macchina, con l'avvertenza di comparabilità di §2.
- Meccanicamente, una cache K/V `q8_0` occupa circa la metà di una cache f16: a `ctx=131072` il
  risparmio è dell'ordine dei GiB, cioè proprio la scala dei buffer da 168-531 MiB che oggi
  mandano in OOM 38 e 36. È un'aspettativa qualitativa da confermare con misure, non un numero da
  contratto.

### Opzioni considerate

| Opzione | Descrizione | Valutazione |
|---|---|---|
| C1 | Status quo (cache f16, `--mmap`) | Rinuncia a VRAM preziosa su una classe hardware da 8 GiB; contraddice il suggerimento del motore stesso e l'evidenza storica. |
| C2 | Cache come asse dei candidati di calibrazione | Viola §5.6.3, moltiplica la matrice e rompe la comparabilità dei candidati. |
| C3 | **Mini-spike mirato su b10011, poi aggiornamento del lock** | Unica via conforme: la verifica avviene sulla release appuntata, l'aggiornamento segue `docs/engine-lock.md` e resta una PR dichiarativa separata. |
| C4 | Doppio contratto (con e senza Q8, scelto a runtime) | Complessità e ambiguità senza requisito dimostrato; i profili non trasportano flag arbitrari. |

### Soluzione scelta: C3, con questa procedura

**Mini-spike (manuale, eseguito da Tommaso, evidenza conservata come per lo Spike 0):**

1. Stessa release/commit b10011 già installata; stesso modello appuntato risolto con `-m`.
2. Tre configurazioni a confronto, a parità di tutto il resto del contratto attuale:
   (a) contratto attuale (f16 + `--mmap`); (b) `--cache-type-k q8_0 --cache-type-v q8_0` +
   `--mmap`; (c) `--cache-type-k q8_0 --cache-type-v q8_0` + `--no-mmap`.
3. Punti di misura minimi per configurazione: `ctx=131072` con `n_cpu_moe=48` e `n_cpu_moe=38`,
   modo `coding`; più uno smoke `studio`/`vstudio` (UI e vision con mmproj) sulla configurazione
   candidata; più il backend CPU per decidere l'ambito del cambio (vedi sotto).
4. Grandezze registrate: avvio riuscito/OOM, tempo di caricamento, RAM totale/disponibile prima e
   durante (`--no-mmap` sposta il modello da page cache a memoria anonima: su 32 GiB va misurato,
   non presunto), VRAM picco/minima libera, salute, MTP (`draft_n`/`draft_n_accepted`), risposta
   vision, cinque misure `benchmark/v1` e stabilità dello stop.
5. Criterio GO: la configurazione candidata non regredisce su salute, MTP, vision e stabilità, non
   viola il gate RAM di §5.5, e libera VRAM o migliora tok/s in modo misurato. Qualunque
   divergenza ferma l'adozione (§2: una contraddizione non si risolve silenziosamente).

**Aggiornamento del lock (solo dopo GO, PR dichiarativa separata dai fix core):**

- `verified_flags` += `--cache-type-k`, `--cache-type-v`, `--no-mmap` (forme lunghe, come
  preferito da §5.7; le forme corte `-ctk`/`-ctv` restano equivalenti ma il lock ne appunta una);
- `command_contract.fixed_args`: `--mmap` → `--no-mmap`, aggiunta di
  `--cache-type-k q8_0 --cache-type-v q8_0`;
- se il backend CPU mostrasse regressioni con la cache quantizzata, l'ambito si restringe
  spostando i flag cache in `backend_args.cuda` invece che in `fixed_args`, documentandolo;
- il test flag-lock esistente copre automaticamente i flag nuovi; si aggiornano i test del builder
  che asseriscono gli argomenti attesi e l'evidenza in `docs/` secondo `docs/engine-lock.md`
  (punti 6-9: matrice sui due OS prima di toccare il lock).

**Fuori ambito dichiarato:** i flag draft `-ctkd`/`-ctvd` (cache del modello draft MTP) esistono
nell'help ma non vengono toccati senza una necessità dimostrata dal mini-spike; nessun altro flag
viene aggiunto «per completezza» (§5.12). La perdita qualitativa della cache Q8 è plausibilmente
minima ma non è quantificata da questa proposta: se il Gate la vorrà misurare, va definito un
protocollo di qualità separato, non improvvisato dentro `benchmark/v1`.

## 6. Problema D — Strategia di ricerca di `n_cpu_moe` troppo grossolana

### Vincoli normativi (e perché sono sensati)

§5.6 punto 3: si parte dalla baseline più prudente, si varia solo `n_cpu_moe`, **niente ricerca
binaria, niente assunzione di monotonicità, niente candidati generati implicitamente**. Il run
reale mostra perché: 36 è fallito allocando 531 MiB dove 38 ne chiedeva 168 — le allocazioni
cambiano forma vicino al confine (frammentazione, buffer temporanei), quindi «40 fallisce»
non dimostra che 39 fallisca né che 41 riesca. Una bisezione convergerebbe con fiducia
ingiustificata su un confine che non è una funzione monotona pulita.

### Opzioni considerate

Costo per candidato con la procedura attuale: ogni candidato *avviabile* paga
`avvii_stabili × (caricamento modello + carico del modo)` più un `benchmark/v1` completo
(warm-up + 5×256 token) sull'ultimo avvio; un candidato OOM costa un solo caricamento fallito,
cioè poco. Il costo totale cresce quindi soprattutto col numero di candidati **validi** dichiarati.

| Opzione | Descrizione | Valutazione |
|---|---|---|
| S1 | Salti grossi (48 → 38 → 36, come il primo run) | Nessuna precisione: fra 48 e 38 restano dieci valori mai osservati; è ciò che ha motivato questa sezione. |
| S2 | Scala uniforme a passo 1 (48, 47, …, 36) | Massima precisione, conforme, ma paga il benchmark completo anche su una lunga coda di candidati prudenti tutti validi e tutti prevedibilmente più lenti del migliore. |
| S3 | **Scala dichiarata asimmetrica informata dal mini-spike**: passo 2 nella zona sicura, passo 1 attorno al confine indicato dalle misure del mini-spike | Stessa conformità di S2 (lista esplicita, ordinata, provata per intero), precisione ±1 dove serve, molti meno benchmark sprecati lontano dal confine. |
| S4 | Due fasi: screening dichiarato (1 avvio + carico + VRAM, senza benchmark) su scala fitta, poi avvii stabili + benchmark solo sui migliori K dichiarati | La più efficiente, ma cambia il protocollo: §5.6 punto 7 impone il benchmark a ogni candidato sopravvissuto e `calibration-report/v1` non ha un esito «sondato senza benchmark». Richiederebbe `calibration/v2` + `report/v2` + approvazione: non per questo Gate. |
| S5 | Bisezione adattiva sull'intervallo | Vietata da §5.6.3 e tecnicamente fragile per la non-monotonicità osservata. |

### Soluzione scelta: S3 ora, S4 registrata come evoluzione futura

Il «modo intelligente» conforme non è rendere adattiva l'esecuzione, ma **spendere bene due punti
di misura prima di dichiarare la lista**: il mini-spike di §5 misura comunque `48` e `38` con la
cache Q8, e quei due punti (picco VRAM e margine osservati) dicono dove infittire la scala. La
calibrazione resta un elenco esplicito, ordinato dal più prudente, provato per intero e
riprodotto identico da chiunque.

Esempio concreto per `coding` (da approvare al momento, **non** è una policy):

- se il mini-spike mostra `38` avviabile con margine sulla riserva:
  `48, 44, 42, 40, 39, 38, 37, 36` — passo 2 nella zona sicura, passo 1 attorno e sotto il
  confine storico, senza fermarsi al primo fallimento;
- se `38` resta OOM anche con Q8: `48, 46, 44, 43, 42, 41, 40, 39, 38` — infittita più in alto.

Regole di contorno proposte:

- **un solo `ctx` per run di calibrazione per modo** (oggi 131072): la regola di selezione
  massimizza la mediana tok/s e non pesa il contesto, quindi mischiare `ctx` diversi nella stessa
  lista farebbe vincere un contesto più piccolo appena marginalmente più veloce. Un eventuale
  ripiego di contesto (98304, 65536, …) è un run dichiarato separato, non un candidato in più;
- **liste per modo, non uniche**: `vstudio` carica anche il mmproj (≈ 0,9 GiB di artefatto) e ha
  un confine più prudente di `coding`; la policy per-modo dello schema lo consente già;
- l'ordine dichiarato resta dal più prudente al più aggressivo e **tutti** i candidati vengono
  provati anche dopo un fallimento intermedio, come oggi: è ciò che rende il report una mappa del
  confine invece di un'estrapolazione.

S4 (screening + benchmark selettivo) resta la strada giusta quando la calibrazione pubblica
diventerà un'operazione frequente su hardware altrui: va registrata come proposta per
`calibration/v2` nel Registro delle decisioni, non improvvisata ora.

## 7. Nota minore — esito «tutti scartati» ed exit code

L'exit 0 del run era corretto per §5.11: la procedura è riuscita e il bundle documenta
legittimamente anche solo scarti. L'equivoco era di presentazione: la CLI mostra i file ma non
dichiara l'esito. Proposta (dentro la PR core di §8): un riepilogo finale esplicito per modo —
candidato proposto oppure «nessun candidato valido: il bundle documenta solo scarti» — senza
cambiare gli exit code contrattuali.

## 8. Ordine di esecuzione proposto

1. **PR core (correzioni Step 5A):** §3 (finestra + tolleranza esplicita, deriva fra avvii come
   scarto), §4 (B1+B2+B3), §7 (riepilogo), con i test offline elencati; poi
   `uv sync --frozen`, lint, format, `pytest`, `validate`, build e verifica wheel.
   Richiede l'emendamento contestuale di `IMPLEMENTATION_SPEC.md` §5.6 (finestra e tolleranza) e
   della sintassi documentata in `docs/calibration.md`.
2. **Mini-spike cache Q8 / no-mmap su b10011** (§5, manuale di Tommaso), con evidenza conservata
   in `docs/` come per lo Spike 0. Decisione GO/NO-GO esplicita.
3. **PR dichiarativa `engine.lock`** (solo dopo GO): flag verificati, `fixed_args`, evidenza e
   `docs/engine-lock.md` aggiornati; mai nella stessa PR dei fix core.
4. **Ricalibrazione:** `calibrate --mode coding` con la scala di §6 e i parametri espliciti
   (riserva e tolleranza inclusi); poi `studio` e `vstudio` con le loro liste.
5. **Calibration Gate 0.1:** Tommaso approva o rifiuta riserva, tolleranza di rilascio, finestre,
   liste candidati, contesti e selezioni per OS/modo. Solo con `CALIBRATION-ACCEPTED` si apre lo
   Step 5B (policy, campo `vram_release_tolerance_gib`, profili iniziali).

Windows ripete i passi 2 e 4 per conto proprio: nessun risultato Linux viene riusato come
evidenza Windows (§ Step 5B, punto 3).

## 9. Decisioni riassuntive

| Problema | Scelta | Motivo in una riga |
|---|---|---|
| A — rilascio VRAM | finestra 10 s a 250 ms + tolleranza esplicita (0 ammesso), stessa soglia per la deriva fra avvii, deriva = scarto non aborto | rispetta «vicino alla baseline» senza soglie inventate e senza perdere la difesa anti-leak |
| B — privacy report | percorsi relativi nei motivi + redazione di tutti i campi stringa + scanner privacy in `validate --path` | tre strati: report utile, generazione robusta, cancello verificabile |
| C — cache Q8 / mmap | mini-spike su b10011, poi `fixed_args` con `--cache-type-k q8_0 --cache-type-v q8_0 --no-mmap` | i flag sono proprietà del contratto motore, adottabili solo con evidenza sulla release appuntata |
| D — strategia candidati | scala dichiarata asimmetrica (passo 1 al confine) informata dal mini-spike; un `ctx` per run; liste per modo; `calibration/v2` per lo screening futuro | precisione ±1 dove conta, piena conformità a §5.6.3, costo controllato |
