# Progettazione di `calibration/v2` — ricerca locale adattiva

> **Stato:** progettazione approvata e implementata nello Step 5A, punti 4–5 del percorso correttivo
> di `CALIBRATE.md`, sezione 7. La specifica normativa resta `IMPLEMENTATION_SPEC.md` (decisioni
> D-038 e D-039). Lo Step 5B resta chiuso fino a un esito reale `CALIBRATION-ACCEPTED`.
> **Data:** 17 luglio 2026. **Evidenza citata:** `docs/mini-spike-kv-q8-ubuntu/`,
> `docs/mini-spike-kv-q8-windows/`, primo bundle reale `calibration-20260716t142541702536`.

## 1. Requisito

Il requisito chiarito dal maintainer il 17 luglio 2026 (ridisegno adattivo local-first, approvato
esplicitamente) è: un utente che non conosce `llama-server` esegue `qwen-launcher calibrate` e il
launcher trova la migliore busta stabile **per quella macchina**, con zero input obbligatori e zero
valori ereditati dalla memoria di chiunque. Nessuna lista di candidati curata a mano, nessuna
esclusione del tipo «salta 36 per scegliere 37», nessuna soglia per-macchina nel codice. La
sicurezza deriva dalla regola della riserva misurata e dal versionamento dell'algoritmo; la
riproducibilità deriva da versione dell'algoritmo più misure registrate, non da liste dichiarate.

## 2. Evidenza che fonda la progettazione

### 2.1 Dominio legale di `n_cpu_moe` (misurato, non ricordato)

I metadati GGUF del modello appuntato (`general.architecture=qwen35moe`) dichiarano
`block_count=41`, `expert_count=256`, `expert_used_count=8`, `context_length=262144`. I probe
Windows (`ncmoe-domain-48/49/41/40`, ctx 8192, Q8+mmap) misurano VRAM di picco e minima libera
identiche per 48, 49 e 41, e maggiore uso VRAM soltanto sotto 41:

- il dominio legale dell'asse CUDA è `[0, 41]`;
- ogni valore sopra 41 è un alias di 41 («tutti i layer MoE su CPU»): la baseline storica
  `n_cpu_moe=48` è quindi l'alias prudente del massimo reale;
- della scala storica `48, 44, 42, 40, 39, 38, 37` i primi tre valori erano alias della stessa
  configurazione: la lista provava 5 configurazioni reali, non 7. Questo conferma il limite n. 1-2
  dell'audit (`CALIBRATE.md`, sezione 3.2) e il valore della verifica del dominio dai metadati.

Il limite inferiore fattibile resta hardware-dipendente (0 non entra in 8 GiB per questo modello) e
viene trovato dalla ricerca, non dichiarato.

### 2.2 Dispersione di `benchmark/v1` (misurata su due host)

Dispersione relativa `(max − min) / mediana` delle cinque misure valide:

| Host | Configurazione | Dispersione |
|---|---|---:|
| Ubuntu (quieto) | Q8+mmap coding 48 / 38 | 0,14% / 0,22% |
| Ubuntu (quieto) | contratto attuale coding 48 / 38 | 0,32% / 1,71% |
| Ubuntu (quieto) | studio 38 / vstudio 38 | 0,54% / 2,41% |
| Ubuntu (quieto) | CPU coding | 6,96% |
| Ubuntu (quieto) | Q8 no-mmap 48 / 38 | 15,6% / 7,9% |
| Windows (desktop attivo) | contratto attuale coding 48 | 11,7% |
| Windows (desktop attivo) | Q8+mmap coding 48 / 38 | 11,5% / 9,6% |
| Windows (desktop attivo) | studio 38 / vstudio 48 / vstudio 38 | 18,0% / 10,5% / 18,8% |
| Windows (desktop attivo) | CPU coding | 6,3% |

I due host sono lo stesso hardware fisico in dual boot: la differenza di dispersione (0,14–2,4%
contro 6,3–18,8%) è interamente ambientale, non di componenti.

La dispersione varia di due ordini di grandezza fra host quieto e host con carico ambientale. Una
fascia fissa di equivalenza (per esempio «2%») giudicherebbe male uno dei due casi: il criterio di
selezione deve quindi derivare il rumore dalle misure locali stesse, senza costanti inventate.

### 2.3 Monotonia della VRAM sull'asse `n_cpu_moe`

Su entrambi gli host la VRAM usata cresce al diminuire di `n_cpu_moe` (più esperti su GPU); la
relazione è fisicamente fondata e misurata su 41→40 e 48→38. Lo screening può quindi cercare il
confine di fattibilità per bisezione, ma ogni probe verifica con la misura e un esito non monotono
degrada onestamente a scansione lineare attorno al confine osservato.

## 3. Pipeline `calibration/v2` (per modo, contesto fisso per confronto)

1. **Predizione.** Dai metadati GGUF e dall'hardware rilevato: dominio legale degli assi
   (`[0, block_count]` per `n_cpu_moe` su CUDA), punto di partenza più prudente
   (`n_cpu_moe = block_count`), ordine di discesa. La predizione ordina la ricerca; non esclude mai
   valori del dominio.
2. **Screening adattivo senza benchmark.** Processo fresco per probe, attesa READY, carico reale del
   modo (testo; anche vision per `vstudio`), campionamento VRAM **e RAM** a 250 ms per tutti i
   backend. Un probe è fattibile se salute, risposta e riserva misurata sono rispettate; OOM, morte,
   salute incompatibile o riserva violata lo rendono non fattibile. La discesa cerca il confine di
   fattibilità (bisezione con verifica misurata, sezione 2.3) entro il tetto di probe.
