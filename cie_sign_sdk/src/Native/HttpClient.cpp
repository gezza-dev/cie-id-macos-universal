// SPDX-License-Identifier: BSD-3-Clause
#include "HttpClient.h"
#include <limits>
#include <memory>
#include <mutex>

namespace cie {
namespace {
struct Buffer { std::vector<unsigned char> bytes; size_t maximum; };
size_t receive(char* data, size_t size, size_t count, void* context)
{
    auto& output = *static_cast<Buffer*>(context);
    if (size && count > std::numeric_limits<size_t>::max() / size) return 0;
    size_t length = size * count;
    if (length > output.maximum - output.bytes.size()) return 0;
    try { output.bytes.insert(output.bytes.end(), data, data + length); }
    catch (...) { return 0; }
    return length;
}
}
HttpResponse httpRequest(const std::string& url, const std::vector<unsigned char>& body,
                         const char* contentType, const HttpOptions& options, size_t maximumBytes)
{
    HttpResponse result;
    static std::once_flag initialized;
    static CURLcode globalStatus = CURLE_FAILED_INIT;
    std::call_once(initialized, [] { globalStatus = curl_global_init(CURL_GLOBAL_DEFAULT); });
    if (globalStatus != CURLE_OK) return result;
    std::unique_ptr<CURL, decltype(&curl_easy_cleanup)> handle(curl_easy_init(), curl_easy_cleanup);
    std::unique_ptr<CURLU, decltype(&curl_url_cleanup)> address(curl_url(), curl_url_cleanup);
    if (!handle || !address || curl_url_set(address.get(), CURLUPART_URL, url.c_str(), 0) != CURLUE_OK) {
        result.error = CURLE_URL_MALFORMAT; return result;
    }
    char* rawScheme = nullptr;
    if (curl_url_get(address.get(), CURLUPART_SCHEME, &rawScheme, 0) != CURLUE_OK) return result;
    std::string scheme(rawScheme); curl_free(rawScheme);
    if (scheme != "http" && scheme != "https") { result.error = CURLE_UNSUPPORTED_PROTOCOL; return result; }
    // Do not transmit timestamp-service credentials over cleartext HTTP.
    if (scheme != "https" && (!options.username.empty() || !options.password.empty())) {
        result.error = CURLE_LOGIN_DENIED; return result;
    }
    char* user = nullptr;
    if (curl_url_get(address.get(), CURLUPART_USER, &user, 0) == CURLUE_OK) {
        curl_free(user); result.error = CURLE_URL_MALFORMAT; return result;
    }
    Buffer output{{}, maximumBytes};
    auto set = [&](CURLoption option, auto value) { return curl_easy_setopt(handle.get(), option, value) == CURLE_OK; };
    if (!set(CURLOPT_URL, url.c_str()) || !set(CURLOPT_SSL_VERIFYPEER, 1L) ||
        !set(CURLOPT_SSL_VERIFYHOST, 2L) || !set(CURLOPT_SSL_OPTIONS, long(CURLSSLOPT_NATIVE_CA)) ||
        !set(CURLOPT_SSLVERSION, long(CURL_SSLVERSION_TLSv1_2)) ||
        !set(CURLOPT_PROTOCOLS_STR, "http,https") ||
        !set(CURLOPT_REDIR_PROTOCOLS_STR, scheme == "https" ? "https" : "http,https") ||
        !set(CURLOPT_FOLLOWLOCATION, 1L) || !set(CURLOPT_MAXREDIRS, 3L) ||
        !set(CURLOPT_CONNECTTIMEOUT_MS, 10000L) || !set(CURLOPT_TIMEOUT_MS, 20000L) ||
        !set(CURLOPT_NOSIGNAL, 1L) || !set(CURLOPT_FAILONERROR, 1L) ||
        !set(CURLOPT_WRITEFUNCTION, receive) || !set(CURLOPT_WRITEDATA, &output)) return result;
    // Empty proxy explicitly means a direct request, not a proxy inherited
    // from environment variables in a calling process.
    if (!set(CURLOPT_PROXY, options.proxy.c_str())) return result;
    if (!options.proxy.empty()) {
        if (options.proxyPort < 1 || options.proxyPort > 65535 ||
            !set(CURLOPT_PROXYTYPE, long(CURLPROXY_HTTP)) ||
            !set(CURLOPT_PROXYPORT, long(options.proxyPort)) ||
            !set(CURLOPT_PROXYUSERPWD, options.proxyCredentials.c_str())) return result;
    }
    if (!options.username.empty() || !options.password.empty()) {
        if (!set(CURLOPT_HTTPAUTH, long(CURLAUTH_BASIC)) || !set(CURLOPT_USERNAME, options.username.c_str()) ||
            !set(CURLOPT_PASSWORD, options.password.c_str())) return result;
    }
    if (!body.empty() && (!set(CURLOPT_POST, 1L) ||
        !set(CURLOPT_POSTFIELDSIZE_LARGE, curl_off_t(body.size())) ||
        !set(CURLOPT_POSTFIELDS, reinterpret_cast<const char*>(body.data())))) return result;
    std::unique_ptr<curl_slist, decltype(&curl_slist_free_all)> headers(nullptr, curl_slist_free_all);
    if (contentType) {
        std::string header = std::string("Content-Type: ") + contentType;
        headers.reset(curl_slist_append(nullptr, header.c_str()));
        if (!headers || !set(CURLOPT_HTTPHEADER, headers.get())) return result;
    }
    result.error = curl_easy_perform(handle.get());
    curl_easy_getinfo(handle.get(), CURLINFO_RESPONSE_CODE, &result.status);
    if (result.error == CURLE_OK && result.status == 200) result.body = std::move(output.bytes);
    else if (result.error == CURLE_OK) result.error = CURLE_HTTP_RETURNED_ERROR;
    return result;
}
}
