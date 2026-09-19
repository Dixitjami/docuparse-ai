# Document Intelligence & Question Extraction Service

A small full-stack service for extracting questions and answers from documents.

Technology stack:

- FastAPI
- PostgreSQL
- Redis
- React
- OCR
- Docker

## Asynchronous Processing

Large documents should not block the API request while they are being processed.

Client → FastAPI → PostgreSQL → Redis → Celery Worker → PostgreSQL

After an upload, FastAPI saves document metadata and queues a background task in Redis. The Celery worker verifies that the uploaded file exists and updates the document status.

Start PostgreSQL and Redis:

```powershell
docker compose up -d postgres redis
```

Start FastAPI from `backend/`:

```powershell
python -m uvicorn app.main:app --reload
```

Start the worker from `backend/`:

```powershell
python -m celery -A app.worker.celery_app worker --loglevel=info --pool=solo
```

## OCR setup on Windows

Install Tesseract from PowerShell:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

Then reopen the terminal and run `tesseract --version` to confirm it is available. If it is installed outside your system `PATH`, set `TESSERACT_CMD` in `backend/.env` to the executable path. `pytesseract` is only the Python bridge; it does not install Tesseract itself.
