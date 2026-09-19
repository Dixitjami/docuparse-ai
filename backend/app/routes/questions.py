from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Integer, cast, select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..database import get_db
from ..models import Document, Question, User, ProcessingWarning
from ..schemas import AnswerResponse, DocumentQuestionsResponse, ExtractedQuestionResponse

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])
document_questions_router = APIRouter(prefix="/api/v1/documents", tags=["questions"])


@router.get("/health")
def questions_health() -> dict[str, str]:
    return {"message": "Questions service is running"}


def question_response(question: Question) -> ExtractedQuestionResponse:
    return ExtractedQuestionResponse(
        id=question.id,
        question_number=question.question_number,
        question_text=question.question_text,
        question_type=question.question_type,
        answer=question.answer,
        source_pages=question.source_pages,
        confidence=question.confidence,
        answer_confidence=question.answer_confidence,
        review_required=question.review_required,
        extraction_status=question.extraction_status,
        options=[{"key": option.option_key, "text": option.option_text} for option in question.options],
    )


@document_questions_router.get("/{document_id}/questions", response_model=DocumentQuestionsResponse)
def list_document_questions(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentQuestionsResponse:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    questions = db.scalars(
        select(Question)
        .where(Question.document_id == document_id)
        .options(selectinload(Question.options))
        .order_by(cast(Question.question_number, Integer), Question.created_at)
    ).all()
    return DocumentQuestionsResponse(
        document_id=document_id, total=len(questions), questions=[question_response(question) for question in questions]
    )


@router.get("/{question_id}", response_model=ExtractedQuestionResponse)
def get_question(
    question_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ExtractedQuestionResponse:
    question = db.scalar(select(Question).where(Question.id == question_id).options(selectinload(Question.options)))
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    document = db.get(Document, question.document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Question not found")
    return question_response(question)


@router.get("/{question_id}/answer", response_model=AnswerResponse)
def get_answer(question_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AnswerResponse:
    question = db.get(Question, question_id)
    if question is None or (document := db.get(Document, question.document_id)) is None or document.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Question not found")
    return AnswerResponse(question_id=question.id, question_number=question.question_number, answer=question.answer, answer_confidence=question.answer_confidence, message=None if question.answer else "No reliable answer was found")


@document_questions_router.get("/{document_id}/warnings")
def get_document_warnings(document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    warnings = db.scalars(select(ProcessingWarning).where(ProcessingWarning.document_id == document_id)).all()
    return {"document_id": document_id, "total": len(warnings), "warnings": [{"question_id": warning.question_id, "warning_type": warning.warning_type, "message": warning.message, "confidence": warning.confidence} for warning in warnings]}
