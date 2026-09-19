from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine, init_db
from .routes import auth, documents, questions


@asynccontextmanager
async def lifespan(_: FastAPI):
    # A missing or stopped database should not prevent health endpoints from starting.
    try:
        init_db()
    except SQLAlchemyError:
        pass
    yield


app = FastAPI(
    title="Document Intelligence & Question Extraction Service API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(questions.document_questions_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Document Intelligence & Question Extraction Service API",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/db")
def database_health() -> dict[str, str]:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured")

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Database is unavailable") from error

    return {"status": "healthy", "database": "connected"}
