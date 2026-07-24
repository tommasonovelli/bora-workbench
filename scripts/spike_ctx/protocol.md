# Protocollo spike cross-context (`D-061`)

Questo pacchetto prepara una misura reale; **non** autorizza né implementa `calibration/v6-lite`.
L'esecuzione e il verdetto sono del maintainer. Prima del run chiudere workload GPU, verificare
`qwen-launcher validate`, modello/mmproj e `llama.cpp b10011`, quindi usare un output privato nuovo:

```bash
uv run --frozen python -m scripts.spike_ctx --output /tmp/qwen-spike-ctx-evidence
```

Per collaudare parser, richieste, bisezione e struttura senza modello o GPU:

```bash
uv run --frozen python -m scripts.spike_ctx \
  --dry-run --output /tmp/qwen-spike-ctx-dry
```

## Misure

Il runner usa il builder e il lifecycle reali, una porta loopback temporanea e una directory runtime
gestita da `tempfile` (sotto `/tmp` su Ubuntu). Ogni processo applica 0,5 GiB di riserva VRAM,
2,0 GiB RAM e 0,125 GiB di tolleranza al rilascio. I contesti sono 131072, 65536 e 32768. A 131K
misura il boundary storico 37 e il prudente 41; a 65K/32K prova prima il prudente 41 e usa poi al
massimo sei decisioni binarie nel dominio `[0,41]`, con un solo retry per esito ritentabile e
classificazione per classe.

Ogni configurazione esegue:

1. un warm-up corto escluso;
2. tre richieste corte da 128 token;
3. una richiesta deterministica da circa 8K token con output 64;
4. `cache_prompt:false`, `ignore_eos:true`, seed `424242`;
5. wall-clock end-to-end e i campi `timings` della risposta;
6. minimi RAM/VRAM, stop e verifica del rilascio.

Appendice A ripete i boundary 131K e 65K con MTP disabilitato. Acceptance MTP si ricava soltanto da
`draft_n_accepted / draft_n`; non si analizzano i log. Appendice B avvia 32K con `--reasoning off`,
fa tre richieste e cerca `<think>` nelle risposte; aggiunge `--reasoning-budget 0` soltanto se il
primo meccanismo non basta.

Se il confronto cade fra gradini, eseguire un'estensione revisionata a 98304 o 49152 in un nuovo
output prima del verdetto; non ricostruire manualmente misure mancanti:

```bash
uv run --frozen python -m scripts.spike_ctx \
  --refine-ctx 98304 --output /tmp/qwen-spike-ctx-refine-98k
```

Usare `49152` soltanto per il raffinamento 65K↔32K. Il runner base non dichiara automaticamente che
il raffinamento sia necessario.

## Verdetto umano

Confrontare il migliore fra 65K e 32K con il migliore 131K. È **GO** se almeno una condizione vale:

- mediana end-to-end corta `≤ 0,92 ×` quella 131K;
- prefill della richiesta 8K `≥ 1,25 ×` quello 131K;
- prestazioni entro deadband 3% e almeno 0,5 GiB di VRAM libera minima in più.

Altrimenti è **NO-GO**. Il 3% è un miglioramento minimo materiale, non significatività statistica.
MTP e reasoning sono dati informativi e non cambiano automaticamente il verdetto.

## Redazione e commit dell'evidenza

L'output iniziale è privato: risposte e log possono contenere testo o percorsi locali. Copiare il
template da `evidence/engine/cross-context-spike-template/`, sostituire i placeholder soltanto con
misure presenti, rimuovere hostname, username e percorsi assoluti, poi rigenerare `SHA256SUMS` sui
byte finali. Verificare manualmente ogni file prima del commit. Il documento finale deve dire
esplicitamente `GO` o `NO-GO`, hardware/OS redatti, criteri applicati, limiti e meccanismo reasoning.

Solo un **GO committato** insieme a una nuova decisione normativa autorizza la Fase 2. Un dry-run,
un run incompleto o la sola presenza di `results.json` non è un Gate.
