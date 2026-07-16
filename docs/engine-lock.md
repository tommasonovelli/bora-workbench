# Aggiornamento controllato di `engine.lock`

`engine.lock` è il contratto macchina eseguibile di `llama.cpp`. Non è un elenco aggiornato
automaticamente e non segue `latest`: release, commit, asset, flag, API e salute cambiano soltanto
dopo un nuovo spike reale approvato secondo `IMPLEMENTATION_SPEC.md`, sezioni 2, 5.7, 5.8 e 7.

## Contratto attivo

La release attiva è `b10011`, commit
`bf2c86ddc0685f580595954056c2e77ebabfab4f`. La matrice verificata e ora completa contiene:

- Ubuntu CPU: prebuilt ufficiale `llama-b10011-bin-ubuntu-x64.tar.gz`;
- Ubuntu CUDA: archivio sorgente del commit completo;
- Windows CPU: prebuilt ufficiale `llama-b10011-bin-win-cpu-x64.zip`;
- Windows CUDA: server CUDA 13.3 e runtime CUDA 13.3 sovrapposti.

URL, SHA-256, formati, ruoli e percorsi eseguibili sono dati normativi nel lock. L'evidenza da cui
sono copiati è `docs/spike-0.json`; gli output grezzi e i manifest sono sotto `docs/spike-0/`.

## Procedura di aggiornamento volontario

1. Aprire uno spike separato e ottenere l'approvazione esplicita della nuova release precisa.
2. Registrare tag, commit sorgente completo, `--version`, `--help`, licenza e asset ufficiali. Non
   usare il ramo corrente per correggere il contratto di una release appuntata.
3. Scaricare ogni archivio tramite HTTPS e conservarne nome, URL e SHA-256 pubblicato. Verificare
   localmente con `sha256sum <file>` su Ubuntu o `Get-FileHash -Algorithm SHA256 <file>` su Windows.
4. Estrarre in una directory di prova sicura. Per Windows CUDA sovrapporre soltanto la coppia
   server/runtime della stessa versione CUDA e registrare tutti i file risultanti.
5. Per Ubuntu CUDA compilare l'archivio del commit, non un clone di tag mobile, con il contratto
   verificato:

   ```text
   cmake -S <source> -B <build> -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON \
     -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release \
     -DLLAMA_BUILD_NUMBER=<numero-release> -DLLAMA_BUILD_COMMIT=<commit-completo>
   cmake --build <build> --config Release --parallel <core> --target llama-server
   ```

6. Ripetere su Ubuntu e Windows la matrice CPU/CUDA dei tre modi, salute, API, metriche, UI,
   vision, MTP, selezione GPU, log, stop e `benchmark/v1`. Un asset non provato non entra nel lock.
7. Aggiornare insieme `docs/spike-0.md`, `docs/spike-0.json`, output grezzi, manifest SHA-256 e
   `resources/engine.lock`. Impostare `assets_complete=true` soltanto quando tutte e quattro le
   coppie supportate hanno l'insieme esatto di ruoli verificati.
8. Riesaminare licenze e redistribuibilità. Le installazioni gestite conservano il testo MIT di
   llama.cpp; Windows CUDA conserva anche la CUDA Toolkit EULA applicabile ai runtime verificati.
9. Eseguire validazione, suite, build e verifica wheel, quindi ripetere le quattro installazioni
   reali e un avvio `coding` da ciascuna installazione gestita.

Una divergenza fra digest pubblicato, archivio scaricato, output reale e lock ferma l'aggiornamento;
non si sostituisce un valore con una supposizione.

## Installazione e attivazione

`qwen-launcher engine install` seleziona il backend rilevato. I download finiscono prima in file
univoci `.part` sotto la cache gestita e vengono promossi soltanto dopo SHA-256 corretto. L'estrazione
rifiuta percorsi assoluti, drive Windows, `..`, link e file speciali.

Ogni installazione verificata viene promossa in una nuova directory immutabile sotto
`data_dir()/engine/installations/`. Il puntatore attivo è `data_dir()/engine/current.json`, schema
`managed-engine/v1`, e contiene soltanto release, backend e percorso relativo confinato. Il file è
scritto, sincronizzato e sostituito atomicamente nella stessa directory: un fallimento di staging,
verifica o attivazione lascia intatti installazione e manifest precedenti. `--force` crea comunque
una nuova installazione; un target identico e già compatibile è altrimenti un no-op.

`qwen-launcher engine status` mostra manifest attivo, eseguibile, compatibilità e differenze dal
lock. Un manifest corrotto non viene seguito; una nuova installazione completa può sostituirlo solo
dopo avere verificato il nuovo eseguibile.
