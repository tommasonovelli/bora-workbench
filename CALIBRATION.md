# Audit della calibrazione hardware

Data dell'audit: 2026-07-22.

Questo documento è il resoconto tecnico non normativo richiesto per la revisione della calibrazione.
Descrive fonti, misure, limiti e decisioni; non sostituisce `IMPLEMENTATION_SPEC.md`, i lock o la
[guida utente corrente](docs/calibration.md). Non contiene ragionamenti privati o transcript di
modelli: conserva soltanto conclusioni verificabili.

## Esito sintetico

`calibration/v3` è conservativo e adatto a trovare una busta valida nel proprio dominio, ma il suo
nome “best fit” va interpretato con precisione:

- massimizza il contesto fra `131072`, `65536`, `32768`, `16384`, `8192`;
- su CUDA trova il confine di memoria di `n_cpu_moe` e confronta soltanto quel valore e l'adiacente
  più prudente;
- misura localmente RAM, VRAM e carico ambientale, quindi non deve introdurre compromessi hardcoded
  per Windows o Ubuntu;
- non dimostra l'ottimo globale di throughput fra tutti i valori `n_cpu_moe`;
- non calibra thread, batch, parametri MTP, cache draft, sampling o quantizzazione;
- su CPU conferma per default `ctx=8192`, pur accettando un target esperto esplicito.

La modifica implementata in questo audit migliora osservabilità e interpretazione senza cambiare il
metodo v3 o invalidare record esistenti. Un ampliamento degli assi richiede un protocollo successivo,
nuovo schema/evidenza e gate reali multipiattaforma.

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
- dominio `n_cpu_moe=[0,41]`, riserva RAM 2 GiB, riserva VRAM 0,5 GiB e tolleranza
  di rilascio 0,125 GiB;
- stato della Calibration Gate `GATE-PARTIAL`.

## Analisi del contesto

La model card Qwen dichiara 262.144 token nativi e consiglia almeno 128K quando possibile. Il tetto
v3 di 131.072 soddisfa quella raccomandazione quando è fattibile, ma usa soltanto metà del contesto
nativo dichiarato. Non è corretto estendere automaticamente il dominio usando una pagina corrente:
la compatibilità locale dipende anche da release motore, cache, MTP, quantizzazione e memoria.

La scala `128K → 64K` può saltare un best fit a 96K. Il target 98.304 già autorizzato consente di
misurare il gap senza cambiare v3. La CLI ora lo suggerisce, con `--no-activate`, soltanto quando una
ricerca automatica CUDA termina a 65.536; non ne promette la fattibilità. Inserire 96K nella scala o
provare 262K automaticamente cambierebbe budget, ordine ed evidenza del protocollo e va versionato.

Su CPU, 8.192 è la baseline automatica e non un massimo tecnico: i target esperti approvati restano
validi. Una vera ricerca automatica del massimo contesto CPU è lavoro per un protocollo successivo.

## RAM, VRAM e ambiente operativo

Il fit non può derivare dalla sola somma nominale RAM+VRAM. Mmap, pagine residenti, KV cache, pesi
MoE, MTP e processi desktop producono pressioni diverse e in parte sovrapposte. v3 prende la decisione
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
lavoro e il traffico lato CPU/RAM. Il throughput non è assunto monotono. v3 usa una ricerca adattiva
per trovare il primo valore fattibile, poi conferma soltanto `boundary` e `boundary+1` in ordine ABBA.

Questo è efficiente per trovare il confine di memoria, non per dimostrare il massimo throughput sul
dominio `[0,41]`. Un valore lontano dal confine potrebbe essere più veloce per effetti di CPU,
banda, MTP o scheduling. Un protocollo successivo dovrebbe separare:

1. ricerca di fattibilità e contesto;
2. campionamento prestazionale controllato del dominio fattibile;
3. conferma accoppiata dei finalisti prodotti dal secondo stadio.

Il disegno deve fissare prima budget, stop rule, gestione del rumore e ricostruzione del record; non
va aggiunto uno sweep opportunistico a v3.

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

