from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""


engine = (
    create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    if settings.DATABASE_URL
    else None
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request."""
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create development tables when a database connection is configured."""
    if engine is None:
        return

    from . import models  # noqa: F401 - imports models before metadata creation

    Base.metadata.create_all(bind=engine)
    existing_columns = {column["name"] for column in inspect(engine).get_columns("documents")}
    json_type = "JSONB" if engine.dialect.name == "postgresql" else "JSON"
    with engine.begin() as connection:
        if "extracted_text" not in existing_columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN extracted_text TEXT"))
        if "page_data" not in existing_columns:
            connection.execute(text(f"ALTER TABLE documents ADD COLUMN page_data {json_type}"))
        question_columns = {column["name"] for column in inspect(engine).get_columns("questions")}
        if "extraction_status" not in question_columns:
            connection.execute(text("ALTER TABLE questions ADD COLUMN extraction_status VARCHAR(20) DEFAULT 'PARTIAL' NOT NULL"))
