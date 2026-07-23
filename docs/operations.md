# Operazioni e diagnostica

## Punto di partenza

Quando qualcosa non funziona, eseguire nell'ordine:

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
qwen-launcher status
qwen-launcher engine status
```

Questi comandi separano rapidamente quattro categorie: installazione del tool, contenuti, macchina e
motore/processo. Conservare l'output completo e il percorso del log indicato dalla CLI. Prima di
condividere un log, rimuovere percorsi, nomi utente e altri dati privati.

Gli errori attesi non mostrano traceback. In generale:

- exit 1: problema operativo o validazione fallita;
- exit 2: comando o configurazione non validi;
- exit 130: interruzione da tastiera.

## Installazione del tool

### L'installer chiede una sorgente

È intenzionale: non esiste un default implicito. Per `0.1.1` usare wheel e digest della GitHub
Release come descritto in [Installazione](installation.md). La sorgente PyPI non è ancora disponibile.

### `uv` non è nel `PATH`

Gli script cercano prima `uv` nel `PATH`, poi:

- Ubuntu: `${UV_INSTALL_DIR:-$HOME/.local/bin}`;
- Windows: `%UV_INSTALL_DIR%` oppure `%USERPROFILE%\.local\bin`.

Aprire un nuovo terminale o aggiungere quella directory al `PATH`. Per il flusso riproducibile:

```bash
uv --version
```

deve riportare `0.11.28`.

### PowerShell blocca lo script

Eseguire il file locale scaricato dalla release in un processo separato:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 <opzioni>
```

Non cambiare la policy di sistema e non eseguire testo remoto con `Invoke-Expression`.

## Configurazione

### TOML invalido o chiave sconosciuta

Il file intero viene validato prima degli override ambiente. Correggere il file stampato da
`doctor`; le sole chiavi sono:

```text
model, model_path, llama_port, engine_path, open_browser
```

Stringhe come `open_browser = "false"` non sono booleani TOML. Usare `open_browser = false`.

### Una variabile ambiente sembra ignorare il file ma il comando fallisce comunque

È il comportamento previsto: un TOML invalido non viene nascosto da un override. Correggere prima il
file, poi verificare il valore risolto con `doctor`.

## Modello

### Modello predefinito non trovato

Il launcher non lo scarica. Verificare che lo snapshot della revisione appuntata esista nella cache
Hugging Face selezionata e che il filename sia esatto. `vstudio` richiede anche `mmproj-BF16.gguf`.

### Dimensione o digest errato

Il file è incompleto o diverso da quello fissato. Non rinominarlo per aggirare il controllo e non
modificare `engine.lock`. Ripristinare i byte corretti dalla fonte scelta dall'utente.

### Modello personalizzato rifiutato

Impostare sia un'identità `model` diversa sia `model_path`. Il modello predefinito non accetta un
percorso sostitutivo. I dati calibrati e il gate del modello predefinito non vengono attribuiti a un
GGUF diverso.

## Memoria

### RAM insufficiente al preflight

Il modello predefinito richiede 28 GiB totali e 22 GiB disponibili. Chiudere workload o usare una
macchina idonea. `--force` sui modi accetta soltanto il rischio di questo gate; non bypassa altri
controlli.

La calibrazione applica inoltre una riserva dinamica di 2 GiB durante ogni trial e non offre
`--force`.

### Il record aveva abbastanza RAM ma ora viene ignorato

Il riuso richiede il fabbisogno massimo misurato più 2 GiB disponibili. Liberare memoria e riprovare.
Nel branch corrente una variazione del totale RAM fino a 1 MiB è tollerata; differenze maggiori
indicano una macchina o una capacità diversa e invalidano il record.

## CUDA

### Il backend è CPU nonostante la GPU NVIDIA

`doctor` mostra il motivo. Controllare:

```bash
nvidia-smi
```

Il launcher ripiega su CPU quando il comando manca, supera 5 secondi, termina con errore o restituisce
CSV non interpretabile. Correggere driver e `PATH`; non impostare globalmente
`CUDA_VISIBLE_DEVICES` come workaround.

### Sono presenti più GPU

Il launcher identifica deterministicamente una GPU ma blocca l'avvio CUDA. Il caso multi-GPU non è
supportato dalla serie corrente; usare un host a GPU singola o rendere invisibili gli altri dispositivi
prima di avviare il launcher, assumendosi la gestione esterna dell'ambiente.

### La calibrazione viene invalidata da un processo GPU

Chiudere workload compute e applicazioni grafiche intensive. Su WDDM i contesti desktop iniziali sono
ammessi entro la popolazione catturata; un nuovo eseguibile, un'identità illeggibile o più istanze del
previsto invalidano comunque il run.

## Motore

### Motore assente

```bash
qwen-launcher engine install
qwen-launcher engine status
```

