# Contribuire

Il progetto segue il piano normativo `IMPLEMENTATION_SPEC.md` e procede uno step
alla volta. Prima di una modifica:

1. leggere l'intero piano e il tracker iniziale;
2. non anticipare feature di step successivi;
3. non inventare flag, benchmark o compatibilità del motore;
4. non usare rete nei test;
5. non modificare configurazione utente o cache Hugging Face.

Una pull request modifica **contenuto dichiarativo oppure core, mai entrambi**. I report devono
contenere misure reali raccolte con `calibration/v3` e la release del lock. Non si accettano profili
`profile/v1` di produzione: una misura su un host non può diventare una busta finale per altri PC.
L'evidenza condivisa può soltanto ordinare la stessa ricerca locale completa.

La procedura, il naming, i checksum, la checklist privacy e il testo PR sono in
[`docs/calibration-contributing.md`](docs/calibration-contributing.md). Il flusso è manuale e non
crea autenticazione, upload, branch remoti, issue o pull request. La sola evidenza v3 attuale resta
Windows 11/CUDA su RTX 2060 SUPER 8 GiB e 31,92 GiB RAM; la copertura è `GATE-PARTIAL` e il
follow-up su hardware materialmente diverso è aperto ma non bloccante per D-047.

## Revisione delle pull request

Il branch `main` è protetto. Prima del merge di una PR di un contributore:

- la CI Ubuntu e Windows deve essere verde e il branch deve essere aggiornato;
- l'unico maintainer esegue personalmente la revisione come code owner;
- è richiesta almeno un'approvazione del code owner;
- nuovi commit annullano l'approvazione precedente e richiedono una nuova revisione.

CI verde e approvazione sono necessarie, ma non garantiscono il merge. Una PR può richiedere
correzioni o essere rifiutata se esce dal perimetro dello step, manca di evidenze o contraddice la
specifica. Essendoci un solo maintainer, non è garantito un tempo preciso di revisione.

Il bypass amministratore resta attivo per evitare che l'unico code owner rimanga bloccato sulle
proprie modifiche. Non cambia il flusso dei contributori e le modifiche del maintainer vengono
comunque verificate dalla CI.

## Verifiche

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Usare Conventional Commits. Push, tag e pubblicazioni richiedono sempre autorizzazione esplicita.
