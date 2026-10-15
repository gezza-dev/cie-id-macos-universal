cmake_minimum_required(VERSION 3.23)

project(cie_sign_sdk LANGUAGES C CXX)

if(NOT APPLE)
    message(FATAL_ERROR "This build entry point targets macOS")
endif()

set(CIE_DEPENDENCY_PREFIX "" CACHE PATH "Prefix produced by scripts/build-dependencies.py")
if(NOT CIE_DEPENDENCY_PREFIX)
    message(FATAL_ERROR "Set CIE_DEPENDENCY_PREFIX to the native dependency prefix; see README.md")
endif()

set(CMAKE_CXX_STANDARD 17)

set(DEPENDENCIES_DIR "${CIE_DEPENDENCY_PREFIX}")
set(SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/include)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
add_link_options("LINKER:-adhoc_codesign")

set(SRC_LIST
    ${SOURCE_DIR}/Native/RsaRecovery.cpp
    ${SOURCE_DIR}/Native/HttpClient.cpp
    ${SOURCE_DIR}/Native/Revocation.cpp
    ${SOURCE_DIR}/Base64.cpp
    ${SOURCE_DIR}/BigInteger.cpp
    ${SOURCE_DIR}/BigIntegerAlgorithms.cpp
    ${SOURCE_DIR}/BigIntegerUtils.cpp
    ${SOURCE_DIR}/BigUnsigned.cpp
    ${SOURCE_DIR}/BigUnsignedInABase.cpp
    ${SOURCE_DIR}/CIESigner.cpp
    ${SOURCE_DIR}/CiePdfSignatureField.cpp
    ${SOURCE_DIR}/CIEEngine.c
    ${SOURCE_DIR}/CIEEngineHelper.c
    ${SOURCE_DIR}/CertStore.cpp
    ${SOURCE_DIR}/CounterSignatureGenerator.cpp
    ${SOURCE_DIR}/SignatureGenerator.cpp
    ${SOURCE_DIR}/LdapCrl.cpp
    ${SOURCE_DIR}/M7MParser.cpp
    ${SOURCE_DIR}/PdfSignatureGenerator.cpp
    ${SOURCE_DIR}/PdfVerifier.cpp
    ${SOURCE_DIR}/SignedDataGeneratorEx.cpp
    ${SOURCE_DIR}/SignedDocument.cpp
    ${SOURCE_DIR}/SignerInfoGenerator.cpp
    ${SOURCE_DIR}/TSAClient.cpp
    ${SOURCE_DIR}/UUCLogger.cpp
    ${SOURCE_DIR}/UUCStringTable.cpp
    ${SOURCE_DIR}/UUCTextFileReader.cpp
    ${SOURCE_DIR}/UUCTextFileWriter.cpp
    ${SOURCE_DIR}/XAdESGenerator.cpp
    ${SOURCE_DIR}/XAdESVerifier.cpp
    ${SOURCE_DIR}/definitions.cpp
    ${SOURCE_DIR}/disigonsdk.cpp
    ${SOURCE_DIR}/ASN1/ASN1BitString.cpp
    ${SOURCE_DIR}/ASN1/ASN1Boolean.cpp
    ${SOURCE_DIR}/ASN1/ASN1GenericSequence.cpp
    ${SOURCE_DIR}/ASN1/ASN1Integer.cpp
    ${SOURCE_DIR}/ASN1/ASN1Null.cpp
    ${SOURCE_DIR}/ASN1/ASN1Object.cpp
    ${SOURCE_DIR}/ASN1/ASN1ObjectIdentifier.cpp
    ${SOURCE_DIR}/ASN1/ASN1Octetstring.cpp
    ${SOURCE_DIR}/ASN1/ASN1OptionalField.cpp
    ${SOURCE_DIR}/ASN1/ASN1Sequence.cpp
    ${SOURCE_DIR}/ASN1/ASN1Setof.cpp
    ${SOURCE_DIR}/ASN1/ASN1UTCTime.cpp
    ${SOURCE_DIR}/ASN1/AlgorithmIdentifier.cpp
    ${SOURCE_DIR}/ASN1/Certificate.cpp
    ${SOURCE_DIR}/ASN1/CertificateInfo.cpp
    ${SOURCE_DIR}/ASN1/ContentInfo.cpp
    ${SOURCE_DIR}/ASN1/ContentType.cpp
    ${SOURCE_DIR}/ASN1/Crl.cpp
    ${SOURCE_DIR}/ASN1/DigestInfo.cpp
    ${SOURCE_DIR}/ASN1/IssuerAndSerialNumber.cpp
    ${SOURCE_DIR}/ASN1/Name.cpp
    ${SOURCE_DIR}/ASN1/OCSPRequest.cpp
    ${SOURCE_DIR}/ASN1/PKIStatusInfo.cpp
    ${SOURCE_DIR}/ASN1/RSAPrivateKey.cpp
    ${SOURCE_DIR}/ASN1/RSAPublicKey.cpp
    ${SOURCE_DIR}/ASN1/RelativeDistinguishedName.cpp
    ${SOURCE_DIR}/ASN1/SignedData.cpp
    ${SOURCE_DIR}/ASN1/SignerInfo.cpp
    ${SOURCE_DIR}/ASN1/SubjectPublicKeyInfo.cpp
    ${SOURCE_DIR}/ASN1/TSTInfo.cpp
    ${SOURCE_DIR}/ASN1/TimeStampData.cpp
    ${SOURCE_DIR}/ASN1/TimeStampRequest.cpp
    ${SOURCE_DIR}/ASN1/TimeStampResponse.cpp
    ${SOURCE_DIR}/ASN1/TimeStampToken.cpp
    ${SOURCE_DIR}/ASN1/ByteReader.cpp
    ${SOURCE_DIR}/RSA/rc2.c
    ${SOURCE_DIR}/RSA/rc2.h
    ${SOURCE_DIR}/CSP/IAS.cpp
    ${SOURCE_DIR}/CSP/ATR.cpp
    ${SOURCE_DIR}/CSP/ExtAuthKey.cpp
    ${SOURCE_DIR}/PCSC/APDU.cpp
    ${SOURCE_DIR}/PCSC/CardLocker.cpp
    ${SOURCE_DIR}/PCSC/PCSC.cpp
    ${SOURCE_DIR}/PCSC/Token.cpp
    ${SOURCE_DIR}/Util/Array.cpp
    ${SOURCE_DIR}/Util/CacheLib.cpp
    ${SOURCE_DIR}/Util/CryptoppUtils.cpp
    ${SOURCE_DIR}/Util/funccallinfo.cpp
    ${SOURCE_DIR}/Util/IniSettings.cpp
    ${SOURCE_DIR}/Util/log.cpp
    ${SOURCE_DIR}/Util/ModuleInfo.cpp
    ${SOURCE_DIR}/Util/TLV.cpp
    ${SOURCE_DIR}/Util/util.cpp
    ${SOURCE_DIR}/Util/UtilException.cpp
    ${SOURCE_DIR}/Util/UUCByteArray.cpp
    ${SOURCE_DIR}/Util/UUCProperties.cpp
    ${SOURCE_DIR}/Util/UUCTextFileReader.cpp
    ${SOURCE_DIR}/Util/SyncroMutex.cpp
    ${SOURCE_DIR}/Crypto/AES.cpp
    ${SOURCE_DIR}/Crypto/ASNParser.cpp
    ${SOURCE_DIR}/Crypto/Base64.cpp
    ${SOURCE_DIR}/Crypto/DES3.cpp
    ${SOURCE_DIR}/Crypto/MAC.cpp
    ${SOURCE_DIR}/Crypto/MD5.cpp
    ${SOURCE_DIR}/Crypto/RSA.cpp
    ${SOURCE_DIR}/Crypto/SHA1.cpp
    ${SOURCE_DIR}/Crypto/SHA256.cpp
    ${SOURCE_DIR}/Crypto/SHA512.cpp
    )

