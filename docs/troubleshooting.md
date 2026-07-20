# Troubleshooting 0.1

Eseguire prima:

```bash
qwen-launcher --version
qwen-launcher validate
qwen-launcher doctor
qwen-launcher status
qwen-launcher engine status
```

Gli errori operativi attesi non mostrano traceback. Conservare il messaggio completo e il percorso
del log indicato dalla CLI; non pubblicare log senza revisarli per percorsi o dati privati.

## Installazione

### Nessuna sorgente selezionata

È intenzionale: gli installer non scelgono una versione o una sorgente implicita. Per la release
corrente usare `--pypi-version 0.1.0` oppure `-PypiVersion 0.1.0`. In alternativa trasferire wheel e
SHA-256 tramite canali verificabili e usare `--wheel ... --sha256 ...` / `-Wheel ... -Sha256 ...`,
oppure indicare un commit Git completo di 40 caratteri. Non sostituire un digest fidato con un valore
calcolato soltanto dopo un trasferimento non verificato.

### uv non viene trovato dopo l'installer

Gli script cercano prima uv nel `PATH`, poi la directory ufficiale `${UV_INSTALL_DIR:-$HOME/.local/bin}`
su Ubuntu o `%USERPROFILE%\.local\bin` su Windows. Aprire un nuovo terminale o aggiungere quella
directory al `PATH`. `uv --version` deve riportare `0.11.28` per il flusso congelato.

### PowerShell blocca lo script locale

Scaricare `install.ps1` dal tag `v0.1.0`. Se la policy locale consente l'esecuzione del solo processo,
avviare PowerShell con `-ExecutionPolicy Bypass -File .\install.ps1 ...`; non cambiare la policy di
sistema e non eseguire stringhe remote con `Invoke-Expression`.

## Configurazione invalida

`config.toml` viene validato interamente prima degli override ambiente. Correggere chiavi sconosciute,
booleani, porte o TOML malformato; il launcher non riscrive il file. Le sole chiavi 0.1 sono `model`,
`model_path`, `llama_port`, `engine_path` e `open_browser`.

## Modello non trovato o digest errato

Per il modello predefinito il launcher cerca soltanto lo snapshot della revisione appuntata e non
scarica né modifica la cache Hugging Face. Verificare che GGUF e mmproj siano completi. Non rinominare
un file diverso per farlo coincidere. Un modello diverso richiede `model_path` esplicito e resta non
calibrato rispetto ai dati del modello predefinito.

## RAM insufficiente

Il modello predefinito richiede almeno 28 GiB totali e 22 GiB disponibili prima del download.
Chiudere workload o usare una macchina idonea. `--force` accetta consapevolmente soltanto il rischio
del gate RAM; non bypassa lock, checksum, config, motore, porta o piattaforma.

## CUDA e GPU

- `nvidia-smi` assente, fallito o non interpretabile produce fallback CPU diagnosticato;
- più GPU CUDA bloccano la 0.1 perché la selezione fisica multi-GPU non è stata provata;
- chiudere workload GPU prima di `calibrate`;
- su WDDM nuovi contesti, identità illeggibili o molteplicità oltre baseline invalidano il run.

Non impostare globalmente `CUDA_VISIBLE_DEVICES`: il launcher lo applica soltanto al processo figlio.

## Motore assente o incompatibile

Eseguire:

```bash
qwen-launcher engine status
qwen-launcher engine install
```

Un eseguibile esplicito o nel `PATH` deve soddisfare versione e help del lock. Su Ubuntu CUDA i
prerequisiti di compilazione mancanti vengono elencati, ma il launcher non esegue `sudo` o package
manager. Vedere [`engine-lock.md`](engine-lock.md).

## Porta occupata o secondo avvio

`llama_port` deve essere libera. Usare `qwen-launcher status` per trovare un servizio gestito e
`qwen-launcher stop` per fermarlo identity-safe. Non cancellare manualmente `services.json` mentre il
processo è vivo. Un lock sicuramente obsoleto viene pulito dal launcher; un proprietario vivo blocca
il secondo avvio.

## Timeout, crash o salute incompatibile

La CLI mostra sempre il log del server. Un caricamento può impiegare fino a 15 minuti; morte del
processo, HTTP 200 con corpo incompatibile o 4xx terminano prima. Non allargare il timeout o cambiare
endpoint senza aggiornare lo spike e il lock.

## Record locale ignorato

`doctor` distingue record assente, candidato, superato, invalido, incompatibile e senza headroom.
Solo `<modo>.json` attivo può entrare nel piano. Modello, artefatto, motore, OS, backend, hardware,
driver e riserve devono coincidere. Il rimedio normale è liberare memoria o rieseguire `calibrate`;
non modificare il JSON a mano.

## Calibrazione invalidata o tutti i candidati scartati

Leggere il motivo per modo e chiudere workload concorrenti. Un esito procedurale con tutti i
candidati scartati non è un record valido. Non promuovere manualmente un candidato e non trasformare
un report condiviso in una busta locale.

## Disinstallazione

Fermare prima i servizi:

```bash
qwen-launcher stop
qwen-launcher uninstall
uv tool uninstall qwen-launcher
```

Revisionare l'anteprima. Se una directory gestita è un symlink o non può essere rimossa, il comando
si ferma con errore invece di seguire il collegamento. La cache Hugging Face è sempre esclusa.
