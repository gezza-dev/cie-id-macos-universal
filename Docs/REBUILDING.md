# Ricompilare e ricollegare la distribuzione

Il pacchetto `cie-corresponding-source.tar.gz` accompagna l'app a cui si
riferiscono i checksum in `SOURCE_MANIFEST.json`. Contiene lo snapshot
completo, le modifiche e gli archivi esatti dei sorgenti delle 13 dipendenze.
Non contiene la vecchia storia Git, prodotti upstream non verificati,
certificati privati, dati della carta o chiavi di firma Apple.

## Ambiente e build

La build verificata usa macOS 26.7.1, Xcode 27, CMake e Python 3.10 o
successivo su Apple Silicon. Le versioni effettive e il deployment target
12.0 sono registrati nel manifest del pacchetto. Installare Xcode completo,
avviarlo e completare l'installazione dei componenti. Sono necessari anche
CMake e gli strumenti di build richiesti dalle dipendenze: `make`, `perl`,
`pkg-config`, Meson 1.11 o successivo, Ninja e gli strumenti forniti da Xcode; il builder segnala quelli
mancanti. Questi strumenti non sono inclusi come binari nel pacchetto.

Estrarre l'archivio e dalla directory `cie-middleware-macos`:

```sh
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
python3 scripts/build-native-app.py --arch arm64 --jobs 6 --clean
```

Le dipendenze vengono ricostruite da zero. Gli archivi nella cache
`.build/dependencies/downloads` sono verificati con i SHA-256 nei lockfile:
non occorre recuperarli da un sito per ricompilare questa versione.
Il builder applica le eventuali modifiche attraverso le ricette incluse.
OpenSSL 3.5.9 viene compilato con `no-shared`, `no-module` e
`no-autoload-config`: provider default/legacy statici, senza dipendenza da
percorsi assoluti di moduli/configurazioni sul Mac del compilatore.
Curl e PoDoFo vengono ricostruiti quando cambia il lock OpenSSL.
PoDoFo 1.1.2 usa le API di firma differita; la build seleziona C++17 e
produce gli archivi `libpodofo.a`, `libpodofo_private.a`, `libpodofo_3rdparty.a`.
Fontconfig 2.18.3 viene compilato con Meson mediante un file cross per ciascuna
architettura. Curl usa OpenSSL con Apple SecTrust e il trust store di macOS.
I test SDK/middleware vengono eseguiti prima della build Xcode. Il risultato
unsigned è `dist/arm64/CIE ID.app`.

Per evitare attese di File Provider nei checkout iCloud, Xcode compila una
copia temporanea locale dello stesso snapshot. Il bundle verificato viene
esportato in `dist`; la copia temporanea viene rimossa.

Il processo ricompila e ricollega l'intera app, SDK, middleware ed estensione;
non dipende da librerie proprietarie precompilate del fork. Il manifest
identifica la build di partenza, senza promettere output identico byte per
byte: timestamp, SDK Apple e firma possono cambiare i byte prodotti.

## Variante Universal

Per ricompilare entrambe le architetture e unirle in un bundle completo,
con un proprio certificato Apple Development e `LocalSigning.xcconfig`:

```sh
python3 scripts/build-universal-app.py --configuration Debug --jobs 6
python3 scripts/prepare-source-package.py --arch universal2
python3 scripts/check-publication.py --release --arch universal2
```

Questa procedura richiede che il Mac possa eseguire i test ARM64 e x86_64
(Apple Silicon con Rosetta). Entrambi i prefissi vengono compilati da sorgente;
non vengono riutilizzati i vecchi binari Intel upstream. Per ricollegare
l'app con modifiche a librerie LGPL preparare il prefisso modificato per
ciascuna architettura, quindi usare `--prepared-dependencies`. Il risultato
è `dist/universal2/CIE ID.app`; nei checkout iCloud è un collegamento alla
copia reale in `~/Developer/Builds/CIE-ID/universal2/CIE ID.app`.
Il manifest identifica anche i comandi delle due build separate.
I permessi di firma vengono preservati e la firma finale è applicata dopo
`lipo`, includendo estensione e middleware. Le istruzioni seguenti per
librerie LGPL valgono per entrambi i prefissi `arm64` e `x86_64`.

## Modificare una libreria LGPL

È permessa la modifica per uso personale e il reverse engineering
necessario al debugging di modifiche alle librerie LGPL, secondo le licenze
incluse. Nessuna condizione aggiuntiva di questa distribuzione vieta tali
attività. Tutti i sorgenti dell'opera che usa queste librerie sono disponibili.

