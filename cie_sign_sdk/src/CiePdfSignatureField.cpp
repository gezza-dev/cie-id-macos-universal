// SPDX-License-Identifier: BSD-3-Clause
#include "CiePdfSignatureField.h"
#include <algorithm>
#include <stdexcept>
namespace cie {
void setSignatureAppearance(PoDoFo::PdfDocument& document, PoDoFo::PdfSignature& signature,
    const PoDoFo::Rect& rectangle, const char* imagePath, const char* description)
{
    using namespace PoDoFo;
    auto appearance = document.CreateXObjectForm(Rect(0, 0, rectangle.Width, rectangle.Height));
    PdfPainter painter;
    painter.SetCanvas(*appearance);
    if (imagePath && *imagePath) {
        auto image = document.CreateImage();
        image->Load(imagePath);
        if (!image->GetWidth() || !image->GetHeight()) throw std::runtime_error("Invalid signature image");
        double scale = std::min(rectangle.Width / image->GetWidth(), rectangle.Height / image->GetHeight());
        painter.DrawImage(*image, (rectangle.Width - image->GetWidth() * scale) / 2,
            (rectangle.Height - image->GetHeight() * scale) / 2, scale, scale);
    }
    if (description && *description) {
        auto& font = document.GetFonts().GetStandard14Font(PdfStandard14FontType::Helvetica);
        painter.TextState.SetFont(font, 8);
        painter.DrawText(description, 2, 2);
    }
    painter.FinishDrawing();
    signature.MustGetWidget().SetAppearanceStream(*appearance);
}
}
