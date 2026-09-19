from pathlib import Path


def register_and_login(client, email: str = "dixit@example.com") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"name": "Dixit", "email": email, "password": "password123"},
    )
    response = client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    return response.json()["access_token"]


def test_root_endpoint(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_documents_health_endpoint(client) -> None:
    response = client.get("/api/v1/documents/health")
    assert response.status_code == 200


def test_questions_health_endpoint(client) -> None:
    response = client.get("/api/v1/questions/health")
    assert response.status_code == 200


def test_upload_requires_authentication(client) -> None:
    response = client.post("/api/v1/documents/upload", files={"file": ("paper.pdf", b"pdf", "application/pdf")})
    assert response.status_code == 401


def test_upload_list_get_status_and_delete_document(client) -> None:
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("question-paper.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    assert upload.json()["status"] == "QUEUED"

    documents = client.get("/api/v1/documents", headers=headers)
    assert documents.status_code == 200
    assert [document["id"] for document in documents.json()["documents"]] == [document_id]

    document = client.get(f"/api/v1/documents/{document_id}", headers=headers)
    assert document.status_code == 200
    assert document.json()["filename"] == "question-paper.pdf"

    document_status = client.get(f"/api/v1/documents/{document_id}/status", headers=headers)
    assert document_status.json() == {
        "id": document_id,
        "status": "QUEUED",
        "progress": 0,
        "error_message": None,
    }

    extracted_text = client.get(f"/api/v1/documents/{document_id}/text", headers=headers)
    assert extracted_text.status_code == 200
    assert extracted_text.json() == {"document_id": document_id, "pages": []}

    deleted = client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/documents/{document_id}", headers=headers).status_code == 404


def test_same_filename_creates_independent_documents(client) -> None:
    """A Drive-style upload must never overwrite a prior file with the same name."""
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("same-name.pdf", b"first copy", "application/pdf")},
    )
    second = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("same-name.pdf", b"second copy", "application/pdf")},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    documents = client.get("/api/v1/documents", headers=headers).json()["documents"]
    assert {document["id"] for document in documents} == {first.json()["id"], second.json()["id"]}


def test_delete_linked_document_removes_relationship_first(client) -> None:
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    question_document = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("questions.pdf", b"questions", "application/pdf")},
    ).json()["id"]
    answer_key_document = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("answer-key.pdf", b"answers", "application/pdf")},
    ).json()["id"]
    related = client.post(
        f"/api/v1/documents/{question_document}/related",
        headers=headers,
        json={"related_document_id": answer_key_document, "relationship_type": "ANSWER_KEY"},
    )
    assert related.status_code == 201
    assert client.delete(f"/api/v1/documents/{answer_key_document}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/documents/{answer_key_document}", headers=headers).status_code == 404
    assert client.delete(f"/api/v1/documents/{question_document}", headers=headers).status_code == 204


def test_upload_valid_image_and_reject_invalid_files(client, monkeypatch) -> None:
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    image = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("scan.png", b"png", "image/png")},
    )
    assert image.status_code == 201

    unsupported = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("notes.txt", b"text", "text/plain")},
    )
    assert unsupported.status_code == 400

    from app.config import settings

    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 0)
    oversized = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("large.pdf", b"too large", "application/pdf")},
    )
    assert oversized.status_code == 413


def test_users_cannot_access_each_others_documents(client) -> None:
    first_token = register_and_login(client, "first@example.com")
    second_token = register_and_login(client, "second@example.com")
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}
    upload = client.post(
        "/api/v1/documents/upload",
        headers=first_headers,
        files={"file": ("private.pdf", b"private", "application/pdf")},
    )
    document_id = upload.json()["id"]

    assert client.get(f"/api/v1/documents/{document_id}", headers=second_headers).status_code == 404
    assert client.delete(f"/api/v1/documents/{document_id}", headers=second_headers).status_code == 404


def test_processing_task_completes_when_uploaded_file_exists(client) -> None:
    import fitz

    from app.models import Document
    from app.worker import process_document

    token = register_and_login(client)
    upload = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("ready.pdf", b"content", "application/pdf")},
    )
    document_id = upload.json()["id"]
    with client.app.state.testing_session() as db:
        document = db.get(Document, document_id)
        assert document is not None
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "What is Python?\nA. Programming language")
        pdf.save(document.storage_path)
        pdf.close()

    assert process_document.run(document_id) == "COMPLETED"
    with client.app.state.testing_session() as db:
        document = db.get(Document, document_id)
        assert document is not None
        assert document.status == "COMPLETED"
        assert document.processing_progress == 100
        assert "What is Python?" in document.extracted_text
        assert document.page_data[0]["method"] == "pdf_text"


def test_processing_task_marks_missing_file_as_failed(client) -> None:
    from app.models import Document
    from app.worker import process_document

    token = register_and_login(client)
    upload = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("missing.pdf", b"content", "application/pdf")},
    )
    document_id = upload.json()["id"]
    with client.app.state.testing_session() as db:
        document = db.get(Document, document_id)
        assert document is not None
        Path(document.storage_path).unlink()

    assert process_document.run(document_id) == "FAILED"
    with client.app.state.testing_session() as db:
        document = db.get(Document, document_id)
        assert document is not None
        assert document.status == "FAILED"
        assert document.processing_progress == 0
        assert document.error_message == "Uploaded file could not be found"
