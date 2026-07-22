# Audit della calibrazione hardware

Data dell'audit: 2026-07-22.

Questo documento è il resoconto tecnico non normativo richiesto per la revisione della calibrazione.
Descrive fonti, misure, limiti e decisioni; non sostituisce `IMPLEMENTATION_SPEC.md`, i lock o la
[guida utente corrente](docs/calibration.md). Non contiene ragionamenti privati o transcript di
modelli: conserva soltanto conclusioni verificabili.

## Esito sintetico

`calibration/v4` deriva da v3 ed è conservativo nel proprio dominio, ma il suo nome “best fit” va
interpretato con precisione:

- massimizza il contesto fra `131072`, `65536`, `32768`, `16384`, `8192`;
- su CUDA trova il confine di memoria di `n_cpu_moe` e confronta soltanto quel valore e l'adiacente
  più prudente;
- misura localmente RAM, VRAM e carico ambientale, quindi non deve introdurre compromessi hardcoded
  per Windows o Ubuntu;
- non dimostra l'ottimo globale di throughput fra tutti i valori `n_cpu_moe`;
- non calibra thread, batch, parametri MTP, cache draft, sampling o quantizzazione;
- su CPU conferma per default `ctx=8192`, pur accettando un target esperto esplicito.

La prima modifica dell'audit ha migliorato osservabilità e interpretazione. D-053 implementa ora un
cambio stretto e versionato: v4 conserva scala, ricerca e ABBA di v3, riduce la riserva VRAM a 0,3
GiB (circa 307 MiB nelle unità binarie del progetto) e produce `calibration-record/v3`. I record v2
storici restano leggibili e mantengono 0,5 GiB al
riuso. Gli altri ampliamenti elencati qui restano proposte, non funzionalità implementate.

## Gerarchia delle fonti

Le decisioni rispettano l'ordine del repository:

1. `engine.lock`, contenuti appuntati e relativi digest;
2. evidenza misurata sotto `evidence/`;
3. schema e test;
4. `IMPLEMENTATION_SPEC.md`;
5. documentazione primaria della versione esatta;
6. documentazione upstream corrente, utile solo per formulare nuovi spike.

Per questo audit restano invariati:

- modello `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M`, revisione
  `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d` e SHA-256 appuntato;
- `llama.cpp b10011`, commit `bf2c86ddc0685f580595954056c2e77ebabfab4f`;
- MTP draft massimo 2, parallelismo 1, flash attention, mmap e cache K/V Q8 su CUDA;
- dominio `n_cpu_moe=[0,41]`, riserva RAM 2 GiB e tolleranza di rilascio 0,125 GiB;
- riserva VRAM v4 0,3 GiB; i record prodotti da `calibration/v3` conservano 0,5 GiB;
- stato della Calibration Gate `GATE-PARTIAL`.

## Analisi del contesto

La model card Qwen dichiara 262.144 token nativi e consiglia almeno 128K quando possibile. Il tetto
v4 di 131.072 soddisfa quella raccomandazione quando è fattibile, ma usa soltanto metà del contesto
nativo dichiarato. Non è corretto estendere automaticamente il dominio usando una pagina corrente:
la compatibilità locale dipende anche da release motore, cache, MTP, quantizzazione e memoria.

La scala `128K → 64K` può saltare un best fit a 96K. Il target 98.304 già autorizzato consente di
misurare il gap senza cambiare la scala v4. La CLI lo suggerisce, con `--no-activate`, soltanto quando una
ricerca automatica CUDA termina a 65.536; non ne promette la fattibilità. Inserire 96K nella scala o
provare 262K automaticamente cambierebbe budget, ordine ed evidenza del protocollo e va versionato.

Su CPU, 8.192 è la baseline automatica e non un massimo tecnico: i target esperti approvati restano
validi. Una vera ricerca automatica del massimo contesto CPU è lavoro per un protocollo successivo.

## RAM, VRAM e ambiente operativo

Il fit non può derivare dalla sola somma nominale RAM+VRAM. Mmap, pagine residenti, KV cache, pesi
MoE, MTP e processi desktop producono pressioni diverse e in parte sovrapposte. v4 prende la decisione
sulle misure locali durante ogni processo fresco e rivalida l'headroom al riuso del record.

Le differenze ambientali sono già trattate nel punto corretto:

- fuori da WDDM, un contesto compute estraneo invalida il run;
- su WDDM, la popolazione desktop iniziale è identificata e sorvegliata per l'intero run;
- RAM e VRAM sono campionate ogni 250 ms su entrambe le piattaforme;
- il carico corrente può rendere una busta infeasible senza diventare una costante per quell'OS.

Non va quindi aggiunto un “margine Windows” o “margine Ubuntu” fisso. Servono invece ripetizioni
controllate sugli stessi hardware/driver e su hardware materialmente diverso, perché l'evidenza
pubblica attuale copre un solo host Windows.

## Analisi di `n_cpu_moe`

