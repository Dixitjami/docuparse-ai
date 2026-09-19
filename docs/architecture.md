# Architecture

```
React UI → FastAPI → PostgreSQL
                 ↓
               Redis → Celery Worker → PDF/OCR → Questions/Answers → PostgreSQL
```

React provides the authenticated dashboard. FastAPI owns HTTP APIs, authorization, and document metadata. PostgreSQL stores users, documents, extracted text, questions, options, answers, and warnings.

Uploads are queued in Redis. A single Celery worker reads the file, extracts text with PyMuPDF or Tesseract OCR, parses questions/options, matches deterministic answer keys, and saves confidence/review results.
