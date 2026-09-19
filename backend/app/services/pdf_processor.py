from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image

from .ocr_service import extract_text_from_image
from .text_normalizer import normalize_text

USEFUL_TEXT_MINIMUM = 20


def process_pdf(file_path: str | Path, progress_callback: Callable[[int], None] | None = None) -> list[dict[str, object]]:
    """Extract selectable text page-by-page, using OCR only when needed."""
    pages: list[dict[str, object]] = []
    try:
        pdf = fitz.open(file_path)
    except (fitz.FileDataError, RuntimeError) as error:
        raise ValueError("The PDF could not be opened") from error

    with pdf:
        if pdf.page_count == 0:
            raise ValueError("The PDF does not contain any pages")
        for index, page in enumerate(pdf):
            extracted_text = normalize_text(page.get_text("text"))
            method = "pdf_text"
            if len(extracted_text) < USEFUL_TEXT_MINIMUM:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                    extracted_text = extract_text_from_image(image)
                method = "ocr"
            pages.append({"page_number": index + 1, "text": extracted_text, "method": method})
            if progress_callback:
                progress_callback(20 + int((index + 1) / pdf.page_count * 70))
    return pages