Valori più bassi lasciano più pesi MoE sulla GPU; valori più alti risparmiano VRAM ma aumentano il
lavoro e il traffico lato CPU/RAM. Il throughput non è assunto monotono. v4 usa una ricerca adattiva
per trovare il primo valore fattibile, poi conferma soltanto `boundary` e `boundary+1` in ordine ABBA.

Questo è efficiente per trovare il confine di memoria, non per dimostrare il massimo throughput sul
dominio `[0,41]`. Un valore lontano dal confine potrebbe essere più veloce per effetti di CPU,
banda, MTP o scheduling. Un protocollo successivo dovrebbe separare:

1. ricerca di fattibilità e contesto;
2. campionamento prestazionale controllato del dominio fattibile;
3. conferma accoppiata dei finalisti prodotti dal secondo stadio.

Il disegno deve fissare prima budget, stop rule, gestione del rumore e ricostruzione del record; non
va aggiunto uno sweep opportunistico a v4.

## Assi disponibili ma non calibrati

L'help del binario esatto b10011 espone assi reali che il contratto corrente lascia ai default o non
usa:

- thread di generazione e batch (`--threads`, `--threads-batch`);
- batch logico e fisico (default osservati 2048 e 512);
- thread, cache K/V e `n_cpu_moe` del modello draft;
- numero massimo di token draft MTP;
- altri tipi di speculative decoding.

Unsloth indica 2 draft token come buon punto iniziale, ma dichiara esplicitamente che l'ottimo è
hardware-dependent; i suoi risultati correnti sui MoE mostrano inoltre guadagni inferiori ai modelli
densi e sconsigliano in generale più di 2 per il calo di acceptance. Il valore 2 già appuntato resta
quindi ragionevole, ma non è dimostrato ottimo sull'intera matrice supportata. Un futuro spike deve
misurare almeno MTP off/1/2/3, acceptance, prefill, decode, RAM/VRAM e interazione con `n_cpu_moe`,
senza estrapolare percentuali upstream al launcher.

La guida modello corrente propone quantizzazioni diverse, fra cui `UD-Q4_K_XL` e NVFP4 su hardware
Blackwell. Non prevalgono su `UD-Q4_K_M` e sui digest pubblicati: cambiare quantizzazione significa
cambiare identità, requisiti, qualità e gate, non ottimizzare silenziosamente la calibrazione 0.1.

## Divergenza sampling separata dalla calibrazione

La model card esatta raccomanda `min_p=0.0` per i profili documentati. Il command contract del
launcher espande solo temperatura, `top_p` e `top_k`; l'help b10011 riporta quindi il proprio default
`min_p=0.05`. È una divergenza nota, ma non prova che il launcher debba cambiare valore.

Adottare `min_p=0.0` richiederebbe modifica coordinata di contenuto modo e command contract. Il digest
del contratto partecipa alla validazione, quindi tutti i record locali diventerebbero incompatibili e
andrebbero ricalibrati. Inoltre `benchmark/v1`, con 256 token e `ignore_eos`, misura throughput e non
qualità o regressioni di sampling. La decisione appartiene a uno spike separato con valutazione di
qualità, thinking/non-thinking, loop, tool calling e matrice dei tre modi; non a questo commit.

## Miglioramento UX implementato

Senza alterare prove, schema o selezione, il comando ora:

- emette un evento prima e dopo ogni trial, così le attese non sembrano blocchi;
- usa una barra Rich con spinner, fase, conteggio, elapsed e tempo residuo su TTY;
- conserva una riga per trial completato quando l'output è rediretto;
- separa le durate per fase: screening dopo due campioni, conferma dopo uno e poi mediana;
- mostra `≤12` nello screening e proietta la durata fino al cap senza chiamarla limite garantito;
- chiude il live display su errori e `Ctrl-C`, mantenendo un riepilogo di fase;
- spiega la regola di selezione e mostra i minimi RAM/VRAM del finalista;
- rende visibili in `calibrate --help` gli extra gestiti dal parser specializzato.

Gli eventi di progresso sono interni e non persistiti; non richiedono un nuovo schema. D-053 è un
cambio separato: timestamp, ordine ABBA e benchmark restano invariati, mentre protocollo e record
passano rispettivamente a v4 e v3.

## Calibrazione empirica locale

Tutti i run reali sono stati eseguiti su `coding`, CUDA, automatici e `--no-activate` in radici
isolate. Nessun record o candidato utente è stato modificato; dopo l'estrazione degli aggregati le
radici temporanee sono eliminate. Queste sono verifiche locali, non evidenza pubblica portabile.

Host osservato:

- Ubuntu 24.04, Intel Core i5-10400F (6 core/12 thread);
- 31,26 GiB RAM;
- NVIDIA RTX 2060 SUPER 8 GiB, driver 595.71.05;
- modello e motore appuntati sopra.

### Baseline v3 a 0,5 GiB

Il run originario (4 min 47 s, exit 0) ha selezionato `ctx=131072, n_cpu_moe=38`: 37 e 38 hanno vinto
un round ciascuno e il tie-break ha preferito 1,248 GiB di VRAM libera minima contro 0,783 GiB. Il
valore 36 non rispettava la riserva. Le mediane 37/38 erano 34,745/34,671 tok/s.

