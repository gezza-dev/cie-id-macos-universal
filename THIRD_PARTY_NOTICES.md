# Avvisi e attribuzioni di terze parti

Fork indipendente di `italia/cie-middleware-macos`, basato sul commit
`43da456fb3002e34beccda73b9bc4b149acae534`. Non è un prodotto ufficiale,
approvato o supportato da IPZS. Verifica effettuata il 14 ottobre 2026.

Questa raccolta accompagna i sorgenti e le build di lavoro. La presenza di
un avviso non risolve una licenza mancante né autorizza una combinazione di
licenze incompatibili. Le condizioni sono descritte in
[LICENSE_AUDIT.md](LICENSE_AUDIT.md).

## Progetto originale e codice incorporato

Copyright (c) 2017, Istituto Poligrafico e Zecca dello Stato.
All rights reserved. Licenza principale:
[BSD 3-Clause](LICENSES/upstream/LICENSE.txt).
I copyright individuali e gli avvisi nei file originali restano applicabili.

| Componente | Licenza o evidenza | Testo incluso |
| --- | --- | --- |
| Logger rxi / log.c | MIT, copyright (c) 2020 rxi | [LICENSE](LICENSES/rxi-log/LICENSE) |
| Utility UUC nel middleware e nell'SDK | LGPL 2.0 o successiva nei file che lo dichiarano | [LGPL](LICENSES/gnu/COPYING.LIB); avvisi nei sorgenti |
| TestCIE, utility di test separata esclusa dal bundle dell'app | GPL 2.0 o successiva | [GPL](LICENSES/gnu/COPYING); avvisi nei sorgenti |
| Adattatori hash/RSA, reader ed eccezioni ASN.1 e tabella proprietà del fork | BSD 3-Clause | SPDX nei nuovi sorgenti; [BSD](LICENSE.txt) |
| Base64 di Philip Busch | BSD 2-Clause, copyright (c) 2006–2007 Philip Busch | [Avviso originale](LICENSES/embedded-sdk/base64-notice.txt) |
| RC2 di Kungliga Tekniska Högskolan | BSD 3-Clause, copyright (c) 2004 KTH | [Avviso originale](LICENSES/embedded-sdk/rc2.c-notice.txt) |
| Header PKCS#11 | Permesso specifico di copia, uso e derivazione | [Avviso originale](LICENSES/embedded-sdk/pkcs11-notice.txt) |
| C++ Big Integer Library di Matt McCutchen | Dominio pubblico dichiarato dall'autore; copia incorporata con adattamenti | [README upstream](LICENSES/bigint/README.txt) |

L'inventario dei file con dichiarazioni esplicite è in
`scripts/embedded-license-inventory.json`. Non assegna la licenza BSD ai file
che dichiarano altri termini e non costituisce una ricostruzione completa
della titolarità di tutti i file.

## Dipendenze della build nativa

I sorgenti sono identificati da URL, versione e SHA-256 nei lockfile
`scripts/dependencies.lock.json` e `scripts/app-dependencies.lock.json`.
I testi qui inclusi provengono dagli archivi con quei checksum.

