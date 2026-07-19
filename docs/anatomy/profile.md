# Anatomia di un profilo `profile/v1`

`profile/v1` è un contratto **storico** nato prima dell'audit di portabilità D-034. La 0.1 conserva
schema, loader e fixture per validare evidenza precedente, ma non distribuisce profili di produzione
e non usa una busta di un altro PC come calibrazione locale.

## Cosa descrive il contratto storico

Un profilo v1 collega:

- modello e release motore esatti;
- report `calibration/v1` e SHA-256 dei suoi byte;
- backend, OS opzionale e intervalli nominali RAM/VRAM;
- uno o più modi con `ctx`, `n_cpu_moe` CUDA ed eventuale riepilogo tok/s;
- macchina e protocollo sui quali la misura era stata eseguita.

Le finestre sono inclusive, non sovrapposte nello stesso scope e possono riconoscere classi nominali.
Questa coerenza strutturale non prova che componenti diversi abbiano lo stesso optimum.

## Perché non produce un piano 0.1

RAM e VRAM uguali non implicano CPU, GPU, driver, pressione memoria o rapporto CPU/GPU uguali. Per
questo D-034–D-037 stabiliscono che:

- nessun nearest-match o intervallo “più vicino” può diventare una busta finale;
- un profilo condiviso può essere soltanto seed/evidenza;
- un `LaunchPlan` calibrato usa esclusivamente un record locale attivo `calibration-record/v2`;
- modello, artefatto, motore, OS, backend, hardware, driver, modo e headroom devono coincidere;
- in assenza di record compatibile si usa la baseline dichiarata o si esegue `calibrate`.

La wheel 0.1 lascia quindi `resources/content/profiles/` assente o vuota.

## Contratti attivi

La separazione corrente è:

| Contratto | Scope | Uso runtime |
|---|---|---|
| `calibration-policy/v2` | pubblico | metodo completo di ricerca locale |
| `calibration-report/v2` | pubblico | evidenza e solo seed `n_cpu_moe` di ordine |
| `calibration-record/v2` | privato locale | busta attiva, se identità e headroom coincidono |
| `profile/v1` | storico | validazione/compatibilità, mai optimum remoto |

Il report pubblico non passa al piano contesto, hardware, tok/s o busta osservata. Rimuovere il seed
non cambia dominio, scala contesti, riserve, tetto probe o selezione.

## Contribuire

Non proporre nuovi `profile/v1` per la 0.1. Un contributo di calibrazione segue
[`../calibration-contributing.md`](../calibration-contributing.md), usa `calibration/v3` e pubblica
soltanto un report v2 privacy-safe con scope misurato e limite di portabilità espliciti. Ogni utente
continua a generare il proprio record locale.