add_library(${PROJECT_NAME} STATIC ${SRC_LIST})

set(INCLUDE_LIST
    ${INCLUDE_DIR}
    ${SOURCE_DIR}/ASN1
    ${SOURCE_DIR}
    ${SOURCE_DIR}/RSA
    ${SOURCE_DIR}/PCSC
    ${SOURCE_DIR}/CSP
    ${SOURCE_DIR}/Util
    ${SOURCE_DIR}/Crypto
    ${DEPENDENCIES_DIR}/include/freetype2
    ${DEPENDENCIES_DIR}/include/libxml2
    ${DEPENDENCIES_DIR}/include/podofo
 )

target_include_directories(${PROJECT_NAME} BEFORE PUBLIC "${DEPENDENCIES_DIR}/include")
target_include_directories(${PROJECT_NAME} PRIVATE ${INCLUDE_LIST})
target_include_directories(${PROJECT_NAME} PUBLIC
    $<BUILD_INTERFACE:${INCLUDE_DIR}>
    $<BUILD_INTERFACE:${DEPENDENCIES_DIR}/include>
    $<BUILD_INTERFACE:${DEPENDENCIES_DIR}/include/freetype2>
    $<BUILD_INTERFACE:${DEPENDENCIES_DIR}/include/libxml2>)
