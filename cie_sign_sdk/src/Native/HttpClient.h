// SPDX-License-Identifier: BSD-3-Clause
#pragma once
#include <curl/curl.h>
#include <cstdint>
#include <string>
#include <vector>

namespace cie {
struct HttpOptions {
    std::string proxy;
    int proxyPort = 0;
    std::string proxyCredentials;
    std::string username;
    std::string password;
};
struct HttpResponse {
    int error = CURLE_FAILED_INIT;
    long status = 0;
    std::vector<unsigned char> body;
};
// HTTP is needed by signed OCSP/CRL protocols. HTTPS always authenticates
// the peer and hostname using macOS trust; redirects cannot downgrade TLS.
HttpResponse httpRequest(const std::string& url, const std::vector<unsigned char>& body,
                         const char* contentType, const HttpOptions& options,
                         size_t maximumBytes = 32 * 1024 * 1024);
}
