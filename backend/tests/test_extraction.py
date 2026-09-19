from app.services.question_extractor import extract_questions
from app.services.answer_extractor import extract_answers
from app.services.confidence import calculate_confidence, extraction_status


def parse(text: str):
    return extract_questions([{"page_number": 1, "text": text, "method": "pdf_text"}])


def test_normal_numbered_mcqs() -> None:
    questions = parse("1. What is Python?\nA. Programming language\nB. Database\n2. What is SQL?\nA. Query language\nB. Browser")
    assert len(questions) == 2
    assert questions[0]["question_type"] == "MCQ"
    assert questions[0]["options"][0] == {"key": "A", "text": "Programming language"}


def test_q_format_and_parenthesized_options() -> None:
    question = parse("Q1) Choose one\n(a) First answer\n(b) Second answer")[0]
    assert question["question_number"] == "1"
    assert [option["key"] for option in question["options"]] == ["A", "B"]


def test_multiline_question_and_option() -> None:
    question = parse("Question 2: Which statement is\ncorrect?\nA. A high-level\n programming language\nB. A database")[0]
    assert question["question_text"] == "Which statement is correct?"
    assert question["options"][0]["text"] == "A high-level programming language"


def test_short_answer() -> None:
    question = parse("(3) Explain object-oriented programming.")[0]
    assert question["question_type"] == "SHORT_ANSWER"


def test_question_spanning_pages() -> None:
    questions = extract_questions([
        {"page_number": 1, "text": "5. Which feature hides implementation details", "method": "pdf_text"},
        {"page_number": 2, "text": "in object-oriented programming?\nA. Encapsulation\nB. Linking", "method": "pdf_text"},
    ])
    assert questions[0]["source_pages"] == [1, 2]
    assert "object-oriented programming" in questions[0]["question_text"]


def test_no_questions_found() -> None:
    assert parse("This document has no numbered items.") == []


def test_answer_key_formats_and_lowercase() -> None:
    pages = [{"page_number": 1, "text": "Answer Key\n1 - b\n2. A\nQ3 (c)", "method": "pdf_text"}]
    assert extract_answers(pages) == {"1": "B", "2": "A", "3": "C"}


def test_missing_or_invalid_answer_is_not_guessed() -> None:
    question = {"question_number": "1", "question_text": "What is Python?", "question_type": "MCQ", "options": [{"key": "A"}, {"key": "B"}], "source_pages": [1]}
    assert calculate_confidence(question, False) == 0.8
    assert extraction_status(0.4, False) == "REVIEW"