target_compile_definitions(${PROJECT_NAME} PUBLIC CIE_USE_UPSTREAM_PODOFO=1 CRYPTOPP_DISABLE_ASM=1 PODOFO_STATIC=1)

# Explicit archive paths keep Intel vendored binaries and Homebrew dylibs out.
set(CIE_STATIC_DEPENDENCIES podofo podofo_private podofo_3rdparty curl ssl crypto cryptopp fontconfig freetype
    png16 xml2 expat iconv charset bz2 z)
foreach(dependency IN LISTS CIE_STATIC_DEPENDENCIES)
    set(archive "${DEPENDENCIES_DIR}/lib/lib${dependency}.a")
    if(NOT EXISTS "${archive}")
        message(FATAL_ERROR "Missing ${archive}; run scripts/build-dependencies.py first")
    endif()
    execute_process(COMMAND lipo -archs "${archive}"
        RESULT_VARIABLE result OUTPUT_VARIABLE architectures OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(NOT result EQUAL 0)
        message(FATAL_ERROR "Cannot inspect ${archive}")
    endif()
    string(REPLACE " " ";" architectures "${architectures}")
    if(CMAKE_OSX_ARCHITECTURES)
        set(required_architectures ${CMAKE_OSX_ARCHITECTURES})
    else()
        set(required_architectures ${CMAKE_SYSTEM_PROCESSOR})
    endif()
    foreach(architecture IN LISTS required_architectures)
        if(NOT architecture IN_LIST architectures)
            message(FATAL_ERROR "${archive} does not contain ${architecture}")
        endif()
    endforeach()
    target_link_libraries(${PROJECT_NAME} PUBLIC "${archive}")
endforeach()
find_library(PCSC_FRAMEWORK PCSC REQUIRED)
find_library(COREFOUNDATION_FRAMEWORK CoreFoundation REQUIRED)
find_library(SECURITY_FRAMEWORK Security REQUIRED)
find_library(SYSTEMCONFIGURATION_FRAMEWORK SystemConfiguration REQUIRED)
target_link_libraries(${PROJECT_NAME} PUBLIC ${PCSC_FRAMEWORK}
    ${COREFOUNDATION_FRAMEWORK} ${SECURITY_FRAMEWORK} ${SYSTEMCONFIGURATION_FRAMEWORK} ldap lber)

include(GNUInstallDirs)
install(TARGETS ${PROJECT_NAME} ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES ${INCLUDE_DIR}/disigonsdk.h ${INCLUDE_DIR}/CIEEngine.h
    ${INCLUDE_DIR}/definitions.h DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/cie_sign_sdk)

# Preserve licence texts with standalone SDK installations as well.
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../LICENSES"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/cie-sign-sdk")
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/../LICENSE.txt"
    "${CMAKE_CURRENT_SOURCE_DIR}/../THIRD_PARTY_NOTICES.md"
    "${CMAKE_CURRENT_SOURCE_DIR}/../LICENSE_AUDIT.md"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/cie-sign-sdk")

option(CIE_BUILD_TESTS "Build SDK integration tests without a physical CIE" ON)
if(CIE_BUILD_TESTS)
    enable_testing()
    add_executable(cie_security_tests tests/security_tests.cpp tests/middleware_stubs.cpp)
    target_include_directories(cie_security_tests PRIVATE ${SOURCE_DIR} ${SOURCE_DIR}/Util ${SOURCE_DIR}/ASN1)
    target_link_libraries(cie_security_tests PRIVATE ${PROJECT_NAME})
    add_test(NAME cie_security_tests COMMAND cie_security_tests)
    add_executable(cie_sdk_tests tests/sdk_tests.cpp tests/middleware_stubs.cpp)
    target_include_directories(cie_sdk_tests PRIVATE ${SOURCE_DIR} ${SOURCE_DIR}/Util ${SOURCE_DIR}/ASN1)
    target_link_libraries(cie_sdk_tests PRIVATE ${PROJECT_NAME})
    add_test(NAME cie_sdk_tests COMMAND cie_sdk_tests "${CMAKE_CURRENT_BINARY_DIR}/verification-fixtures")
    set_tests_properties(cie_sdk_tests PROPERTIES FIXTURES_SETUP CIEVerificationFixtures)
endif()
