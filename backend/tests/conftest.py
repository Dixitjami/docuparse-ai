from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app import worker
from app.routes import documents


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Run endpoint tests against an isolated SQLite database and upload folder."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(settings, "SECRET_KEY", "test-only-secret")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(worker, "SessionLocal", testing_session)
    monkeypatch.setattr(worker, "init_db", lambda: None)
    monkeypatch.setattr(documents.process_document, "delay", lambda document_id: None)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.testing_session = testing_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    del app.state.testing_session
    test_engine.dispose()
