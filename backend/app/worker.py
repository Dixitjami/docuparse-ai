import logging
from pathlib import Path

from celery import Celery
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .database import SessionLocal, init_db
from .models import Document, DocumentRelationship, Option, ProcessingWarning, Question
from .services.document_processor import process_document as extract_document_text
from .services.question_extractor import extract_questions
from .services.answer_extractor import extract_answers
from .services.confidence import calculate_confidence, extraction_status
from .services.answer_matcher import match_answers

logger = logging.getLogger(__name__)

celery_app = Celery("document_intelligence", broker=settings.REDIS_URL, backend=settings.REDIS_URL)


@celery_app.task(name="process_document")
def process_document(document_id: str) -> str:
    """Extract document text in a separate worker database session."""
    db = SessionLocal()
    try:
        init_db()
        document = db.get(Document, document_id)
        if document is None:
            logger.warning("Document processing skipped; document not found: %s", document_id)
            return "NOT_FOUND"

        logger.info("Document processing started: %s", document_id)
        document.status = "PROCESSING"
        document.processing_progress = 10
        document.error_message = None
        db.commit()

        if not Path(document.storage_path).is_file():
            raise FileNotFoundError("Uploaded file could not be found")

        def update_progress(value: int) -> None:
            document.processing_progress = value
            db.commit()

        result = extract_document_text(document.storage_path, update_progress)
        pages = result["pages"]
        document.page_data = pages
        document.extracted_text = "\n\n".join(str(page["text"]) for page in pages)
        document.processing_progress = 90
        db.flush()

        db.query(ProcessingWarning).filter(ProcessingWarning.document_id == document.id).delete()
        for question in list(document.questions):
            db.delete(question)
        db.flush()

        extracted_questions = extract_questions(pages)
        answers = extract_answers(pages)
        if not extracted_questions:
            db.add(ProcessingWarning(
                document_id=document.id,
                warning_type="NO_QUESTIONS_DETECTED",
                message="No numbered questions were detected in the extracted text.",
            ))
        for extracted in extracted_questions:
            answer = answers.get(str(extracted["question_number"]))
            option_keys = {option["key"] for option in extracted["options"]}
            invalid_answer = answer is not None and bool(option_keys) and answer not in option_keys
            if invalid_answer:
                answer = None
            confidence = calculate_confidence(extracted, answer is not None)
            review_required = bool(extracted["review_required"]) or confidence < 0.50 or invalid_answer
            question = Question(
                document_id=document.id,
                question_number=str(extracted["question_number"]),
                question_text=str(extracted["question_text"]),
                question_type=str(extracted["question_type"]),
                source_pages=extracted["source_pages"],
                answer=answer,
                confidence=confidence,
                answer_confidence=0.90 if answer else None,
                review_required=review_required,
                extraction_status=extraction_status(confidence, review_required),
            )
            db.add(question)
            db.flush()
            if not question.question_text:
                db.add(ProcessingWarning(
                    document_id=document.id,
                    question_id=question.id,
                    warning_type="EMPTY_QUESTION_TEXT",
                    message=f"Question {question.question_number} has no detected text.",
                ))
            options = extracted["options"]
            if options and len(options) < 2:
                db.add(ProcessingWarning(
                    document_id=document.id,
                    question_id=question.id,
                    warning_type="INSUFFICIENT_OPTIONS",
                    message=f"Question {question.question_number} has fewer than two options.",
                ))
            if invalid_answer:
                db.add(ProcessingWarning(document_id=document.id, question_id=question.id, warning_type="INVALID_ANSWER", message="Answer key value does not match an available option."))
            elif answer is None and answers:
                db.add(ProcessingWarning(document_id=document.id, question_id=question.id, warning_type="NO_ANSWER_FOUND", message="No reliable answer was found for this question."))
            if confidence < 0.50:
                db.add(ProcessingWarning(document_id=document.id, question_id=question.id, warning_type="LOW_CONFIDENCE", message="Question extraction confidence is below the review threshold.", confidence=confidence))
            for option in options:
                db.add(Option(question_id=question.id, option_key=option["key"], option_text=option["text"]))

        document.status = "COMPLETED"
        document.processing_progress = 100
        db.commit()
        outgoing = db.scalars(select(DocumentRelationship).where(DocumentRelationship.document_id == document.id, DocumentRelationship.relationship_type == "ANSWER_KEY")).all()
        incoming = db.scalars(select(DocumentRelationship).where(DocumentRelationship.related_document_id == document.id, DocumentRelationship.relationship_type == "ANSWER_KEY")).all()
        for relationship in outgoing:
            answer_document = db.get(Document, relationship.related_document_id)
            if answer_document and answer_document.status == "COMPLETED":
                match_answers(db, document, answer_document)
        for relationship in incoming:
            question_document = db.get(Document, relationship.document_id)
            if question_document and question_document.status == "COMPLETED":
                match_answers(db, question_document, document)
        db.commit()
        logger.info("Document processing completed: %s", document_id)
        return "COMPLETED"
    except Exception as error:
        db.rollback()
        document = db.get(Document, document_id)
        if document is not None:
            document.status = "FAILED"
            document.processing_progress = 0
            document.error_message = str(error)
            db.commit()
        logger.exception("Document processing failed: %s", document_id)
        return "FAILED"
    finally:
        db.close()
