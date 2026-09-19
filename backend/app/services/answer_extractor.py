import re

ANSWER_SECTION = re.compile(r"\b(answer key|correct answers|answers?|answer)\b", re.IGNORECASE)
# Answer keys are commonly formatted either one answer per line ("1. B") or
# several pairs on one line ("1. B 2. C 3. A").  Capture every pair after the
# answer-key heading instead of requiring the entire line to contain one pair.
ANSWER_PAIR = re.compile(
    r"(?:^|\s)(?:Q\s*)?(\d+)\s*(?:[-.:)]\s*|\s+)(?:\(?\s*)?([A-Da-d])(?:[A-Da-d])?(?:\s*\))?(?=\s|$)",
    re.IGNORECASE,
)


def extract_answers(page_data: list[dict[str, object]]) -> dict[str, str]:
    """Find a labeled answer section and return normalized question-to-letter mappings."""
    answers: dict[str, str] = {}
    in_answer_section = False
    for page in page_data:
        for line in str(page.get("text", "")).splitlines():
            if ANSWER_SECTION.search(line):
                in_answer_section = True
                continue
            if in_answer_section:
                for match in ANSWER_PAIR.finditer(line):
                    number, answer = match.groups()
                    answers[number] = answer.upper()
    return answers
