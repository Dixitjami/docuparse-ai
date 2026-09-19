def calculate_confidence(question: dict[str, object], answer_matched: bool) -> float:
    """A transparent, non-statistical extraction quality heuristic."""
    score = 0.0
    if question.get("question_number"):
        score += 0.20
    if len(str(question.get("question_text") or "")) >= 10:
        score += 0.30
    options = question.get("options") or []
    if question.get("question_type") == "MCQ" and len(options) >= 2:
        score += 0.20
    elif question.get("question_type") == "SHORT_ANSWER":
        score += 0.20
    if question.get("source_pages"):
        score += 0.10
    if answer_matched:
        score += 0.20
    return round(min(score, 1.0), 2)


def extraction_status(confidence: float, review_required: bool) -> str:
    if review_required or confidence < 0.50:
        return "REVIEW"
    return "SUCCESS" if confidence >= 0.80 else "PARTIAL"
