# Evidenza verificata

Questa directory contiene output misurati, fonti acquisite e manifest SHA-256 che sostengono i
contratti distribuiti. Non è documentazione utente e non è una raccolta di piani.

- `engine/spike-0.*` e `engine/spike-0/`: selezione e matrice reale di `llama.cpp b10011`;
- `engine/kv-q8-*`: prove che sostengono cache K/V Q8 con mmap sul ramo CUDA;
- `engine/cross-context-spike-template/`: solo template non misurato per il futuro run D-061;
- `calibration/windows-11-rtx-2060-super-v3/`: fonti checksum-bound del report pubblico v3.

I file grezzi coperti da manifest vanno conservati byte per byte. Alcuni documenti accettati
contengono riferimenti ai percorsi storici sotto `docs/`: quei riferimenti fanno parte dei byte
hashati e non vengono riscritti. I percorsi correnti autorevoli sono quelli nei manifest e nei
`source_references` del report distribuito.

Per capire il comportamento attuale usare [`docs/`](../docs/README.md). Per cambiare un lock o
aggiungere nuova evidenza seguire [Sviluppo e contributi](../docs/development.md).
