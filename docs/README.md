# Documentazione

Questa directory descrive **il comportamento del codice nel branch corrente**. Non contiene tracker,
proposte o piani di implementazione conclusi.

La lettura consigliata è lineare:

1. [Installazione e primo avvio](installation.md) — piattaforme, requisiti, modello, motore e avvio
   iniziale;
2. [Comandi](commands.md) — intera superficie CLI, opzioni, output ed exit code;
3. [Configurazione e dati locali](configuration.md) — TOML, variabili ambiente, precedenze e
   directory gestite;
4. [Architettura](architecture.md) — componenti, flussi, contratti, lifecycle e confini di
   sicurezza;
5. [Calibrazione](calibration.md) — ricerca locale v3, benchmark, record, riuso ed evidenza
   condivisa;
6. [Operazioni e diagnostica](operations.md) — controlli ordinari, errori e recupero;
7. [Sviluppo](development.md) — struttura del repository, contenuti, test, packaging e contributi;
8. [Release](releasing.md) — costruzione, pubblicazione e stato degli artefatti pubblici.

Per una panoramica breve e un quick start vedere il [README principale](../README.md).

## Quale fonte consultare

| Domanda | Fonte |
|---|---|
| Cosa fa oggi il programma? | codice, lock, schemi, test e questa documentazione |
| Quali versioni e checksum sono accettati? | `src/qwen_launcher/resources/engine.lock` e contenuti versionati |
| Da quali misure derivano lock e report? | [`evidence/`](../evidence/README.md) |
| Come si contribuisce? | [CONTRIBUTING.md](../CONTRIBUTING.md) e [sviluppo](development.md) |
| Cosa è previsto ma non implementato? | [IMPLEMENTATION_SPEC.md](../IMPLEMENTATION_SPEC.md) |
| Cosa è cambiato fra le versioni? | [CHANGELOG.md](../CHANGELOG.md) |

`IMPLEMENTATION_SPEC.md` è il piano normativo, non un manuale utente. Le prove grezze sono separate
in `evidence/` perché servono a verificare la provenienza dei contratti, non a spiegare l'uso
quotidiano del launcher.

## Stato corrente

La release pubblica è `0.1.0`. Il branch `main` contiene questa documentazione riorganizzata e due
correzioni runtime non incluse negli artefatti immutabili della release: porta temporanea per i trial
quando `llama_port` è occupata e tolleranza massima di 1 MiB nella lettura del totale RAM per il
riuso dei record. La sezione `Unreleased` del changelog riassume le differenze.

PyPI non ospita ancora `0.1.0`: il job di pubblicazione attende la configurazione del Trusted
Publisher. Gli artefatti verificati sono disponibili nella GitHub Release `v0.1.0`; non vanno
ricostruiti o sostituiti.

## Limiti attuali

- supporto garantito: Ubuntu 22.04+ x86-64 e Windows 11 x86-64;
- backend: CPU oppure una singola GPU NVIDIA CUDA;
- CUDA su host multi-GPU bloccato;
- modello predefinito e `llama.cpp` fissati a identità precise;
- pesi e mmproj non redistribuiti e non scaricati automaticamente;
- evidenza empirica della calibrazione ancora `GATE-PARTIAL` perché copre un solo hardware reale;
- nessuna garanzia di stabilità delle interfacce della serie 0.1.

**Successivo:** [Installazione e primo avvio](installation.md)
