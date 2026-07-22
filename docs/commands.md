# Comandi

La forma generale è:

```text
qwen-launcher [--version] <comando> [opzioni]
```

`--help` è disponibile sul gruppo principale e su ogni comando. Typer espone inoltre
`--install-completion` e `--show-completion` per la shell corrente.

## Riepilogo

| Comando | Scopo | Modifica dati locali? |
|---|---|---:|
| `--version` | mostra la versione installata | no |
| `validate` | valida risorse o un bundle locale | no |
| `doctor` | descrive configurazione, hardware, motore e record | no |
| `engine status` | ispeziona il motore gestito | no |
| `engine install` | installa e attiva il motore del lock | sì |
| `coding` | avvia l'API testuale | stato e log |
| `studio` | avvia la UI testuale integrata | stato e log |
| `vstudio` | avvia UI e vision | stato e log |
| `status` | mostra servizi vivi e ripulisce stato obsoleto | se necessario |
| `stop` | ferma servizi gestiti verificati | sì |
| `calibrate` | misura la macchina e gestisce record locali | sì |
| `uninstall` | elimina le radici gestite dopo conferma | sì |

## `validate`

```bash
qwen-launcher validate
qwen-launcher validate --path <directory-bundle>
```

Senza `--path` valida le risorse installate:

- JSON Schema Draft 2020-12;
- modi, policy e report;
- riferimenti e SHA-256 fra policy ed evidenza;
- semantica del lock motore e copertura dei flag;
- vincoli incrociati che uno schema non può esprimere.

Con `--path` valida un bundle condivisibile prodotto dal laboratorio `calibration/v1`, inclusi
manifest, riferimenti relativi e scansione privacy. Errori indicano file, percorso del campo e
motivo. Soli warning terminano con 0; almeno un errore termina con 1.

## `doctor`

```bash
qwen-launcher doctor
```

Mostra versione, configurazione risolta, OS, CPU, RAM, backend, GPU/VRAM, numero di seed condivisi,
motore gestito, quattro directory pubbliche e validazione dei contenuti. Per ogni modo valuta anche
lo stato del record locale:

- attivo e valido;
- candidato in attesa di attivazione;
- assente;
- incompatibile o obsoleto;
- schema superato;
- headroom corrente insufficiente.

Il comando non crea directory e non corregge automaticamente alcun problema. Una configurazione
invalida termina con 2; un errore hardware o di contenuto con 1; warning diagnostici con 0.

## `engine status`

```bash
qwen-launcher engine status
```

Mostra manifest attivo, release, backend, eseguibile e compatibilità con `engine.lock`. Un motore
assente è uno stato informativo e termina con 0; un'installazione presente ma incompatibile termina
con 1.

## `engine install`

```bash
qwen-launcher engine install
qwen-launcher engine install --force
```

Rileva CPU/CUDA, seleziona l'insieme esatto di asset nel lock, scarica via HTTPS, verifica SHA-256,
estrae in staging, verifica l'eseguibile e attiva una nuova directory immutabile. Un target già
attivo e compatibile è un no-op. `--force` reinstalla comunque lo stesso target; non disabilita TLS,
checksum, confinamento o probe di compatibilità.

Il comando può usare la rete e, su Ubuntu CUDA, eseguire CMake e compilazione. Non installa
prerequisiti di sistema e non eleva i privilegi.

## Modi di esecuzione

```bash
qwen-launcher coding [--force]
qwen-launcher studio [--force]
qwen-launcher vstudio [--force]
```

Tutti e tre seguono lo stesso flusso: configurazione → hardware → gate RAM → contenuti → modello →
piano → motore → porta → processo → health check → foreground.

| Modo | UI | Vision | Sampling `(temp, top_p, top_k)` |
|---|---:|---:|---|
| `coding` | no | no | `(0.6, 0.95, 20)` |
| `studio` | sì | no | `(0.7, 0.8, 20)` |
| `vstudio` | sì | sì | `(0.7, 0.8, 20)` |

`--force` salta esclusivamente le soglie di 28 GiB totali e 22 GiB disponibili del modello
predefinito. Non salta configurazione, piattaforma, multi-GPU, motore, modello, checksum, porta o
health check.

Quando READY, la CLI mostra:

- backend e modo;
- record locale oppure baseline non ottimizzata;
- API `http://127.0.0.1:<porta>/v1`;
- per `studio`/`vstudio`, UI `http://127.0.0.1:<porta>/`;
- percorso del log.

Il contratto espone anche `/health`, `/v1/models`, `/v1/chat/completions` e `/metrics`. Il servizio
ascolta solo su `127.0.0.1`. `studio` e `vstudio` aprono il browser soltanto dopo READY e se
`open_browser=true`.

Con `coding` in esecuzione, una richiesta minima da un altro terminale POSIX è:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  --header 'Content-Type: application/json' \
  --data '{"messages":[{"role":"user","content":"Scrivi una funzione Python somma."}],"max_tokens":128,"stream":false}'
