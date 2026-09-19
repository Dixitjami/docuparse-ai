from pathlib import Path

import fitz
from PIL import Image

from app.services import document_processor, image_processor, ocr_service
from app.services.pdf_processor import process_pdf
from app.services.text_normalizer import normalize_text


def test_text_normalization_preserves_meaningful_lines() -> None:
    assert normalize_text(" Question  1 \r\n\r\n A.  Option ") == "Question 1\n\nA. Option"


def test_pdf_processor_extracts_selectable_text(tmp_path: Path) -> None:
    path = tmp_path / "questions.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "What is SQL?\nA. Query language")
    pdf.save(path)
    pdf.close()

    pages = process_pdf(path)
    assert pages[0]["method"] == "pdf_text"
    assert "What is SQL?" in pages[0]["text"]


def test_image_processor_uses_ocr_service(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "question.png"
    Image.new("RGB", (20, 20), "white").save(path)
    monkeypatch.setattr(image_processor, "extract_text_from_image", lambda image: "OCR text")

    assert image_processor.process_image(path) == [
        {"page_number": 1, "text": "OCR text", "method": "ocr"}
    ]


def test_ocr_service_normalizes_tesseract_output(monkeypatch) -> None:
    image = Image.new("RGB", (20, 20), "white")
    monkeypatch.setattr(ocr_service.pytesseract, "image_to_string", lambda image, lang: " OCR   text \n")
    assert ocr_service.extract_text_from_image(image) == "OCR text"


def test_document_processor_selects_file_type(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "document.pdf"
    path.write_bytes(b"pdf")
    monkeypatch.setattr(document_processor, "process_pdf", lambda path, callback: [{"page_number": 1, "text": "text", "method": "pdf_text"}])

    assert document_processor.process_document(path)["pages"][0]["method"] == "pdf_text"


def test_document_processor_rejects_missing_file(tmp_path: Path) -> None:
    try:
        document_processor.process_document(tmp_path / "missing.pdf")
    except FileNotFoundError as error:
        assert str(error) == "Uploaded file could not be found"
    else:
        raise AssertionError("Expected missing file to be rejected")
