CIE ID 1.5.2 (build 35) per macOS 12 o successivo, Universal per Apple Silicon e Intel.

Questa versione introduce una guida aggiornata per il fork e corregge l'apertura dei collegamenti del tutorial:

- guida in italiano inclusa nell'app e consultabile offline dal menu **Tutorial**;
- istruzioni per associazione della CIE, firma e verifica dei documenti, cambio PIN, sblocco con PUK e utilizzo nei browser;
- collegamento aggiornato alla pagina ufficiale [Software CIE](https://www.cartaidentita.interno.gov.it/info-utili/software-cie-2/);
- collegamenti web aperti nel browser predefinito, compresi quelli che richiedono una nuova finestra;
- istruzioni adeguate al bundle del fork e rimozione dei riferimenti agli strumenti di sviluppo dai testi per l'utente.

La versione mantiene le correzioni di sicurezza e le dipendenze della 1.5.1. Il DMG conserva la finestra più alta (640 × 420 punti) con le icone dell'app e di Applicazioni.

Fork indipendente di [italia/cie-middleware-macos](https://github.com/italia/cie-middleware-macos). Questo fork non è un prodotto ufficiale dell'Istituto Poligrafico e Zecca dello Stato Italiano e non è approvato o supportato da IPZS.

### Installazione

1. Scaricare **CIE-ID-Universal.dmg**.
2. Chiudere CIE ID e aprire il DMG.
3. Trascinare **CIE ID.app** sul collegamento **Applicazioni**. Se esiste un'app omonima, verificare quale copia conservare prima di sostituirla.
4. Espellere il volume e avviare CIE ID da Applicazioni.
5. Aprire **Tutorial** nel menu laterale per consultare la nuova guida.

Carta CIE e lettore compatibile sono necessari per le operazioni sulla carta; la verifica della revoca e i collegamenti ai siti web richiedono Internet. Chi aggiorna una precedente versione di questo fork conserva gli stessi identificativi dell'app; chi proviene dall'app ufficiale può dover associare nuovamente la CIE.

App, middleware ed estensione CryptoTokenKit sono firmati con **Developer ID Application: GIAN CARLO EZZA (S2NL5NXU7Y)**. App e DMG sono notarizzati da Apple e includono il ticket. Sono verificati Gatekeeper e l'integrità dell'app montata e copiata dal DMG.

### Materiali allegati

- **CIE-ID-Universal.dmg**: app Universal firmata e notarizzata, con collegamento ad Applicazioni.
- **CIE-ID-corresponding-source.tar.gz**: sorgenti corrispondenti di app, SDK, middleware, estensione e delle 13 dipendenze, con ricette di ricompilazione e ricollegamento.
- **INSTALLAZIONE.txt**: istruzioni in italiano.
- **SHA256SUMS.txt**: checksum dei tre allegati precedenti.

Salvare i quattro file nella stessa cartella e verificare:

```sh
shasum -a 256 -c SHA256SUMS.txt
```

I download automatici GitHub “Source code” non includono gli archivi delle dipendenze: per ricompilare usare l'allegato **corresponding-source.tar.gz**. Licenze e attribuzioni sono in `LICENSE.txt`, `LICENSES/`, `THIRD_PARTY_NOTICES.md` e `LICENSE_AUDIT.md`; istruzioni in `Docs/REBUILDING.md`.

### Verifiche

Suite SDK, middleware, interfaccia e navigazione della guida superate su ARM64 e x86_64 (Intel eseguito tramite Rosetta). Verificati il caricamento locale della guida, i collegamenti dell'indice e l'apertura della pagina ufficiale nel browser predefinito. Sono incluse le regressioni sulle risposte OCSP/CRL non valide e sulle connessioni TLS non attendibili; dettagli in `Docs/SECURITY.md`.

La verifica della revoca non costituisce una validazione qualificata eIDAS o LTV. Il collaudo software e la notarizzazione restano distinti dal collaudo hardware con CIE, lettori e Mac Intel reali.
