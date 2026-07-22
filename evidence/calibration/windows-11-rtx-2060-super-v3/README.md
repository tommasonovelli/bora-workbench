# Evidenza `windows-11-rtx-2060-super-v3`

Questa directory lega tramite SHA-256 la policy pubblica, il report strutturato e le due fonti
revisionate della calibrazione v3. Non contiene record locali o log grezzi.

Dalla radice del repository verificare:

```bash
sha256sum -c evidence/calibration/windows-11-rtx-2060-super-v3/SHA256SUMS
```

## Scope misurato

- Windows 11 build 10.0.26200;
- backend CUDA e driver NVIDIA 610.47;
- NVIDIA GeForce RTX 2060 SUPER con 8 GiB VRAM;
- 31,92 GiB RAM;
- modi `coding`, `studio` e `vstudio`;
- modello e motore esatti appuntati nel repository.

L'esito locale è accettato, ma la copertura complessiva resta `GATE-PARTIAL`: le costanti non sono
state ripetute su hardware materialmente diverso.

## Uso consentito

Il report conserva le buste osservate soltanto come evidenza. Il loader proietta esclusivamente
`seed_n_cpu_moe` per anticipare un probe in una nuova ricerca locale completa. Non trasferisce
contesto, hardware, tok/s o busta nel `LaunchPlan` di un altro PC.

`gate.md` e `protocol.md` mantengono i byte originali perché i loro digest sono referenziati dal
report. Eventuali percorsi storici nel testo fanno parte dell'evidenza hashata.