Gli eventi di progresso sono interni e non persistiti; non richiedono un nuovo schema. Timestamp,
ordine ABBA, benchmark e record restano invariati.

## Calibrazione empirica locale

È stato eseguito un run reale `coding`, CUDA, automatico e `--no-activate` in radici isolate. Nessun
record o candidato utente è stato modificato; record, log e transcript temporanei sono stati
eliminati dopo l'estrazione degli aggregati. Questa è una verifica locale del commit, non nuova
evidenza pubblica e non modifica `GATE-PARTIAL`.

Host osservato:

- Ubuntu 24.04, Intel Core i5-10400F (6 core/12 thread);
- 31,26 GiB RAM;
- NVIDIA RTX 2060 SUPER 8 GiB, driver 595.71.05;
- modello e motore appuntati sopra.

Esito del run (4 min 47 s, exit code 0):

| Campo | Osservazione |
|---|---:|
| probe screening | 7 |
| massimo contesto v3 | 131.072, fattibile |
| confine | `n_cpu_moe=37` fattibile; 36 non rispetta la riserva VRAM |
| finalisti | 37 e 38, entrambi validi |
| vincitore round 1 / round 2 | 38 / 37 |
| regola finale | equivalente, preferire VRAM libera |
| selezione | `n_cpu_moe=38` |
| mediana tok/s, 37 | 34,745 |
| mediana tok/s, 38 | 34,671 |
| VRAM libera minima, 37 / 38 | 0,783 / 1,248 GiB |
| RAM disponibile minima selezionata | 25,788 GiB |
| deriva baseline VRAM | 0,0166 GiB, sotto 0,125 GiB |

La differenza di mediana fra i finalisti è circa 0,21% e ciascuno vince un round: non c'è evidenza di
una vittoria throughput unanime. Scegliere 38 sacrifica una differenza marginale e rumorosa, aumenta
la VRAM libera minima di circa 0,465 GiB e lascia circa 0,748 GiB oltre la riserva obbligatoria. Il
risultato è quindi ragionevole e prudente secondo v3. Il contesto 128K raggiunge il tetto automatico
e la raccomandazione minima della model card, quindi non serve il probe esperto 96K su questo host.

Il run non dimostra però un ottimo globale: copre un solo modo, un solo host Ubuntu, un solo run e i
soli finalisti adiacenti, con thread/MTP/batch/quantizzazione fissati. Non autorizza modifica dei seed
pubblici né attivazione automatica dei candidati locali esistenti.

## Priorità consigliate per un protocollo successivo

1. Definire e versionare un protocollo v4 prima di cambiare scala o finalisti.
2. Valutare 96K nella scala e 262K come asse sperimentale, con budget e requisiti memoria espliciti.
3. Separare ricerca del confine e ricerca throughput nel dominio `n_cpu_moe` fattibile.
4. Aggiungere una vera ricerca del contesto CPU, mantenendo un percorso breve per la baseline.
5. Eseguire spike monovariati su thread, batch e MTP; solo dopo provare le interazioni principali.
6. Trattare sampling/thinking e quantizzazione come audit di contratto e qualità separati.
7. Ripetere Ubuntu e Windows con stesso hardware quando possibile, poi su hardware materialmente
   diverso; pubblicare soltanto report redatti e manifestati.

Qualunque v4 deve restare deterministico, limitato nel budget, interrompibile, ricostruibile dal
record e validato offline con fake prima dei gate reali.

## Consultazione Claude Fable

Claude Fable è stato consultato due volte con `--model fable --effort max` e accesso in sola lettura.
La prima revisione ha confermato che v3 cerca soprattutto il confine di memoria, che hardcodare
compromessi per OS sarebbe scorretto e che 96K/CPU richiedono un nuovo protocollo. La seconda ha
revisionato il disegno UX e ha corretto tre formulazioni recepite qui: 8K è baseline CPU, non tetto;
l'ETA screening è un massimo; `min_p` comporta una cascata di contratto/record e non è una modifica
innocua. Nessun output del consulente è trattato come evidenza empirica e nessun file è stato da lui
modificato.

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
