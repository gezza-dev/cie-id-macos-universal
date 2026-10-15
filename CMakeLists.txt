cmake_minimum_required(VERSION 3.23)
project(cie_native LANGUAGES C CXX OBJC OBJCXX)

if(NOT APPLE)
    message(FATAL_ERROR "This project targets macOS")
endif()
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_OBJCXX_STANDARD 14)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
enable_testing()
add_subdirectory(cie_sign_sdk)
include(cmake/MiddlewareSources.cmake)
set_source_files_properties(cie-pkcs11/Util/CacheLib.cpp cie-pkcs11/LOGGER/Logger.cpp
    PROPERTIES LANGUAGE OBJCXX)
set(CIE_APP_GROUP_ID "" CACHE STRING "macOS shared container identifier for the signed application")

add_library(cie-pkcs11 SHARED ${CIE_MIDDLEWARE_SOURCES})
target_include_directories(cie-pkcs11 PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/cie-pkcs11/Util"
    "${CMAKE_CURRENT_SOURCE_DIR}/cie-pkcs11/PKCS11"
    "${CMAKE_CURRENT_SOURCE_DIR}/cie-pkcs11/Sign"
    "${CMAKE_CURRENT_SOURCE_DIR}/CIE ID")
target_link_libraries(cie-pkcs11 PRIVATE cie_sign_sdk "-framework Cocoa")
target_compile_definitions(cie-pkcs11 PRIVATE CIE_BUILD_APP_GROUP_ID="${CIE_APP_GROUP_ID}")
target_compile_options(cie-pkcs11 PRIVATE
    "$<$<COMPILE_LANGUAGE:OBJC,OBJCXX>:-fobjc-arc>")
set_target_properties(cie-pkcs11 PROPERTIES
    BUILD_WITH_INSTALL_RPATH ON INSTALL_NAME_DIR "@rpath" MACOSX_RPATH ON)

add_library(CIEToken MODULE CIEToken/CIEToken.mm CIEToken/CIETokenSession.mm
    CIEToken/CIETokenDriver.m cie-pkcs11/LOGGER/Logger.cpp)
target_include_directories(CIEToken PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/CIE ID")
target_compile_definitions(CIEToken PRIVATE CIE_BUILD_APP_GROUP_ID="${CIE_APP_GROUP_ID}")
target_compile_options(CIEToken PRIVATE "$<$<COMPILE_LANGUAGE:OBJC,OBJCXX>:-fobjc-arc>")
target_link_libraries(CIEToken PRIVATE "-framework Cocoa" "-framework CryptoTokenKit"
    "-framework Security")
set_target_properties(CIEToken PROPERTIES PREFIX "" SUFFIX "")

add_executable(cie_middleware_tests tests/middleware_tests.cpp)
target_include_directories(cie_middleware_tests PRIVATE cie-pkcs11/PKCS11)
add_dependencies(cie_middleware_tests cie-pkcs11)
add_test(NAME cie_middleware_tests COMMAND cie_middleware_tests "$<TARGET_FILE:cie-pkcs11>")
add_executable(cie_verification_tests tests/verification_bridge_tests.cpp)
target_include_directories(cie_verification_tests PRIVATE cie-pkcs11/Sign cie-pkcs11/Util)
add_dependencies(cie_verification_tests cie-pkcs11)
add_test(NAME cie_verification_tests COMMAND cie_verification_tests
    "${CMAKE_CURRENT_BINARY_DIR}/cie_sign_sdk/verification-fixtures" "$<TARGET_FILE:cie-pkcs11>")
set_tests_properties(cie_verification_tests PROPERTIES FIXTURES_REQUIRED CIEVerificationFixtures)
install(TARGETS cie-pkcs11 LIBRARY DESTINATION lib)
install(DIRECTORY LICENSES DESTINATION share/cie-native)
install(FILES LICENSE.txt THIRD_PARTY_NOTICES.md LICENSE_AUDIT.md
    DESTINATION share/cie-native)

add_executable(cie_presentation_tests tests/presentation_tests.mm)
target_compile_options(cie_presentation_tests PRIVATE -fobjc-arc)
target_link_libraries(cie_presentation_tests PRIVATE "-framework Cocoa")
add_test(NAME cie_presentation_tests COMMAND cie_presentation_tests)
