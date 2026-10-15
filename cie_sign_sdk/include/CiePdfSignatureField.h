#ifndef CIE_PDF_SIGNATURE_FIELD_H
#define CIE_PDF_SIGNATURE_FIELD_H

#include <podofo/podofo.h>

// SDK-facing adapter for the public PoDoFo 0.9.8 API. The old Intel archive
// exposed extra signature methods whose implementation was not distributed.
class CiePdfSignatureField : public PoDoFo::PdfSignatureField
{
public:
    CiePdfSignatureField(PoDoFo::PdfPage* page, const PoDoFo::PdfRect& rect,
                        PoDoFo::PdfDocument* document, const PoDoFo::PdfString& name,
                        const char* subFilter);
    void SetSignatureReason(const PoDoFo::PdfString& label, const PoDoFo::PdfString& value);
    void SetSignatureLocation(const PoDoFo::PdfString& label, const PoDoFo::PdfString& value);
    void SetSignatureName(const PoDoFo::PdfString& label, const PoDoFo::PdfString& value);
    void SetSignatureSize(size_t size);
    void SetAppearance(const char* imagePath, const char* description);
    void SetGraphometricData(const PoDoFo::PdfString& name, const PoDoFo::PdfString& data,
                            const PoDoFo::PdfString& version);

private:
    PoDoFo::PdfDocument* document_;
    PoDoFo::PdfRect rect_;
};

#endif
