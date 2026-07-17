# CALIBRATE.md — Audit di portabilità della calibrazione

> **Stato:** analisi non normativa che corregge il precedente piano host-specific. La specifica
> normativa resta `IMPLEMENTATION_SPEC.md`. Nessun profilo o policy di produzione è autorizzato da
> questo documento e lo Step 5B resta chiuso.
> **Data:** 17 luglio 2026. **Evidenza conservata:** primo bundle reale
> `calibration-20260716t142541702536` e mini-spike Q8 sotto
> `docs/mini-spike-kv-q8-ubuntu/`.

## 1. Requisito di prodotto chiarito

Il prodotto non deve trovare una configurazione per la macchina del maintainer e applicarla a PC
che hanno soltanto la stessa quantità nominale di memoria. Deve invece:

1. eseguire la ricerca sulla macchina dell'utente;
2. misurare il rapporto prestazionale reale fra CPU, GPU, RAM, VRAM, driver e carico del modo;
3. scegliere localmente una busta stabile secondo un obiettivo dichiarato;
4. riutilizzare il risultato solo finché hardware e contratti rilevanti restano compatibili;
5. usare evidenza condivisa soltanto per governare o accelerare la ricerca, mai come prova che il
   candidato ottimo su un PC sia ottimo su un altro.

Una calibrazione locale è intenzionalmente personalizzata. L'overfitting indesiderato nasce quando
quel risultato viene promosso a decisione portabile senza una nuova misura locale.

## 2. Perché la correzione basata sulla larghezza delle classi non basta

La proposta di imporre finestre larghe almeno 1 GiB e un margine di 0,5 GiB dai bordi impedirebbe una
classe singleton, ma non dimostrerebbe portabilità. Due PC con 32 GiB RAM e 8 GiB VRAM possono avere:

- GPU di generazioni e bandwidth diverse;
- CPU con prestazioni per core e memoria molto diverse;
- rapporti CPU/GPU opposti, decisivi per `n_cpu_moe`;
- driver, processi grafici e VRAM libera differenti;
- RAM disponibile e pressione di memoria differenti;
- comportamento diverso fra Linux e Windows.

Perciò `[31, 33]` e `[7.5, 8.5]` possono descrivere capacità nominali, ma non autorizzano a chiamare
la busta misurata sulla RTX 2060 SUPER «calibrata» su ogni macchina 32/8. Anche CPU e nome GPU nel
solo campo di provenienza non risolvono questo limite.

Non vengono quindi introdotte soglie arbitrarie di larghezza o distanza dai bordi come surrogato
della generalizzazione. Le classi possono al massimo indicizzare seed o evidenza comparabile.

## 3. Audit dell'attuale `calibration/v1`

### 3.1 Parti valide

Restano validi e utili:

- processo fresco e stato isolato per ogni prova;
- carico reale per modo, incluso vision per `vstudio`;
- polling aggregato VRAM a 250 ms;
- rilascio VRAM entro 10 s con tolleranza esplicita;
- rilevamento di processi compute concorrenti;
- `benchmark/v1` con warm-up escluso e cinque misure;
- bundle atomico, redazione, manifest e scanner privacy;
- fallback non ottimizzato quando manca una calibrazione locale valida.

Le correzioni del primo run su rilascio VRAM e privacy rimangono necessarie e corrette.

### 3.2 Limiti che impediscono l'uso pubblico come calibratore generale

1. **Dominio dei candidati esterno.** L'utente deve conoscere e fornire manualmente
   `n_cpu_moe`; il programma sceglie solo fra quei valori e non dimostra di avere cercato il dominio
   rilevante.
2. **Lista derivata da un solo host.** La scala `48, 44, 42, 40, 39, 38, 37` nasce dal confine di una
   RTX 2060 SUPER 8 GiB. Può essere utile per ripetere quel caso, non è una policy portabile.
3. **Contesto e prestazioni erano separati solo nella documentazione.** Il codice accettava contesti
   diversi nello stesso run; massimizzare tok/s avrebbe favorito normalmente il contesto minore.
4. **Nessun asse CPU verificato.** A contesto fisso i candidati CPU sono identici; dichiarare una
   scelta «ottima» sarebbe fittizio finché uno spike non approva parametri CPU realmente variabili.
5. **RAM non monitorata durante i trial.** Il report registra la disponibilità iniziale, ma non il
   minimo osservato durante caricamento e benchmark.
6. **Selezione fragile rispetto al rumore.** La mediana maggiore vince anche per differenze minime;
   non esiste ancora evidenza per fissare una fascia di equivalenza o un criterio statistico.
7. **Nessuna attivazione locale.** Il bundle è una bozza di contribuzione: l'utente sostiene il costo
   della calibrazione ma gli avvii successivi non usano ancora il risultato.
8. **Matching per capacità precedente.** Prima di questa correzione `profile/v1` applicava una busta
   condivisa tramite OS, backend e finestre RAM/VRAM senza misurarla sul PC corrente.

Questi sono limiti architetturali. Non si correggono cambiando soltanto i bordi delle classi.

## 4. Interpretazione corretta dell'evidenza esistente

Il run del 16 luglio conserva valore diagnostico sulla macchina originale:

| Candidato | `ctx` | `n_cpu_moe` | Evidenza utile |
|---|---:|---:|---|
| safe | 131072 | 48 | carico e benchmark completati; falso scarto per rilascio VRAM corretto dopo il run |
| historical | 131072 | 38 | OOM col contratto allora attivo |
| aggressive | 131072 | 36 | OOM col contratto allora attivo |

Il mini-spike Ubuntu conserva inoltre questi esiti sul contratto motore:

- cache K/V Q8 con mmap: `GO` Ubuntu;
- Q8 con `--no-mmap`: `NO-GO` Ubuntu;
- smoke Windows ancora necessario prima di modificare il lock globale.

Questi fatti possono correggere il contratto Q8 e riprodurre il PC originale. Non approvano una
policy universale, una classe portabile o una lista di ricerca completa.

## 5. Architettura corretta

### 5.1 Policy portabile

La policy distribuita deve descrivere il **metodo di ricerca**, non il vincitore di Tommaso. Per ogni
modello, motore, backend e modo deve fissare soltanto valori verificati e revisionati:

- target di contesto, tenuto costante durante un confronto;
- dominio legale degli assi realmente supportati dal lock;
- strategia deterministica di screening e verifica;
- riserve RAM/VRAM e controlli di stabilità;
- numero di avvii e misure;
- criterio di selezione e regole di invalidazione.

Il dominio di `n_cpu_moe` non viene dedotto dai risultati 8 GiB: limite e semantica devono essere
verificati sul modello e sulla release appuntati. Nessun nuovo flag CPU entra senza spike e lock.

### 5.2 Calibrazione locale autorevole

Ogni macchina esegue il protocollo. Il risultato locale contiene almeno modello e digest artefatto,
release/commit e digest del contratto motore, modo, backend, identità hardware locale stabile,
busta scelta, risorse minime osservate e benchmark. Il record:

- è scritto atomicamente in una directory gestita;
- è usato prima dei seed condivisi;
- non viene condiviso automaticamente;
- viene ignorato dopo cambi incompatibili di modello, motore, backend o hardware;
- non viene usato quando RAM/VRAM libera corrente non copre il fabbisogno misurato più la riserva.

La revisione privacy è necessaria per condividere un bundle, non per usare localmente un risultato
che ha già superato i controlli automatici.

### 5.3 Ruolo dei dati condivisi

Report e profili distribuiti sono evidenza di riferimento e possono:

- proporre seed da provare per primi;
- mostrare risultati osservati su componenti dichiarati;
- ridurre il costo della ricerca senza eliminarne la verifica locale.

Non possono:

- diventare automaticamente la busta finale su un altro PC;
- promettere gli stessi tok/s;
- usare nearest-match;
- escludere dalla calibrazione hardware supportato solo perché fuori dalla classe 32/8.

### 5.4 Ricerca e costo

`calibration/v1` esegue il benchmark completo su ogni candidato valido. Una policy sufficientemente
ampia sarebbe lenta. Il percorso pubblico richiede quindi un protocollo successivo, versionato, con:

1. screening locale economico dell'intero dominio approvato;
2. scelta deterministica di finalisti senza assumere che memoria o prestazioni siano perfettamente
   monotone;
3. avvii stabili e `benchmark/v1` completo sui finalisti;
4. selezione soltanto fra candidati allo stesso contesto;
5. ripetizione separata per ciascun modo.

Numero di finalisti, misure di screening e trattamento del rumore devono arrivare da uno spike; non
vengono inventati in questo documento.

## 6. Correzioni core applicabili senza inventare evidenza

L'audit autorizza subito soltanto invarianti dimostrabili:

- un run confronta un solo contesto;
- `n_cpu_moe` è unico e ordinato dal più prudente al più aggressivo;
- su CPU non si finge una ricerca con candidati identici;
- `validate` ricostruisce il vincitore di ogni report accettato;
- `validate` ricontrolla riserva, rilascio e coerenza picco/minimo libero VRAM;
- un report accettato richiede policy e classe nominate e la misura originale deve appartenervi;
- il profilo deve copiare esattamente classe approvata e OS misurato;
- un profilo v1 condiviso resta un seed e non viene più applicato direttamente al `LaunchPlan`.

Questi controlli impediscono report incoerenti, ma **non rendono portabile una busta**. La parte
mancante richiede il nuovo protocollo locale descritto sopra.

## 7. Gate corretto

Il precedente invito a ripetere subito la lista 8 GiB viene ritirato come percorso verso una policy
pubblica. L'ordine corretto è:

1. completare lo smoke Windows Q8+mmap, che resta evidenza indipendente sul lock;
2. verificare sul modello/engine appuntati il dominio legale degli assi di calibrazione;
3. definire con evidenza screening, finalisti, monitoraggio RAM e criterio robusto;
4. implementare e testare il protocollo versionato per la ricerca locale;
5. implementare record locale, compatibilità, headroom e invalidazione;
6. eseguire il gate sulla macchina di Tommaso come primo caso reale, senza attribuirgli portabilità;
7. provare almeno casi hardware eterogenei o fixture che ne riproducano confini differenti;
8. aprire lo Step 5B solo dopo almeno un risultato locale accettato e dopo aver dimostrato che un PC
   fuori dalla classe originaria può eseguire la propria ricerca.

Fino ad allora la baseline verificata resta il comportamento sicuro. Non viene pubblicata la classe
`[31, 33]` / `[7.5, 8.5]` come soluzione al problema di generalizzazione.