3. **Conferma dei finalisti.** Il confine fattibile e il vicino più prudente diventano finalisti.
   Ogni finalista supera gli avvii stabili richiesti (deriva fra baseline entro la tolleranza) e un
   `benchmark/v1` completo (un warm-up escluso, cinque misure esatte da 256 token), più rilascio
   VRAM entro finestra e tolleranza dopo lo stop.
4. **Selezione robusta al rumore, senza soglie inventate.** Il candidato A domina B soltanto se la
   mediana di A supera il massimo delle cinque misure di B. Senza dominanza i candidati sono
   equivalenti: si preferisce la maggiore VRAM libera minima osservata, poi il più prudente.
   Su un host quieto (dispersione sotto l'1%) la dominanza emerge; su un host rumoroso la regola
   ripiega in sicurezza sul margine di memoria. `validate` ricostruisce la scelta.
5. **Record locale.** Scrittura atomica nella directory dati gestita di: modello e digest
   dell'artefatto, release/commit e digest del contratto motore, modo, backend, OS, identità
   hardware stabile (nome GPU, VRAM totale, driver, CPU, RAM totale, numero GPU), busta scelta
   (`ctx`, `n_cpu_moe`), minimi osservati (VRAM libera, RAM disponibile), riepilogo benchmark,
   versione dell'algoritmo. Il record è usato immediatamente dai lanci successivi.
6. **Riuso e invalidazione.** Un record è calibrato per l'avvio solo se ogni campo d'identità
   coincide con lo stato corrente e se RAM/VRAM libere attuali coprono il fabbisogno misurato più la
   riserva. Ogni divergenza (modello, motore, contratto, driver, hardware, headroom) ignora il
   record con diagnostica azionabile e ripiega sulla baseline; non esiste nearest-match.
7. **Seed condivisi.** Report e profili distribuiti possono soltanto riordinare la sequenza dei
   probe della stessa ricerca completa. Mai restringere il dominio, mai diventare busta finale.
8. **Backend CPU.** Senza un asse di tuning verificato dal lock, il v2 esegue onestamente la sola
   conferma della baseline auto-configurata dal motore (avvii stabili più benchmark) e la registra
   come «baseline confermata», non come optimum prodotto dal launcher.
9. **Scala di contesto.** Target per modo dalla scala approvata `131072 → 65536 → 32768 → 16384 →
   8192`: si scende soltanto se il candidato più prudente non è fattibile al contesto corrente. I
   confronti restano a parità di contesto; il record registra il contesto raggiunto. Il modello
   supporta 262144: l'estensione della scala oltre 131072 è una decisione di prodotto futura.
10. **Invalidazione ambientale.** Come in `calibration/v1`: carichi compute concorrenti, cambio
    driver o monitor inaffidabile invalidano il run; la deriva oltre tolleranza scarta il candidato.

## 4. Costanti di design e loro provenienza

| Costante | Valore | Provenienza e stato |
|---|---:|---|
| Riserva VRAM minima | 0,5 GiB | ridisegno approvato dal maintainer (17 luglio 2026); sostituisce la riserva 0,25 del primo run: l'evidenza `vstudio` 38 (minimo libero 0,148 GiB) e la variabilità ambientale Windows (~0,1 GiB fra baseline) mostrano che 0,25 era insufficiente; da validare al Gate |
| Tolleranza rilascio/deriva | 0,125 GiB | già operativa nelle correzioni v1 e usata nei due mini-spike; confermata dalla misura |
| Avvii stabili per finalista | 2 | ridisegno approvato dal maintainer; da validare al Gate |
| Tetto probe di screening per modo | 12 | ridisegno approvato dal maintainer; con dominio `[0, 41]` la bisezione converge in ≤ 6 probe più le conferme; da validare al Gate |
| Scala contesti | 131072 → 8192 | ridisegno approvato dal maintainer; coerente con l'evidenza 131072 dei mini-spike |

Nessuna di queste costanti è una soglia per-macchina: valgono identiche su ogni host e il loro
effetto passa sempre dalla misura locale. Il Gate le valida o le corregge con evidenza; il codice
non ne introduce altre.

## 5. Contratti implementati nello Step 5A

- `calibration/v2` è il protocollo predefinito senza input tecnici obbligatori; `--protocol v1`
  conserva il laboratorio storico senza alterarne retroattivamente i contratti;
- `calibration-record/v1` è uno schema versionato incluso nella wheel; i record privati vivono nella
  directory dati, sono scritti atomicamente e rivalidano selezione ed evidenza a ogni caricamento;
- RAM disponibile è monitorata durante caricamento, workload e benchmark su tutti i backend;
- riuso, headroom, invalidazione e diagnostica per modo sono integrati nei lanci e in `doctor`;
- seed condivisi possono soltanto riordinare probe della stessa ricerca completa;
- test offline deterministici coprono screening, tetto probe, degradazione, dominanza/equivalenza,
  monitor, record, invalidazione e headroom.

Il passo successivo è il Calibration Gate sulla macchina del maintainer come primo caso locale, più
almeno un caso materialmente diverso, come richiesto da `CALIBRATE.md`, sezione 7. Solo un esito
`CALIBRATION-ACCEPTED` apre lo Step 5B.
