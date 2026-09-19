from collections.abc import Callable
from pathlib import Path

from .image_processor import process_image
from .pdf_processor import process_pdf


def process_document(
    file_path: str | Path, progress_callback: Callable[[int], None] | None = None
) -> dict[str, list[dict[str, object]]]:
    """Choose PDF text extraction or image OCR based on the uploaded file extension."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError("Uploaded file could not be found")

    extension = path.suffix.lower()
    if extension == ".pdf":
        pages = process_pdf(path, progress_callback)
    elif extension in {".jpg", ".jpeg", ".png"}:
        pages = process_image(path)
        if progress_callback:
            progress_callback(90)
    else:
        raise ValueError("Unsupported document type")

    if not any(page["text"] for page in pages):
        raise ValueError("No text could be extracted from document")
    return {"pages": pages}
