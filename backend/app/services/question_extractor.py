import re
from dataclasses import dataclass, field


QUESTION_PATTERN = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?\(?([0-9]+|[gG])(?:\)\s*|\s*[.:,])\s*(.*)$", re.IGNORECASE
)
OPTION_PATTERN = re.compile(
    r"^\s*(?:\(([A-Da-d])\)|([A-Da-d])(?:[A-Da-d])?\s*[.)'’]|([1-9][0-9]*)\s*[.)])\s*(.*)$"
)


@dataclass
class ParsedQuestion:
    question_number: str
    explicit_question: bool = False
    parenthesized_number: bool = False
    question_lines: list[str] = field(default_factory=list)
    options: list[dict[str, str]] = field(default_factory=list)
    source_pages: list[int] = field(default_factory=list)
    _active_option: dict[str, str] | None = None

    def add_page(self, page_number: int) -> None:
        if page_number not in self.source_pages:
            self.source_pages.append(page_number)

    def add_option(self, key: str, text: str) -> None:
        option = {"key": key.upper(), "text": text.strip()}
        self.options.append(option)
        self._active_option = option

    def append_line(self, text: str) -> None:
        if self._active_option is not None:
            self._active_option["text"] = f"{self._active_option['text']} {text.strip()}".strip()
        else:
            self.question_lines.append(text.strip())

    def as_dict(self) -> dict[str, object]:
        question_text = " ".join(line for line in self.question_lines if line).strip()
        return {
            "question_number": self.question_number,
            "question_text": question_text,
            "question_type": "MCQ" if len(self.options) >= 2 else "SHORT_ANSWER",
            "source_pages": self.source_pages,
            "options": self.options,
            "review_required": not bool(question_text) or (bool(self.options) and len(self.options) < 2),
        }


def extract_questions(page_data: list[dict[str, object]]) -> list[dict[str, object]]:
    """Parse common numbered questions and answer options from extracted pages."""
    questions: list[ParsedQuestion] = []
    current: ParsedQuestion | None = None
    in_answer_section = False

    for page in page_data:
        page_number = int(page["page_number"])
        for raw_line in str(page.get("text", "")).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.fullmatch(r"\s*(answer key|correct answers|answers?)\s*", line, re.IGNORECASE):
                current = None
                in_answer_section = True
                continue
            # Answer-key rows such as "1. B 2. C" look like numbered
            # questions. They are data for answer extraction, not questions.
            if in_answer_section:
                continue
            question_match = QUESTION_PATTERN.match(line)
            if question_match:
                detected_number = question_match.group(1)
                # In photographed sheets, Tesseract commonly reads a printed
                # 8 as "g". Treat it as a question number only at line start.
                question_number = "8" if detected_number.lower() == "g" else detected_number
                current = ParsedQuestion(
                    question_number=question_number,
                    explicit_question=bool(re.match(r"^\s*Q(?:uestion)?\s*", line, re.IGNORECASE)),
                    parenthesized_number=bool(re.match(r"^\s*\(", line)),
                )
                current.add_page(page_number)
                remainder = question_match.group(2).strip()
                if remainder:
                    current.question_lines.append(remainder)
                questions.append(current)
                continue
            if current is None:
                continue
            current.add_page(page_number)
            option_match = OPTION_PATTERN.match(line)
            if option_match:
                parenthesized_key, letter_key, number_key, option_text = option_match.groups()
                # A numbered line following a question is an option; a question header was handled first.
                current.add_option(parenthesized_key or letter_key or number_key, option_text)
            else:
                current.append_line(line)

    # Ignore numbered document headings (for example, "1. Arrays") while
    # retaining MCQs, incomplete MCQs, conventional question sentences, and
    # explicit Q1/Question 1 short-answer prompts.
    return [
        question.as_dict()
        for question in questions
        if question.options
        or "?" in " ".join(question.question_lines)
        or question.explicit_question
        or question.parenthesized_number
    ]
