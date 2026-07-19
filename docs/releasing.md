# Procedura release 0.1

Questa guida separa preparazione locale, Human Gate e pubblicazione. Nessun passaggio locale
costituisce autorizzazione a creare tag, push, release GitHub, progetto PyPI, Trusted Publisher o
upload.

## Step 6A: release candidate locale

La versione è `0.1.0rc1`. Da un checkout pulito:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --frozen qwen-launcher validate
# eseguire da un checkout pulito con dist/ assente
uv build
uv run --frozen python scripts/verify_wheel.py
```

Calcolare e conservare SHA-256 di wheel e sdist. Trasferire il release candidate e il digest tramite
canali distinti o comunque verificabili. Finché il pacchetto non esiste su PyPI, usare soltanto il
percorso esplicito degli installer:

```bash
sh ./install.sh --wheel <wheel-rc-locale> --sha256 <64-hex-verificato>
```

```powershell
.\install.ps1 -Wheel <wheel-rc-locale> -Sha256 <64-hex-verificato>
```

Un commit Git è ammesso soltanto come SHA completo tramite `--git-commit` / `-GitCommit`. Non
pubblicare un one-liner PyPI per una versione inesistente.

## Human Gate 0.1

Tommaso verifica personalmente l'artefatto RC con hash verificato:

### Ubuntu 22.04 pulito

- installer RC, `--version`, `validate` e `doctor`;
- `engine install` e contratto compatibile;
- `coding`, `studio`, `vstudio`, salute, UI/vision e stop;
- macchina senza record: baseline dichiarata, calibrazione e riuso;
- bundle separato, validazione e nessun upload;
- `uninstall`, confini delle directory e cache Hugging Face intatta.

### Windows Sandbox

Ripetere lo stesso percorso con `install.ps1`, inclusi motore, tre modi, calibrazione, record,
disinstallazione e verifica che non restino processi o porte.

### Portabilità e contenuti

- un seed di altro hardware non entra direttamente nel piano;
- la ricerca resta completa e deterministica con o senza seed;
- modello, mmproj, policy, report, manifest, licenze e avvisi sono presenti negli artefatti;
- nomi progetto/account e metadati sono controllati manualmente;
- il limite `GATE-PARTIAL` resta visibile.

Il Gate termina con una decisione esplicita `RELEASE` oppure `NO-RELEASE`. `NO-RELEASE` riapre il
solo step responsabile; non si correggono artefatti pubblicati o misure a mano.

## Preparare PyPI Trusted Publishing

Queste operazioni sono umane e avvengono soltanto durante il Gate:

1. creare o verificare il progetto PyPI `qwen-launcher`;
2. creare l'ambiente GitHub `pypi` con approvatore richiesto;
3. configurare su PyPI un Trusted Publisher per:
   - owner: `tommasonovelli`;
   - repository: `qwen-launcher`;
   - workflow: `release.yml`;
   - environment: `pypi`;
4. verificare che non esistano token PyPI nel repository o nei secret del workflow.

Il workflow `.github/workflows/release.yml` usa permessi globali `contents: read`. Soltanto il job
`publish` riceve `id-token: write`, dipende dalla matrice di test e dall'artefatto costruito e
verificato, e attende l'approvazione dell'ambiente `pypi`. Tutte le action sono appuntate a commit
SHA completi.

## Step 6B e pubblicazione

Dopo `RELEASE` esplicito, lo Step 6B aggiorna localmente versione `0.1.0`, changelog e riferimenti RC,
poi ripete suite e build. Anche in quel momento push, tag `v0.1.0`, release GitHub e upload non sono
impliciti.

Quando Tommaso autorizza e crea il tag esatto, il workflow:

1. ripete test e validazione su Ubuntu e Windows;
2. verifica che il tag `v<versione>` coincida coi metadati;
3. costruisce wheel e sdist e verifica la wheel in isolamento;
4. trasferisce l'artefatto fra job tramite GitHub Actions;
5. pubblica con OIDC soltanto dopo l'approvazione dell'ambiente.

## Verifica post-pubblicazione

Su Ubuntu pulito e Windows Sandbox:

- verificare hash e metadati degli artefatti PyPI;
- usare il percorso installer PyPI soltanto ora, con versione esplicita già esistente;
- controllare `qwen-launcher --version`, `validate` e `doctor`;
- eseguire almeno i modi principali e uno stop pulito;
- verificare di nuovo `uninstall` e `uv tool uninstall qwen-launcher`.

Eventuali problemi post-pubblicazione vengono documentati; una versione esistente non viene
sostituita in place.