### Gate v4 a 0,3 GiB

Sono stati conservati anche gli esiti negativi:

| Run | Esito | Osservazione |
|---|---:|---|
| 1, 5 min 20 s | exit 1 | confine 36; 36 viola 0,3 GiB in conferma e 37 non rilascia entro tolleranza; nessun finalista valido |
| 2, 4 min 50 s | exit 0 | confine 37; 36 scende a 0,051 GiB ed è scartato; 37 e 38 sono validi |

Aggregati del retry valido:

| Campo | Osservazione |
|---|---:|
| probe screening | 7 |
| massimo contesto v4 | 131.072, fattibile |
| finalisti | 37 e 38 |
| vincitore round 1 / round 2 | 37 / 37 |
| selezione | `n_cpu_moe=37`, dominanza unanime |
| mediane round, 37 | 34,907 / 34,258 tok/s |
| mediane round, 38 | 34,647 / 34,067 tok/s |
| mediana aggregata selezionata | 34,763 tok/s |
| VRAM libera minima, 37 / 38 | 0,509 / 0,962 GiB |
| RAM disponibile minima selezionata | 25,577 GiB |
| deriva baseline VRAM | 0,0117 GiB |

Il risultato non autorizza `n_cpu_moe=36`: il benchmark completo lo porta quasi a esaurimento VRAM.
Inoltre non dimostra il beneficio della soglia 0,3, perché il finalista selezionato resta sopra 0,5
GiB e un run su due è fallito. La 0.1.1 resta quindi bloccata fino a un Gate reale Windows v4 e a una
successiva decisione umana `RELEASE`; test offline o il Gate Windows v3 non sono sostituti.

## Priorità consigliate per un protocollo successivo

1. D-053 ha versionato come v4 il solo cambio di riserva; scala e finalisti restano invariati.
2. Valutare 96K nella scala e 262K come asse sperimentale, con budget e requisiti memoria espliciti.
3. Separare ricerca del confine e ricerca throughput nel dominio `n_cpu_moe` fattibile.
4. Aggiungere una vera ricerca del contesto CPU, mantenendo un percorso breve per la baseline.
5. Eseguire spike monovariati su thread, batch e MTP; solo dopo provare le interazioni principali.
6. Trattare sampling/thinking e quantizzazione come audit di contratto e qualità separati.
7. Completare prima il Gate Windows v4, poi ripetere su hardware materialmente diverso; pubblicare
   soltanto report redatti e manifestati.

Qualunque metodo successivo deve restare deterministico, limitato nel budget, interrompibile,
ricostruibile dal record e validato offline con fake prima dei gate reali.

## Consultazione Claude Fable

Claude Fable è stato consultato tre volte con `--model fable --effort max` e accesso in sola lettura.
Le prime due revisioni hanno coperto confine di memoria, UX, baseline CPU e cascata di `min_p`. La
terza ha revisionato D-053 e i due run v4: ha identificato che il primo codice applicava 0,3 GiB anche
al riuso dei record v2 storici. La migrazione è stata corretta affinché ogni record mantenga la
propria riserva, con test dedicati. Ha inoltre confermato che assenza del Gate Windows e incoerenza
fra codice/spec/docs bloccano una release stabile; queste conclusioni sono recepite qui. Nessun
output del consulente è evidenza empirica e nessun file è stato modificato dal consulente.

## Fonti primarie consultate

Fonti versionate del repository:

- [`engine.lock`](src/qwen_launcher/resources/engine.lock);
- [`evidence/engine/spike-0.md`](evidence/engine/spike-0.md) e help b10011
  [Ubuntu CUDA](evidence/engine/spike-0/ubuntu-b10011/cuda-help.txt) /
  [Windows CUDA](evidence/engine/spike-0/windows-b10011/cuda-help.txt);
- [spike KV Q8 Ubuntu](evidence/engine/kv-q8-ubuntu.md) e
  [Windows](evidence/engine/kv-q8-windows.md);
- [protocollo pubblico v3](evidence/calibration/windows-11-rtx-2060-super-v3/protocol.md) e
  [Calibration Gate](evidence/calibration/windows-11-rtx-2060-super-v3/gate.md).

Fonti upstream primarie, subordinate ai lock:

- [Qwen/Qwen3.6-35B-A3B model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B);
- [Unsloth GGUF alla revisione appuntata](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/blob/5bc3e238d916f48a861bac2f8a1990a0e9b7e98d/README.md);
- [guida Unsloth Qwen3.6](https://unsloth.ai/docs/models/qwen3.6) e
  [guida MTP](https://unsloth.ai/docs/models/mtp);
- [release llama.cpp b10011](https://github.com/ggml-org/llama.cpp/releases/tag/b10011);
- [PR llama.cpp MTP #22673](https://github.com/ggml-org/llama.cpp/pull/22673);
- [PR llama.cpp `n_cpu_moe` #15077](https://github.com/ggml-org/llama.cpp/pull/15077).

Le pagine upstream correnti sono state consultate il 2026-07-22 e possono cambiare; flag e default
del binario b10011 sono stati ricontrollati anche sull'eseguibile locale verificato.
