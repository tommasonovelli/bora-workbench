# Evidenza di riferimento `windows-11-rtx-2060-super-v3`

Questa directory lega tramite SHA-256 la policy pubblica, il report strutturato e le fonti revisionate
del Gate `calibration/v3` del 19 luglio 2026. Verifica il manifest dalla radice del repository:

```console
sha256sum -c docs/calibrations/windows-11-rtx-2060-super-v3/SHA256SUMS
```

## Perimetro misurato

L'unica evidenza reale `calibration/v3` distribuita copre:

- Windows 11 build 10.0.26200;
- backend CUDA e driver NVIDIA 610.47;
- NVIDIA GeForce RTX 2060 SUPER con 8 GiB VRAM;
- 31,92 GiB RAM;
- `coding`, `studio` e `vstudio` sul modello e motore appuntati.

L'esito locale è `CALIBRATION-ACCEPTED`; la copertura complessiva resta `GATE-PARTIAL`. Le costanti
non sono state validate empiricamente su hardware materialmente diverso. Quel collaudo resta un
follow-up aperto e non bloccante per D-047.

## Limite d'uso

Il report conserva le buste osservate 37/37/39 soltanto come evidenza locale. Il loader ne proietta
esclusivamente `seed_n_cpu_moe` per anticipare un probe dentro la staffa di una nuova ricerca
completa con modello, motore, backend e modo compatibili. Non importa contesto, hardware, tok/s o
busta nel `LaunchPlan`; cancellare o ignorare il report non cambia dominio, scala contesti, tetto probe,
riserve o selezione locale.

Il report non contiene hostname, username, percorsi privati o log locali. I record candidato e i log
del Gate rimangono nella directory dati privata e non fanno parte del repository.