| Dipendenza | Versione | Licenza e testi |
| --- | --- | --- |
| OpenSSL | 3.5.9 LTS | [Apache License 2.0](LICENSES/openssl/LICENSE.txt), [autori e titolari](LICENSES/openssl/AUTHORS.md) |
| Crypto++ | 8.2.0 | [File in dominio pubblico, compilazione Boost 1.0 e avvisi CRYPTOGAMS](LICENSES/cryptopp/License.txt) |
| PoDoFo | 0.9.8, commit `67b5b8272b76700e0bb756aa0b45300cfc576100` | [LGPL 2.0 o successiva](LICENSES/podofo/COPYING.LIB), [GPL per le parti che la dichiarano](LICENSES/podofo/COPYING), [eccezione OpenSSL per le parti coperte](LICENSES/podofo/COPYING.exception) |
| zlib | 1.3.1 | [zlib](LICENSES/zlib/LICENSE) |
| bzip2 | 1.0.8 | [Termini bzip2](LICENSES/bzip2/LICENSE) |
| GNU libiconv e libcharset | 1.17 | [LGPL 2.1 o successiva](LICENSES/libiconv/COPYING.LIB), [libcharset](LICENSES/libiconv/libcharset--COPYING.LIB) |
| Expat | 2.6.4 | [MIT](LICENSES/expat/expat--COPYING) |
| libpng | 1.6.47 | [PNG Reference Library License e avvisi storici](LICENSES/libpng/LICENSE) |
| FreeType | 2.13.3 | [FTL scelta per questa build](LICENSES/freetype/LICENSE.TXT), [FTL](LICENSES/freetype/docs--FTL.TXT), [GPL](LICENSES/freetype/docs--GPLv2.TXT); avvisi BDF/PCF/hash nella stessa cartella |
| fontconfig | 2.15.0 | [Termini permissivi e avvisi per i sottocomponenti](LICENSES/fontconfig/COPYING) |
| Tabelle Unicode di fontconfig | CaseFolding 15.1.0 | [Avviso della copia 2023](LICENSES/unicode/CaseFolding-15.1.0-notice.txt), [Unicode License V3 pubblicata dal titolare](LICENSES/unicode/Unicode-LICENSE-V3.txt) |
| libxml2 | 2.9.14 | [MIT e avvisi di file con copyright distinti](LICENSES/libxml2/COPYING); avvisi hash/list/trio nella stessa cartella |
| curl | 8.12.1 | [curl license](LICENSES/libcurl/COPYING) |
| SSZipArchive | 2.5.5 | [MIT](LICENSES/ssziparchive/LICENSE.txt) |
| minizip incorporato in SSZipArchive | Copia del tag SSZipArchive 2.5.5 | [zlib](LICENSES/ssziparchive/SSZipArchive--minizip--LICENSE), [copyright dei contributori](LICENSES/ssziparchive/minizip-copyrights.txt) |

Crypto++ 7.0 nei vecchi header conservati del middleware non è un input
della build nativa. Gli header storici dell'SDK dichiarano invece 8.2.0 e
sono coperti dal testo della medesima versione incluso sopra.
Il suo [testo di licenza separato](LICENSES/cryptopp-legacy-7.0/License.txt)
è incluso per la redistribuzione di quei sorgenti. I vecchi archivi Intel e
gli output CMake upstream inutilizzati sono esclusi dallo snapshot corrente;
la pulizia non riscrive la cronologia Git.

## Attribuzioni OpenSSL e FreeType

OpenSSL 3.5.9 usa Apache License 2.0. Il testo integrale e l'elenco di autori
per i copyright sono inclusi; l'archivio ufficiale non contiene un file
NOTICE alla radice. Non sono state riscritte le sue intestazioni.
Gli header vendored OpenSSL 1.x inutilizzati sono rimossi dallo snapshot;
non sono input della build né componenti dell'app nuova.

> Portions of this software are copyright © 1996–2024 The FreeType Project
> (www.freetype.org). All rights reserved.

Per questa build si sceglie FreeType License (FTL). Il testo dell'alternativa
GPL resta incluso per completezza della distribuzione upstream, senza
applicarlo alla build del fork. Vedere `LICENSES/freetype/LICENSE.TXT`.

## Font e risorse

Il font incorporato è Allura-Regular, versione 1.005:

Copyright (c) 2011 TypeSETit, LLC (typesetit@att.net),
with Reserved Font Name "Allura".

Autore: Robert E. Leuschke. Il font dichiara nei propri metadati la
[SIL Open Font License 1.1](LICENSES/allura/OFL-1.1.txt).
L'[avviso della copia effettiva](LICENSES/allura/COPYRIGHT.txt) è conservato;
il font non è stato modificato dal fork. Non vendere il font da solo; per
modifiche al font rispettare le condizioni sul Reserved Font Name.

Le risorse grafiche e i nomi CIE/IPZS conservati dall'upstream sono
attribuzioni storiche. Non devono essere presentati come approvazione del
fork. L'audit non attesta una concessione generale dei diritti sui marchi.

## Redistribuzione

Conservare questi avvisi e tutti i testi in `LICENSES/` insieme ai sorgenti.
La build Xcode include entrambi nelle risorse di app ed estensione prima
della firma. Le copie finali in `dist/` mantengono i medesimi avvisi.

Per componenti GPL/LGPL, i testi di licenza non sostituiscono gli obblighi
di fornire i sorgenti corrispondenti, le modifiche e, quando richiesto, ciò
che permette la ricompilazione o il ricollegamento. Per i dettagli e i punti
di distribuzione consultare `LICENSE_AUDIT.md` e `Docs/PUBLICATION.md`.
