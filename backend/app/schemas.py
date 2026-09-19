from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(ORMModel):
    id: str
    name: str
    email: EmailStr
    created_at: datetime


class CurrentUserResponse(ORMModel):
    id: str
    name: str
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class DocumentCreate(BaseModel):
    filename: str
    file_type: str
    file_size: int = Field(ge=0)
    storage_path: str


class DocumentResponse(ORMModel):
    id: str
    user_id: str
    filename: str
    file_type: str
    file_size: int
    storage_path: str
    status: str
    processing_progress: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str


class DocumentListItem(ORMModel):
    id: str
    filename: str
    status: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    progress: int
    error_message: str | None = None


class OptionCreate(BaseModel):
    option_key: str
    option_text: str


class OptionResponse(ORMModel):
    id: str
    question_id: str
    option_key: str
    option_text: str


class QuestionCreate(BaseModel):
    question_number: str
    question_text: str
    question_type: str | None = None
    source_pages: list[int] | None = None


class QuestionResponse(ORMModel):
    id: str
    document_id: str
    question_number: str
    question_text: str
    question_type: str | None
    answer: str | None
    confidence: float | None
    answer_confidence: float | None
    review_required: bool
    source_pages: list[int] | None
    created_at: datetime
    options: list[OptionResponse] = []


class ProcessingWarningResponse(ORMModel):
    id: str
    document_id: str
    question_id: str | None
    warning_type: str
    message: str
    confidence: float | None
    created_at: datetime


class ExtractedOptionResponse(BaseModel):
    key: str
    text: str


class ExtractedQuestionResponse(BaseModel):
    id: str
    question_number: str
    question_text: str
    question_type: str | None
    answer: str | None
    source_pages: list[int] | None
    confidence: float | None
    answer_confidence: float | None
    review_required: bool
    extraction_status: str
    options: list[ExtractedOptionResponse]


class DocumentQuestionsResponse(BaseModel):
    document_id: str
    total: int
    questions: list[ExtractedQuestionResponse]


class RelatedDocumentCreate(BaseModel):
    related_document_id: str
    relationship_type: str = "ANSWER_KEY"


class AnswerResponse(BaseModel):
    question_id: str
    question_number: str
    answer: str | None
    answer_confidence: float | None
    message: str | None = None
