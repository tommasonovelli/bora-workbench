# Benchmark, calibrazione e regressione

## Stato nella 0.1

`benchmark/v1` è implementato come operazione riusabile dalla calibrazione, ma la 0.1 non espone un
comando `qwen-launcher benchmark`. Il comando autonomo è previsto dallo Step 9 della 0.2. Un normale
lancio non esegue benchmark implicitamente.

Le risorse immutabili sono incluse nella wheel:

- `resources/benchmark-v1/prompt.txt`, SHA-256
  `1c7182235411da2d4fe6fca130e3effb0b0d965569c52abd8fd45327103ddb2e`;
- `resources/benchmark-v1/request.json`, SHA-256
  `025dc91aeb61a790d5fd36c27f127e04761ae7f1c3d6b542d0cfd9d37bc5c19f`.

Una modifica richiederebbe `benchmark/v2`; non si cambia retroattivamente il protocollo.

## Protocollo `benchmark/v1`

Per ogni sessione valida:

1. nessun client concorrente;
2. una richiesta completa di warm-up, esclusa dai risultati;
3. cinque richieste misurate;
4. esattamente 256 completion token per misura;
5. `max_tokens=256`, `ignore_eos=true`, seed `424242`;
6. `finish_reason=length`, `completion_tokens=256` e `predicted_n=256` obbligatori;
7. tok/s da `response.timings.predicted_per_second`, ricontrollato con
   `predicted_n / predicted_ms`;
8. registrazione di ogni valore e riepilogo minimo, mediana e massimo.

Un timeout, conteggio token diverso o risposta incompatibile rende la misura invalida; non viene
sostituita con un numero stimato.

## Benchmark non significa calibrazione

Un benchmark misura una busta già scelta. La calibrazione v3 invece:

- cerca il dominio locale e la scala contesti approvati;
- misura RAM e, su CUDA, VRAM e rilascio;
- usa processi freschi;
- confronta due finalisti in round `A→B` e `B→A`;
- esegue un `benchmark/v1` completo su ogni avvio;
- richiede riserve assolute e ricostruisce deterministicamente la selezione.

Un singolo benchmark non può quindi creare o aggiornare un record calibrato.

## Interpretazione corretta

Tok/s non misura qualità semantica. I valori non devono essere confrontati come promessa fra:

- modelli, release motore o contratti comando diversi;
- contesti diversi;
- modi o backend diversi;
- componenti, driver o carico ambientale diversi;
- cache o parametri non identici.

Le misure dello Spike 0 provano fattibilità della busta `ctx=8192`; le misure del Gate v3 spiegano
la selezione locale della macchina osservata. Nessuna delle due diventa una previsione per altri PC.

## Regressione

Una regressione futura deve ripetere lo stesso protocollo, conservare metadati e misure singole e
confrontare soltanto scope compatibili. La 0.1 non inventa una soglia percentuale universale. Una
variazione va riportata con il rumore osservato e non modifica automaticamente record, policy o
contenuti distribuiti.

Vedere [`calibration.md`](calibration.md) per il protocollo v3 e
[`spike-0.md`](spike-0.md) per le misure di fattibilità originali.
