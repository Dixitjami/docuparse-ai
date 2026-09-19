from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..models import Document, ProcessingWarning, Question
from .answer_extractor import extract_answers
from .confidence import calculate_confidence, extraction_status


def match_answers(db: Session, question_document: Document, answer_document: Document) -> int:
    """Apply an already processed answer-key document to a question document."""
    if not question_document.page_data or not answer_document.page_data:
        return 0
    answers = extract_answers(answer_document.page_data)
    questions = db.scalars(
        select(Question).where(Question.document_id == question_document.id).options(selectinload(Question.options))
    ).all()
    if not questions:
        return 0
    db.execute(delete(ProcessingWarning).where(
        ProcessingWarning.document_id == question_document.id,
        ProcessingWarning.warning_type.in_(["NO_ANSWER_FOUND", "INVALID_ANSWER", "LOW_CONFIDENCE"]),
    ))
    for question in questions:
        candidate = answers.get(question.question_number)
        option_keys = {option.option_key.upper() for option in question.options}
        invalid = candidate is not None and bool(option_keys) and candidate not in option_keys
        question.answer = None if invalid else candidate
        question.answer_confidence = 0.90 if question.answer else None
        data = {"question_number": question.question_number, "question_text": question.question_text, "question_type": question.question_type, "options": [{"key": option.option_key} for option in question.options], "source_pages": question.source_pages}
        question.confidence = calculate_confidence(data, question.answer is not None)
        question.review_required = question.confidence < 0.50 or invalid or (question.question_type == "MCQ" and len(question.options) < 2)
        question.extraction_status = extraction_status(question.confidence, question.review_required)
        if invalid:
            db.add(ProcessingWarning(document_id=question_document.id, question_id=question.id, warning_type="INVALID_ANSWER", message="Answer key value does not match an available option."))
        elif question.answer is None and answers:
            db.add(ProcessingWarning(document_id=question_document.id, question_id=question.id, warning_type="NO_ANSWER_FOUND", message="No reliable answer was found for this question."))
        if question.confidence < 0.50:
            db.add(ProcessingWarning(document_id=question_document.id, question_id=question.id, warning_type="LOW_CONFIDENCE", message="Question extraction confidence is below the review threshold.", confidence=question.confidence))
    db.flush()
    return len(questions)
