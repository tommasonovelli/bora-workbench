# Anatomia di un modo `mode/v1`

Un modo descrive **comportamento**, non prestazioni o capacità hardware. I tre modi 0.1 sono risorse
JSON sotto `src/qwen_launcher/resources/content/modes/` e vengono validati con JSON Schema 2020-12.

## Campi

```json
{
  "schema": "mode/v1",
  "id": "coding",
  "description": "...",
  "services": {
    "ui": false,
    "vision": false
  },
  "sampling": {
    "temp": 0.6,
    "top_p": 0.95,
    "top_k": 20
  }
}
```

- `schema`: deve essere esattamente `mode/v1`;
- `id`: ASCII minuscolo/trattini e uguale al nome del file senza `.json`;
- `description`: testo non vuoto mostrabile all'utente;
- `services.ui`: abilita o disabilita esplicitamente la UI integrata;
- `services.vision`: abilita o disabilita esplicitamente il mmproj appuntato;
- `sampling`: temperatura, top-p e top-k verificati per il modo.

`additionalProperties` è falso. Un modo non può contenere contesto, `n_cpu_moe`, intervalli RAM/VRAM,
identità hardware, flag motore o risultati benchmark.

## Modi distribuiti

| Modo | UI | Vision | Sampling `(temp, top_p, top_k)` |
|---|---:|---:|---|
| `coding` | no | no | `(0.6, 0.95, 20)` |
| `studio` | sì | no | `(0.7, 0.8, 20)` |
| `vstudio` | sì | sì | `(0.7, 0.8, 20)` |

Questi valori derivano dalla matrice funzionale dello Spike 0; non sono profili prestazionali.

## Composizione nel lancio

Il launcher carica il modo e lo combina con:

1. configurazione utente validata;
2. hardware rilevato;
3. record locale `calibration-record/v2` compatibile e con headroom, oppure baseline dichiarata;
4. modello e motore risolti ai contratti appuntati.

Il risultato è un `LaunchPlan`. UI, vision e sampling arrivano soltanto dal modo; contesto e
`n_cpu_moe` arrivano soltanto dal record locale o dal fallback. Un report condiviso può cambiare
l'ordine dei probe di calibrazione, ma non il piano.

## Modifiche e validazione

Una pull request che modifica un modo è contenuto dichiarativo e non deve includere modifiche al core.
Prima della revisione:

```bash
uv run --frozen qwen-launcher validate
uv run --frozen pytest
uv build
uv run --frozen python scripts/verify_wheel.py
```

Non aggiungere nuovi servizi o campi a `mode/v1`: una modifica incompatibile richiede uno schema
versionato e una milestone che la autorizzi.
