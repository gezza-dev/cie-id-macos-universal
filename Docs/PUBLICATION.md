# Pubblicazione del fork indipendente

## Repository dei sorgenti

RSAEURO, SHA-1 legacy e parti GPL dell'SDK sono sostituiti nello snapshot
corrente; vedere `LICENSE_AUDIT.md` e il registro
`scripts/replaced-legacy-sources.json`. La licenza principale BSD non è
stata estesa ai file LGPL/GPL o alle dipendenze con licenze diverse.

1. Eseguire `python3 scripts/check-publication.py --publish` e revisionare
   le modifiche. Conservare `LICENSE.txt`, avvisi originali, `LICENSES/`,
   README, audit, inventari e ricette.
2. Scegliere nome e descrizione che identifichino un fork indipendente,
   mantenendo repository e commit upstream nel README. Il nome e l'account
   GitHub non sono fissati: non sono stati inventati indirizzi di release.
3. Usare un **nuovo repository dello snapshot ripulito**, senza importare
   `.git`, `.build`, `dist` o le copie locali di recupero. Il pacchetto di
   sorgenti corrispondenti contiene una directory `cie-middleware-macos`
   pronta per essere estratta; eliminare da quella copia la sola `.build`
   che contiene gli archivi delle dipendenze, prima di inizializzare il
   nuovo repository. Conservare l'archivio completo per la release dell'app.
4. Escludere certificati e chiavi private, profili e dati CIE/PIN; revisionare
   gli untracked prima di aggiungerli. Le chiavi pubbliche tecniche upstream
   non vanno confuse con chiavi private di firma.
5. Inizializzare e committare il nuovo repository, poi pubblicarlo con il
   proprio account. La pubblicazione remota non viene eseguita dagli script.

## Storia upstream

Il pulsante Fork di GitHub o il push di tutta la storia redistribuiscono
anche RSAEURO, SHA-1 e vecchi binari rimasti nei commit precedenti. Questa
migrazione **non** risolve i diritti di redistribuzione di quei vecchi file.
La storia locale è conservata per recupero; le rimozioni riguardano lo
snapshot corrente. Per questo il percorso preparato è un fork indipendente
pubblicato come repository nuovo, con attribuzione e provenienza upstream.

## Release dell'app

1. Configurare branding, bundle identifier, App Group e provisioning per il
   proprio team tramite `LocalSigning.xcconfig` (vedere README). App e CTK
   usano identificativi configurabili del fork. Il fork non è approvato da
   IPZS e la licenza del codice non
   certifica diritti sui marchi.
2. Compilare e testare con `scripts/build-native-app.py`; scegliere la firma
   appropriata e completare collaudo CIE/lettore. Per distribuzione esterna
   al Mac App Store predisporre Developer ID e notarizzazione.
3. Eseguire `scripts/prepare-source-package.py --arch arm64`. Il risultato
   contiene sorgenti esatti del progetto, delle dipendenze e ricette per
   modifica/ricompilazione/ricollegamento LGPL. FreeType è scelto sotto FTL.
4. Eseguire `scripts/check-publication.py --release --arch arm64` e distribuire
   insieme app e `cie-corresponding-source.tar.gz` abbinato. Conservare
   avvisi e condizioni, consentendo gli usi richiesti da LGPL. Seguire
   `Docs/REBUILDING.md`, anche dopo modifiche o una nuova firma.
5. Non includere `TestCIE` nella release binaria dell'app: il tool GPL è
   separato, i suoi sorgenti e la licenza restano nello snapshot.

I controlli distinguono integrità delle licenze e corrispondenza dei
materiali dalle verifiche Apple e dal collaudo hardware. Non attestano
notarizzazione, sicurezza per uso produttivo o l'adempimento futuro degli
obblighi da parte del distributore. Una firma Apple Development vale per il collaudo locale.

Le risorse di licenza sono copiate prima della firma. La copia verso `dist`
cambia i flag Finder e conserva i contenuti; modificare i file del bundle
richiede una nuova firma e un nuovo abbinamento con i materiali della release.
