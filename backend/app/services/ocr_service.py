from PIL import Image
import pytesseract

from ..config import settings
from .text_normalizer import normalize_text


class OcrError(RuntimeError):
    """Raised when the local Tesseract executable cannot process an image."""


def extract_text_from_image(image: Image.Image, config: str = "") -> str:
    """Run basic image preparation and local Tesseract OCR."""
    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    prepared_image = image.convert("L")
    # Layout-specific OCR modes preserve their geometry best. Enlarging a
    # cropped column/table can merge option rows or lose a narrow table cell.
    if prepared_image.width < 1500 and not config:
        prepared_image = prepared_image.resize(
            (prepared_image.width * 2, prepared_image.height * 2)
        )
    try:
        if config:
            text = pytesseract.image_to_string(
                prepared_image, lang=settings.OCR_LANGUAGE, config=config
            )
        else:
            text = pytesseract.image_to_string(prepared_image, lang=settings.OCR_LANGUAGE)
    except pytesseract.TesseractNotFoundError as error:
        raise OcrError(
            "Tesseract OCR is not installed or is not on PATH. Install Tesseract and optionally set TESSERACT_CMD."
        ) from error
    except pytesseract.TesseractError as error:
        raise OcrError(f"Tesseract OCR failed: {error}") from error
    return normalize_text(text)