L'installazione gestita seleziona il backend rilevato. Se si vuole usare un eseguibile esterno,
`engine_path` deve puntare a `llama-server` della release esatta e con tutti i flag verificati.

### Motore incompatibile

Un eseguibile esplicito o trovato nel `PATH` ha precedenza su quello gestito. Se è incompatibile, il
launcher si ferma invece di ignorarlo. Correggere/rimuovere `engine_path` o il candidato nel `PATH`,
quindi rieseguire `engine status`.

### Ubuntu CUDA segnala prerequisiti mancanti

La release fissata non ha un prebuilt CUDA Linux verificato, quindi il launcher compila dal sorgente.
Installa manualmente gli strumenti elencati dal messaggio e ripeti il comando. Il launcher non usa
`sudo` né package manager.

### Download o checksum fallito

Controllare rete HTTPS, spazio e proxy. Non disabilitare TLS o checksum. File `.part` e staging non
vengono attivati; `current.json` precedente resta valido.

## Avvio e processo

### Porta occupata

Per `coding`, `studio` e `vstudio`, cambiare `llama_port` oppure fermare il proprietario. Se è un
servizio gestito:

```bash
qwen-launcher status
qwen-launcher stop
```

Non eliminare `services.json` per liberare la porta. Dalla `v0.1.1` i soli trial di calibrazione
possono scegliere automaticamente una porta temporanea; gli avvii ordinari restano severi sulla
porta configurata.

### Un secondo avvio è rifiutato

È ammesso un solo servizio gestito. Un `start.lock` con proprietario vivo blocca il secondo comando;
un lock sicuramente obsoleto viene rimosso e acquisito una sola volta. Usare `status` e `stop`.

### Il caricamento termina in timeout

Il timeout totale è 15 minuti. Controllare il log per OOM, modello errato, librerie mancanti o lentezza
estrema. Non allargare il timeout o cambiare endpoint senza cambiare e verificare il contratto.

### Health check incompatibile

READY richiede esattamente HTTP 200 con `{"status":"ok"}`. Un corpo diverso indica un motore o un
servizio incompatibile sulla porta. Controllare `engine_path`, `PATH`, `engine status` e il processo
che ascolta.

### Il browser non si apre

La UI può essere già pronta. Copiare l'URL stampato dalla CLI. Verificare `open_browser=true`; un
fallimento del browser non termina il server.

### Stato corrotto

`status` sposta automaticamente il file in `services.corrupt-<timestamp>.json` e ricostruisce uno
stato vuoto. Prima di avviare un nuovo server, verificare manualmente che non esista ancora un vecchio
`llama-server` non più gestibile dal file corrotto.

## Record e calibrazione

### Il record è assente o ignorato

`doctor` distingue candidato, assente, invalido, obsoleto, schema superato e headroom insufficiente.
Solo `<modo>.json` attivo è riusabile. Il rimedio normale è liberare memoria o rieseguire:

```bash
qwen-launcher calibrate --mode <modo>
```

Non correggere il JSON a mano e non copiare un record da un altro PC.

### Esiste un candidato valido

Promuoverlo senza nuove prove:

```bash
qwen-launcher calibrate --mode <modo> --activate
```

Controllare prima `doctor`. L'attivazione sostituisce atomicamente l'attivo e conserva un solo
`previous`.

### Tutti i probe falliscono

Leggere il riepilogo e l'evidenza privata dell'ultimo run. Le cause comuni sono RAM/VRAM insufficienti,
OOM, workload concorrenti, driver cambiato, risposta API incompatibile o rilascio memoria fuori
soglia. Un run senza busta valida non va completato o promosso manualmente.

### La calibrazione è stata interrotta

I processi vengono fermati; i log disponibili vengono preservati come ultima evidenza privata. Un
record candidato viene scritto solo dopo che l'intero risultato del modo è stato costruito e validato.

## Disinstallazione

Fermare prima i servizi. Se una radice gestita è un symlink, un file invece di una directory o non
coincide con l'anteprima corrente, il comando si ferma senza rimuovere nulla. Correggere manualmente
la struttura soltanto dopo aver verificato il percorso.

La cache Hugging Face e uv non vengono mai inclusi. Con l'installazione supportata `uv tool`, la
stessa conferma rimuove anche il comando appena il processo corrente termina. Se il resoconto indica
che l'installazione Python non è gestita da uv, occorre usare il gestore con cui è stata installata:
il launcher non indovina né modifica ambienti esterni.

## Segnalare un problema

Includere:

- versione e commit, se si usa un checkout;
- OS e backend mostrati da `doctor`;
- comando esatto ed exit code;
- output di `validate`, `doctor` ed `engine status` pertinente;
- estratto minimo del log, revisionato per dati privati;
- comportamento atteso e osservato.

Non allegare config, record locali, log completi, token, hostname, username o percorsi privati senza
redazione.

**Successivo:** [Sviluppo e contributi](development.md)
