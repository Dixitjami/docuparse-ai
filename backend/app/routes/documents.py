from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import Document, DocumentRelationship, User
from ..schemas import (
    DocumentListItem,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    RelatedDocumentCreate,
)
from ..worker import process_document
from ..services.answer_matcher import match_answers

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

ALLOWED_FILE_TYPES = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
}
CHUNK_SIZE = 1024 * 1024


@router.get("/health")
def documents_health() -> dict[str, str]:
    return {"message": "Documents service is running"}


def upload_directory() -> Path:
    configured_path = Path(settings.UPLOAD_DIR)
    if configured_path.is_absolute():
        return configured_path
    return Path(__file__).resolve().parents[2] / configured_path


def get_owned_document(document_id: str, user_id: str, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF or image document",
)
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    original_filename = Path(file.filename or "").name
    extension = Path(original_filename).suffix.lower()
    allowed_mime_types = ALLOWED_FILE_TYPES.get(extension)
    if not original_filename or allowed_mime_types is None:
        raise HTTPException(status_code=400, detail="Only PDF, JPG, JPEG, and PNG files are supported")
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=400, detail="File MIME type does not match its extension")

    destination_directory = upload_directory()
    destination_directory.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4()}{extension}"
    storage_path = destination_directory / stored_filename
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    file_size = 0

    try:
        with storage_path.open("xb") as destination:
            while chunk := file.file.read(CHUNK_SIZE):
                file_size += len(chunk)
                if file_size > max_bytes:
                    raise HTTPException(status_code=413, detail="File exceeds the maximum allowed size")
                destination.write(chunk)
    except HTTPException:
        storage_path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    if file_size == 0:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    document = Document(
        user_id=current_user.id,
        filename=original_filename,
        file_type=file.content_type,
        file_size=file_size,
        storage_path=str(storage_path),
        status="QUEUED",
        processing_progress=0,
    )
    try:
        db.add(document)
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise

    try:
        process_document.delay(document.id)
    except Exception as error:
        db.delete(document)
        db.commit()
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Document processing queue is unavailable") from error

    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status,
        "message": "Document uploaded successfully",
    }


@router.get("", response_model=DocumentListResponse, summary="List the current user's documents")
def list_documents(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentListResponse:
    documents = db.scalars(
        select(Document).where(Document.user_id == current_user.id).order_by(Document.created_at.desc())
    ).all()
    return DocumentListResponse(documents=[DocumentListItem.model_validate(document) for document in documents])


@router.get("/{document_id}", response_model=DocumentResponse, summary="Get one owned document")
def get_document(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Document:
    return get_owned_document(document_id, current_user.id, db)


@router.get(
    "/{document_id}/status", response_model=DocumentStatusResponse, summary="Get document processing status"
)
def get_document_status(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, str | int | None]:
    document = get_owned_document(document_id, current_user.id, db)
    return {
        "id": document.id,
        "status": document.status,
        "progress": document.processing_progress,
        "error_message": document.error_message,
    }


@router.get("/{document_id}/text", summary="Get extracted text for an owned document")
def get_document_text(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    document = get_owned_document(document_id, current_user.id, db)
    return {"document_id": document.id, "pages": document.page_data or []}


@router.get("/{document_id}/file", summary="Preview or download an owned uploaded file")
def get_document_file(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FileResponse:
    """Serve an uploaded file only after confirming its ownership."""
    document = get_owned_document(document_id, current_user.id, db)
    storage_path = Path(document.storage_path)
    if not storage_path.is_file():
        raise HTTPException(status_code=404, detail="Uploaded file is no longer available")
    return FileResponse(storage_path, media_type=document.file_type, filename=document.filename)


@router.post("/{document_id}/related", status_code=status.HTTP_201_CREATED)
def relate_document(document_id: str, payload: RelatedDocumentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    document = get_owned_document(document_id, current_user.id, db)
    related = get_owned_document(payload.related_document_id, current_user.id, db)
    relationship_type = payload.relationship_type.upper()
    relationship = db.scalar(select(DocumentRelationship).where(DocumentRelationship.document_id == document.id, DocumentRelationship.related_document_id == related.id, DocumentRelationship.relationship_type == relationship_type))
    if relationship is None:
        relationship = DocumentRelationship(document_id=document.id, related_document_id=related.id, relationship_type=relationship_type)
        db.add(relationship)
        db.flush()
    if relationship_type == "ANSWER_KEY" and document.status == "COMPLETED" and related.status == "COMPLETED":
        match_answers(db, document, related)
    db.commit()
    return {"id": relationship.id, "relationship_type": relationship.relationship_type}


@router.get("/{document_id}/related")
def list_related_documents(document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    get_owned_document(document_id, current_user.id, db)
    relationships = db.scalars(select(DocumentRelationship).where(DocumentRelationship.document_id == document_id)).all()
    related_documents = []
    for item in relationships:
        related = db.get(Document, item.related_document_id)
        if related:
            related_documents.append({"id": related.id, "filename": related.filename, "relationship_type": item.relationship_type, "status": related.status})
    return {"documents": related_documents}


@router.delete("/{document_id}/related/{related_document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(document_id: str, related_document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    get_owned_document(document_id, current_user.id, db)
    get_owned_document(related_document_id, current_user.id, db)
    relationship = db.scalar(select(DocumentRelationship).where(DocumentRelationship.document_id == document_id, DocumentRelationship.related_document_id == related_document_id))
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    db.delete(relationship)
    db.commit()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an owned document")
def delete_document(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    document = get_owned_document(document_id, current_user.id, db)
    storage_path = Path(document.storage_path)
    try:
        storage_path.unlink(missing_ok=True)
    except OSError as error:
        # Do not remove the database record if Windows (or a synced Drive
        # client) is temporarily holding the file open.
        raise HTTPException(
            status_code=409,
            detail="The uploaded file is currently in use. Close its preview and try again.",
        ) from error
    # A question paper and an answer key can reference each other. Remove
    # those lightweight links first so either original upload can be deleted.
    db.execute(
        delete(DocumentRelationship).where(
            or_(
                DocumentRelationship.document_id == document.id,
                DocumentRelationship.related_document_id == document.id,
            )
        )
    )
    try:
        db.delete(document)
        db.commit()
    except Exception:
        db.rollback()
        raise
