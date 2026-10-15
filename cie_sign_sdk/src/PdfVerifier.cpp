/*
 * PdfVerifier.cpp
 * Created by svp on 26/05/12.
 * Copyright 2012 __MyCompanyName__. All rights reserved.
 * Modified for the independent native fork: PoDoFo 1.1 and checked byte ranges.
 */
#include "PdfVerifier.h"
#include "Native/Digest.h"
#include "ASN1/SignedData.h"
#include "ASN1/SignerInfo.h"
#include "SignedDocument.h"
#include "ASN1/Asn1Errors.h"
#include <fstream>
#include <iterator>
#include <limits>
#include <cstring>
#include <stdexcept>
#include <memory>

namespace {
std::vector<const PoDoFo::PdfField*> signatures(const PoDoFo::PdfMemDocument& document)
{
    std::vector<const PoDoFo::PdfField*> result;
    for (const auto* field : document.GetFieldsIterator()) {
        if (field->GetType() != PoDoFo::PdfFieldType::Signature) continue;
        const auto* value = field->GetValueObject();
        if (value && value->IsDictionary() && value->GetDictionary().FindKey("Contents")) result.push_back(field);
    }
    return result;
}
std::string_view contents(const PoDoFo::PdfField& field)
{
    auto* value = field.GetValueObject();
    auto* data = value ? value->GetDictionary().FindKey("Contents") : nullptr;
    if (!data || !data->IsString()) throw std::runtime_error("Missing signature contents");
    return data->GetString().GetRawData();
}
std::vector<unsigned char> signedBytes(const PoDoFo::PdfField& field, const BYTE* bytes, size_t length)
{
    auto* value = field.GetValueObject();
    auto* range = value ? value->GetDictionary().FindKey("ByteRange") : nullptr;
    if (!range || !range->IsArray() || range->GetArray().size() != 4) throw std::runtime_error("Invalid ByteRange");
    size_t offsets[4];
    for (unsigned i = 0; i < 4; ++i) {
        int64_t n = range->GetArray()[i].GetNumber();
        if (n < 0 || uint64_t(n) > length) throw std::runtime_error("ByteRange outside document");
        offsets[i] = size_t(n);
    }
    if (offsets[0] != 0 || offsets[1] == 0 || offsets[2] <= offsets[1] || offsets[3] > length - offsets[2])
        throw std::runtime_error("Overlapping or overflowing ByteRange");
    // A signature gap may contain its hex /Contents and PDF whitespace only.
    // This prevents hiding arbitrary unsigned objects in an enlarged gap.
    if (bytes[offsets[1]] != '<' || bytes[offsets[2] - 1] != '>') throw std::runtime_error("Invalid signature gap");
    for (size_t i = offsets[1] + 1; i + 1 < offsets[2]; ++i) {
        unsigned char c = bytes[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F') ||
              c == ' ' || c == '\r' || c == '\n' || c == '\t' || c == '\f' || c == 0))
            throw std::runtime_error("Unsigned data in signature gap");
    }
    std::vector<unsigned char> output;
    output.reserve(offsets[1] + offsets[3]);
    output.insert(output.end(), bytes, bytes + offsets[1]);
    output.insert(output.end(), bytes + offsets[2], bytes + offsets[2] + offsets[3]);
    return output;
}
}
PDFVerifier::PDFVerifier() : m_pPdfDocument(nullptr), m_actualLen(0), m_szDocBuffer(nullptr) { }
PDFVerifier::~PDFVerifier() { delete m_pPdfDocument; }
int PDFVerifier::Load(const char* data, int length)
{
    delete m_pPdfDocument; m_pPdfDocument = nullptr;
    if (!data || length <= 0 || !cie::initializeOpenSsl()) return -1;
    try {
        auto document = std::make_unique<PoDoFo::PdfMemDocument>();
        document->LoadFromBuffer(PoDoFo::bufferview(data, size_t(length)));
        m_data.removeAll(); m_data.append(reinterpret_cast<const BYTE*>(data), size_t(length));
        m_actualLen = length; m_szDocBuffer = reinterpret_cast<const char*>(m_data.getContent());
        m_pPdfDocument = document.release(); return 0;
    } catch (...) { return -2; }
}
int PDFVerifier::Load(const char* file)
{
    if (!file) return DISIGON_ERROR_INVALID_FILE;
    std::ifstream input(file, std::ios::binary);
    if (!input) return DISIGON_ERROR_FILE_NOT_FOUND;
    std::vector<char> data((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    if (data.size() > size_t(std::numeric_limits<int>::max())) return DISIGON_ERROR_INVALID_FILE;
    return Load(data.data(), int(data.size()));
}
int PDFVerifier::GetNumberOfSignatures(PoDoFo::PdfMemDocument* document)
{
    try { return document ? int(signatures(*document).size()) : -1; } catch (...) { return -1; }
}
int PDFVerifier::GetNumberOfSignatures(const char* file)
{
    PDFVerifier verifier; int result = verifier.Load(file);
    return result ? result : verifier.GetNumberOfSignatures();
}
int PDFVerifier::GetNumberOfSignatures() { return GetNumberOfSignatures(m_pPdfDocument); }
int PDFVerifier::GetSignature(int index, UUCByteArray& output, SignatureAppearanceInfo& appearance)
{
    try {
        if (!m_pPdfDocument || index < 0) return -1;
        auto fields = signatures(*m_pPdfDocument);
        if (size_t(index) >= fields.size()) return -1;
        auto data = contents(*fields[index]);
        output.append(reinterpret_cast<const BYTE*>(data.data()), data.size());
        appearance = {};
        if (auto* widget = fields[index]->GetWidget()) {
            auto rect = widget->GetRect();
            appearance.left = int(rect.X); appearance.bottom = int(rect.Y);
            appearance.width = int(rect.Width); appearance.heigth = int(rect.Height);
        }
        return 0;
    } catch (...) { return -1; }
}
int PDFVerifier::VerifySignature(int index, const char* date, char* type, REVOCATION_INFO* information)
{
    try {
        if (!m_pPdfDocument || index < 0) return -1;
        auto fields = signatures(*m_pPdfDocument);
        if (size_t(index) >= fields.size()) return -1;
        auto& field = *fields[index];
        auto* filter = field.GetValueObject()->GetDictionary().FindKey("SubFilter");
        if (!filter || !filter->IsName()) return -1;
        std::string subFilter(filter->GetName().GetString());
        if (subFilter != "adbe.pkcs7.detached" && subFilter != "ETSI.CAdES.detached" && subFilter != "adbe.pkcs7.sha1") return -5;
        if (type) { std::string name = "/" + subFilter; std::memcpy(type, name.c_str(), name.size() + 1); }
        auto encoded = contents(field);
        CSignedDocument container(reinterpret_cast<const BYTE*>(encoded.data()), encoded.size());
        CSignedData data(container.getSignedData());
        auto bytes = signedBytes(field, reinterpret_cast<const BYTE*>(m_szDocBuffer), size_t(m_actualLen));
        if (subFilter == "adbe.pkcs7.sha1") {
            auto encapsulated = data.getContentInfo().getContent();
            unsigned char digest[20];
            cie::digest(EVP_sha1(), bytes.data(), bytes.size(), digest);
            if (encapsulated.getLength() != sizeof(digest) ||
                CRYPTO_memcmp(digest, encapsulated.getValue()->getContent(), sizeof(digest)) != 0) return -1;
            return data.verify(0, date, information);
        }
        UUCByteArray buffer(bytes.data(), bytes.size());
        CASN1OctetString content(buffer);
        auto signers = data.getSignerInfos();
        auto certificates = data.getCertificates();
        CSignerInfo signer(signers.elementAt(0));
        return CSignerInfo::verifySignature(content, signer, certificates, date, information);
    } catch (CASN1Exception* error) { delete error; return -1; }
    catch (...) { return -1; }
}
