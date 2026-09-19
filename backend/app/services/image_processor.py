from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .ocr_service import extract_text_from_image


def process_image(file_path: str | Path) -> list[dict[str, object]]:
    """Extract text from one supported image document."""
    try:
        with Image.open(file_path) as image:
            # A wide question sheet usually has two numbered columns. OCR each
            # column independently so its question numbers stay with its text.
            if image.width / image.height > 1.2:
                split = image.width // 2
                left = image.crop((0, 100, split, image.height))
                right = image.crop((split, 100, image.width, image.height))
                text = "\n\n".join(
                    [
                        extract_text_from_image(left, "--psm 6"),
                        extract_text_from_image(right, "--psm 6"),
                    ]
                )
            else:
                # Tables such as an answer key are read much more reliably in
                # Tesseract's single-column/table layout mode.
                text = extract_text_from_image(image, "--psm 4")
    except UnidentifiedImageError as error:
        raise ValueError("The image could not be opened") from error
    return [{"page_number": 1, "text": text, "method": "ocr"}]
