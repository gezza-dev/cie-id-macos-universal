# Correzioni di sicurezza 1.5.1

Questa versione corregge i tre problemi individuati nel controllo della 1.5.0.
Il repository resta privato fino alla decisione del proprietario di pubblicarlo.

## Verifica autenticata delle informazioni di revoca

`cie_sign_sdk/src/Native/Revocation.cpp` sostituisce l'interpretazione manuale
delle risposte OCSP e la semplice ricerca del seriale nelle CRL.

- L'emittente deve essere una CA che ha firmato il certificato del documento.
  I certificati CMS, dello store e scaricati da AIA sono candidati non fidati.
- Le risposte OCSP devono avere firma valida, risponditore autorizzato,
  CertID corrispondente, nonce compatibile e tempi validi. È ammessa l'assenza
  del nonce per i risponditori che usano risposte preprodotte.
- Le CRL devono essere firmate dall'emittente autorizzato, correnti e complete.
  Delta CRL e CRL con ambito parziale non implementato non producono un esito
  «non revocato». Non vengono usate risposte scadute per attestare uno stato
  storico basandosi sulla data dichiarata nel documento.
- Errori di rete, dati alterati o informazioni insufficienti restituiscono
  **stato di revoca sconosciuto**, senza convertirlo in «certificato valido».

Questa verifica attesta lo stato di revoca rispetto all'emittente del
certificato. Non implementa una validazione qualificata eIDAS, una lista di
fiducia europea, né una validazione LTV con prova temporale attendibile.

## TLS dei servizi remoti

`cie_sign_sdk/src/Native/HttpClient.cpp` è condiviso dalle richieste AIA,
OCSP, CRL e TSA. Verifica catena TLS e nome del server, con Apple SecTrust e
il trust store di macOS; richiede almeno TLS 1.2. Non permette downgrade
HTTPS → HTTP, protocolli diversi da HTTP(S), credenziali nell'URL o invio di
credenziali TSA su HTTP. Numero di redirect, dimensioni e tempi sono limitati.
Le risposte OCSP/CRL distribuite su HTTP richiedono comunque firma verificata.

## Dipendenze aggiornate e compatibilità PDF

Versioni e SHA-256 sono fissati nei due lockfile sotto `scripts/`.
OpenSSL resta alla 3.5.9 LTS; sono aggiornati Crypto++, PoDoFo, zlib, Expat,
libpng, FreeType, fontconfig, libiconv, libxml2, curl e SSZipArchive.
PoDoFo passa alla 1.1.2 LTS e richiede C++17: firma PDF differita, salvataggio
incrementale e controllo dei ByteRange. Le dipendenze sono compilate da
sorgente per ARM64 e Intel; il bundle Universal incorpora entrambe.

## Test ripetibili

```sh
ctest --test-dir .build/native/arm64 --output-on-failure
ctest --test-dir .build/native/x86_64 --output-on-failure
python3 scripts/test-http-security.py .build/native/arm64/cie_sign_sdk/cie_security_tests
python3 scripts/test-http-security.py .build/native/x86_64/cie_sign_sdk/cie_security_tests
```

I test generano localmente certificati e risposte di prova. Coprono OCSP valido,
revocato e sospeso; delega autorizzata; firme alterate, CertID, emittente, EKU,
nonce e scadenze errati; CRL valide, revocate, false, scadute o delta senza base.
`scripts/test-middleware-ocsp.py LIBRERIA --openssl PERCORSO_OPENSSL` riproduce
il difetto della 1.5.0 contro il middleware reale, richiedendo il rifiuto di
una risposta OCSP priva di firma e CertID valido. Le prove HTTP controllano il rifiuto di TLS autofirmato, URL con credenziali e
protocolli non consentiti. `--trusted-url https://www.apple.com` aggiunge una
prova con il trust store reale, richiedendo accesso Internet. Nessuna CA di
prova viene installata sul Mac.

La suite SDK verifica CMS, firme PDF singole e multiple, alterazione dei
contenuti, aggiornamenti incrementali e lettura dei PDF cifrati. La build
verifica anche il middleware incorporato e le due architetture. Le prove
software non sostituiscono il collaudo con CIE, lettore e documento reale.

Riferimenti: [verifica OCSP OpenSSL](https://docs.openssl.org/3.5/man3/OCSP_resp_find_status/),
[verifica TLS curl](https://curl.se/libcurl/c/CURLOPT_SSL_VERIFYPEER.html),
[certificati e Apple SecTrust](https://curl.se/docs/sslcerts.html).