Per una modifica locale, ricostruire la dipendenza in una directory separata
dai sorgenti forniti, installandola nel prefisso nativo
`.build/dependencies/arm64/prefix` con gli stessi header e nomi di archivi.
Le opzioni di configurazione sono in `scripts/build-dependencies.py`.
Ad esempio PoDoFo deve mantenere i propri header sotto `include/podofo` e
gli archivi statici `lib/libpodofo.a`, `lib/libpodofo_private.a`, `lib/libpodofo_3rdparty.a`; libiconv `lib/libiconv.a` e `lib/libcharset.a`.
Le utility UUC LGPL del progetto sono modificate direttamente nei sorgenti.

Ricompilare l'opera utilizzatrice con il prefisso modificato:

```sh
python3 scripts/build-native-app.py --arch arm64 --prepared-dependencies --clean
```

`--prepared-dependencies` evita che il builder ripristini le librerie originali.
CMake/Xcode ricollegano con gli archivi del prefisso; l'app esportata incorpora
il middleware appena prodotto. La build può fallire se la modifica cambia
le API: i sorgenti dell'opera utilizzatrice sono inclusi per adattarli.

I checksum dei lockfile identificano la distribuzione originale, non vietano
modifiche locali. Per redistribuire una variante cambiare lockfile e audit
con versioni, sorgenti e avvisi corrispondenti alla variante; non usare il
manifest originale per attestare una build diversa.

## Firma e nuovi materiali

Una build unsigned permette compilazione e test software. L'attivazione
CryptoTokenKit richiede identificativi, App Group e firma/provisioning
appropriati: copiare `LocalSigning.xcconfig.example` in
`LocalSigning.xcconfig`, impostare team e bundle ID, quindi usare
`--sign-development --configuration Debug`. Il gruppo macOS con prefisso
del team non richiede un profilo. Non sono necessari né forniti i certificati
privati del distributore originale. Il file locale non entra nei pacchetti
sorgente; i valori effettivi (team, bundle ID, gruppo e configurazione) sono
registrati nei metadati di build. Per ricreare quella variante, riportare
i valori `identity_settings` in un nuovo `LocalSigning.xcconfig`, poi usare
un proprio certificato. La firma crittografica non sarà identica.

Dopo una build verificata, prima di distribuire:

```sh
python3 scripts/prepare-source-package.py --arch arm64
python3 scripts/check-publication.py --release --arch arm64
```

Il pacchetto deve essere pubblicato insieme al bundle cui si riferisce.
Dopo modifiche ai sorgenti o firma del bundle, ripetere build e preparazione:
i controlli rifiutano materiali non corrispondenti. Non distribuire il
binario separato `TestCIE` con il pacchetto dell'app: ha GPL e resta una
utility di test, non un componente incorporato nel bundle.

## Riprodurre la variante Developer ID

Usare lo stesso comando Universal con `--configuration Release`,
`--sign-developer-id`, un proprio `--team`, `--bundle-id` e certificato
`--signing-identity`. Questi parametri sono registrati nelle ricevute senza
password o chiavi. I prodotti sono separati sotto `dist/release`.
La firma include hardened runtime e timestamp; gli entitlements Debug sono
rifiutati. Lo script `notarize-release.py --profile NOME_PROFILO` invia il
bundle ad Apple, prosegue le richieste pendenti e confeziona i materiali
solo dopo l'approvazione e la verifica del ticket.

Per rigenerare separatamente il pacchetto dei sorgenti di questa variante:

```sh
python3 scripts/prepare-source-package.py --arch universal2 --variant release
python3 scripts/check-publication.py --release --arch universal2 --variant release
```

La notarizzazione applica un ticket al bundle; il builder di distribuzione
aggiorna la ricevuta prima di creare i sorgenti corrispondenti. I controlli
continuano a rifiutare qualsiasi modifica non registrata dopo la build.

## DMG di distribuzione

Installare il modulo Python `ds_store` (versione verificata 1.3.1) in un
ambiente locale. Dopo la notarizzazione dell'app, usare `scripts/package-dmg.py`
con `preview`, aprire il volume e verificarne la finestra; poi `prepare`,
`submit` e `finalize`, indicando il proprio certificato e profilo notarytool.
Il layout contiene una finestra 640 × 420 punti, due icone e il collegamento
`Applicazioni -> /Applications`. Lo script rifiuta la sovrascrittura di un DMG
esistente e verifica il bundle dopo montaggio e copia.
