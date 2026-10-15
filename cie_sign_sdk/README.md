# SDK di firma nativo per macOS

La nuova build compila dai sorgenti le dipendenze statiche per Apple Silicon.
Gli archivi Intel storici inutilizzati sono esclusi dallo snapshot del fork;
la loro rimozione non riscrive la cronologia Git.

Il progetto è un fork indipendente dell'upstream IPZS. Per licenze, avvisi
e punti aperti sulla pubblicazione consultare
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) e
[LICENSE_AUDIT.md](../LICENSE_AUDIT.md). La build locale non è una verifica
della compatibilità delle licenze per distribuire il binario.

## Build ARM

Servono macOS su Apple Silicon, Command Line Tools di Xcode (o Xcode completo),
Python 3.9+, CMake 3.23+, make, Perl e pkg-config. La prima esecuzione richiede
Internet e può durare diversi minuti. Dalla radice del repository:

```sh
python3 scripts/build-native-sdk.py --arch arm64 --jobs 6
```

Lo script scarica i sorgenti fissati in
[`dependencies.lock.json`](../scripts/dependencies.lock.json), verifica i
checksum SHA-256, compila le dipendenze e il SDK, esegue i test e installa gli
artefatti localmente. Non installa software nelle cartelle di sistema.

| Artefatto | Percorso |
| --- | --- |
| Dipendenze, header e manifest | `.build/dependencies/arm64/prefix` |
| Log delle dipendenze | `.build/dependencies/arm64/logs` |
| SDK | `.build/sign-sdk/arm64/install/lib/libcie_sign_sdk.a` |
| Header pubblici | `.build/sign-sdk/arm64/install/include/cie_sign_sdk` |
| Test | `.build/sign-sdk/arm64/cie_sdk_tests` |

Queste cartelle sono escluse da Git. Gli archivi e l'eseguibile di test devono
contenere `arm64`. L'eseguibile deve importare solo librerie e framework di
macOS: lo script rifiuta dipendenze dinamiche da Homebrew o dalla build.

## Fasi separate

```sh
python3 scripts/build-dependencies.py --arch arm64 --jobs 6
cmake -S cie_sign_sdk -B .build/sign-sdk/arm64 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=12.0 \
  -DCIE_DEPENDENCY_PREFIX="$PWD/.build/dependencies/arm64/prefix" \
  -DCMAKE_INSTALL_PREFIX="$PWD/.build/sign-sdk/arm64/install"
cmake --build .build/sign-sdk/arm64 --parallel 6
ctest --test-dir .build/sign-sdk/arm64 --output-on-failure
cmake --install .build/sign-sdk/arm64
```

Si usa sempre una build fuori dai sorgenti. Le cache e gli oggetti CMake
storici presenti nel repository non sono input della nuova build.

La cache delle dipendenze viene invalidata quando cambiano ricette, checksum,
architettura, deployment target, compilatore o versione dell'SDK macOS.
Per ricompilare una singola dipendenza, con i suoi prerequisiti già costruiti:

```sh
python3 scripts/build-dependencies.py --arch arm64 --only podofo --force
```

## Versioni e compatibilità

Le versioni fissate sono OpenSSL 1.1.1w, Crypto++ 8.2.0, PoDoFo 0.9.8 (commit
`67b5b8272b76700e0bb756aa0b45300cfc576100`), zlib 1.3.1, bzip2 1.0.8,
libiconv 1.17, expat 2.6.4, libpng 1.6.47, FreeType 2.13.3, fontconfig 2.15.0,
libxml2 2.9.14 e curl 8.12.1.

Questa è una fase di porting, non una configurazione pronta per un rilascio.
OpenSSL 1.1.1w è mantenuto temporaneamente per compatibilità con le API ENGINE.
[OpenSSL 1.1.1 è fuori supporto](https://openssl-library.org/post/2023-09-11-eol-111/):
l'aggiornamento a una versione supportata e la revisione delle altre versioni
legacy restano necessari prima della distribuzione. Crypto++ è compilato
nella modalità C++ portabile, con assembly disabilitato anche nel chiamante.

PoDoFo viene compilato dal progetto pubblico. Il vecchio archivio Intel
conteneva estensioni private senza sorgenti. `CiePdfSignatureField` adatta
metadati, SubFilter, spazio CMS e aspetto grafico con PNG e testo alle API
pubbliche. La grafica non è garantita identica al vecchio fork. Nei PDF già
firmati si usano `LoadFromBuffer(..., true)` e `WriteUpdate` per preservare i
byte precedenti.

La codifica grafometrica privata non è ricostruibile dai soli header: le
richieste con dati grafometrici vengono rifiutate esplicitamente. I normali
flussi di firma CIE dell'app passano dati grafometrici nulli.

## Test senza carta

I test generano chiavi e certificati temporanei e verificano:

- chiave pubblica dell'engine e comportamento senza certificato;
- vettore noto SHA-256 attraverso Crypto++ nativo;
- inserimento di un PNG trasparente nell'aspetto della firma;
- firma CMS del PDF e verifica crittografica dei ByteRange;
- seconda firma incrementale, con byte precedenti identici ed entrambe le
  firme CMS verificabili.

Queste prove non certificano il flusso FEA con carta fisica. Usano CMS software
con `adbe.pkcs7.detached`, senza verifica di una catena pubblica di certificati.
I simboli di cache, registrazione e SOD forniti dal middleware sono sostituiti
solo nei test da stub che generano un errore se invocati. Gli stub non sono
inclusi nella libreria SDK.

## Integrazione con l'app

Il SDK statico non incorpora le altre librerie: il consumatore deve collegare
anche le dipendenze e i framework indicati dal target CMake `cie_sign_sdk`.

Middleware, estensione CryptoTokenKit e target Xcode usano ora la stessa
configurazione nativa e gli header Crypto++ 8.2.0. Lo script
`scripts/build-native-app.py` prepara le dipendenze e compila il bundle
completo senza CocoaPods. Il target CMake del middleware collega i veri
simboli di registrazione, cache e SOD; gli stub restano confinati ai test del
SDK. Restano da provare autenticazione, PIN e firme con carta e lettore.
Per Universal 2 vanno costruite e validate anche le versioni Intel e poi
unite le due architetture.

`--arch x86_64` prepara una build Intel separata: non è validata in questa fase
e richiede un host Intel o Rosetta per i test. Non creare un archivio Universal
2 usando soltanto gli archivi ARM.