```

Sostituire `8080` se `llama_port` è diverso. È possibile usare qualunque client compatibile con
l'endpoint OpenAI chat completions locale; non è richiesta una chiave dal server gestito corrente.

Il comando rimane collegato al processo. `Ctrl-C` termina il server, rimuove lo stato e restituisce
130. Un'uscita naturale non zero restituisce 1 e indica il log.

## `status`

```bash
qwen-launcher status
```

Mostra servizio, PID, modo, backend, porta e log. Prima verifica ogni voce tramite `pid +
create_time`; voci morte o PID riutilizzati vengono rimosse con warning. Uno stato JSON malformato è
messo in quarantena come `services.corrupt-<timestamp>.json`. Nessun servizio è un successo con exit
code 0.

## `stop`

```bash
qwen-launcher stop
```

Ferma soltanto processi la cui identità coincide con lo stato. Attende fino a 10 secondi dopo
`terminate`, poi usa `kill` e attende fino a 5 secondi. È idempotente: nessun servizio restituisce 0.
Non cancellare manualmente `services.json` mentre il processo è vivo.

## `calibrate`: protocollo corrente v3

```bash
qwen-launcher calibrate --mode <coding|studio|vstudio|all>
```

`--protocol v3` è il default. Il comando mostra un preflight e chiede conferma prima dei processi.
Per default scrive un candidato per ogni modo completato e lo attiva atomicamente.

Opzioni v3:

```bash
qwen-launcher calibrate --mode all --no-activate
qwen-launcher calibrate --mode coding --activate
qwen-launcher calibrate --mode coding --target-ctx 98304
```

| Opzione | Effetto |
|---|---|
| `--no-activate` | conserva i nuovi record come candidati senza cambiare quelli attivi |
| `--activate` | promuove candidati già validi, senza nuovi trial |
| `--target-ctx N` | usa un solo contesto esperto approvato |

I target ammessi sono `131072`, `98304`, `65536`, `32768`, `16384` e `8192`. `98304` è solo
esplicito e non appartiene alla scala automatica. `--activate` non può essere combinato con
`--target-ctx`; `--activate` e `--no-activate` sono mutuamente esclusivi.

Le tre opzioni sono gestite dal parser specializzato del comando. `calibrate --help` le elenca
nell'epilogo insieme agli extra v1, mentre la tabella generata da Typer contiene soltanto le opzioni
comuni; la sintassi sopra è quella effettivamente supportata.

Su un terminale interattivo il run v3 mostra una barra viva con fase, trial, tempo trascorso e stima
adattiva; l'output rediretto resta line-oriented. Lo screening mostra `≤12` e una proiezione della
durata fino a quel cap, non un limite o una promessa. Il riepilogo finale include la motivazione
della selezione e i minimi RAM/VRAM osservati.

La calibrazione non effettua upload, non modifica `config.toml` e non installa modello o motore. I
trial usano la porta configurata se libera; nel branch corrente ripiegano su una porta loopback
assegnata dal sistema quando è occupata. Questo fallback non vale per i tre avvii normali.

Dettagli dell'algoritmo e dei record: [Calibrazione](calibration.md).

## `calibrate`: laboratorio v1

Il protocollo storico resta eseguibile solo come laboratorio esplicito e produce un bundle bozza,
non un record attivo:

```bash
qwen-launcher calibrate \
  --mode coding \
  --protocol v1 \
  --candidate safe:8192:41 \
  --candidate mixed:8192:30 \
  --settings 2:0.5:0.125
```

Su CUDA ogni candidato usa `ID:CTX:N_CPU_MOE` e le impostazioni usano
`RUNS:MIN_FREE_VRAM_GIB:RELEASE_TOLERANCE_GIB`. Su CPU il candidato usa `ID:CTX` e `--settings`
contiene solo `RUNS`. `--candidate` è ripetibile. Se candidati o impostazioni mancano, la CLI li
chiede interattivamente; non assegna default impliciti.

Le opzioni v3 non sono valide con `--protocol v1`. Candidati o `--settings` non sono validi con v3.

## `uninstall`

```bash
qwen-launcher uninstall
```

Rifiuta di procedere se esiste un servizio gestito vivo. Mostra configurazione, dati, cache e stato,
indicando quali radici esistono, quindi richiede conferma. Un annullamento normale non elimina nulla
e termina con 0; `Ctrl-C` termina con 130. Il comando non rimuove né il tool Python né la cache
Hugging Face.

## Exit code

| Codice | Significato |
|---:|---|
| `0` | successo, stato vuoto o soli warning |
| `1` | errore operativo atteso o validazione fallita |
| `2` | input CLI o configurazione invalida |
| `130` | interruzione da tastiera |

Gli errori operativi attesi sono scritti su stderr senza traceback. Un traceback indica invece un
bug inatteso e va segnalato con il comando eseguito, l'output e un log revisionato per dati privati.

**Successivo:** [Configurazione e dati locali](configuration.md)
